"""Durable Leader commands, shared by HTTP and the native socket gateway."""
import hashlib
import json
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy import text

from app.realtime.rooms import RoomError, envelope


class Moderation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    commandId: UUID
    correlationId: UUID
    expectedStateVersion: StrictInt = Field(ge=0)
    action: Literal['mute', 'unmute', 'remove', 'lockRoom', 'unlockRoom', 'transfer']
    targetUserId: UUID | None = None

    @model_validator(mode='after')
    def target_required(self):
        targeted = self.action in ('mute', 'unmute', 'remove', 'transfer')
        if targeted != (self.targetUserId is not None):
            raise ValueError('target must be supplied only for participant actions')
        return self


async def moderate(room, actor, command: Moderation):
    await room.load()
    fingerprint = hashlib.sha256(json.dumps(command.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    async with room.lock:
        async with room.transaction_locked() as conn:
            current = (await conn.execute(text('''SELECT t.state_version,t.status,t.room_locked,t.planning_session_id,
                t.leader_user_id,m.role FROM trips t JOIN memberships m ON m.trip_id=t.id
                JOIN auth_sessions s ON s.user_id=m.user_id WHERE t.id=:trip AND m.user_id=:uid
                AND m.status='active' AND s.id=:session AND s.revoked_at IS NULL AND s.expires_at>now()'''),
                {'trip':room.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).mappings().first()
            if not current:
                raise RoomError('NOT_FOUND')
            prior = (await conn.execute(text('SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:command'),
                {'trip':room.trip_id,'command':command.commandId})).mappings().first()
            if prior:
                if str(prior['actor_id']) != str(actor['user_id']) or prior['payload'].get('commandHash') != fingerprint:
                    raise RoomError('COMMAND_ID_REUSE')
                return {'commandId':str(command.commandId),'status':'duplicate','durable':True,
                        'roomSeq':prior['payload']['roomSeq'],'committedSeq':room.seq,
                        'stateVersion':prior['payload']['stateVersion']}
            if current['role'] != 'leader' or current['status'] == 'finalized':
                raise RoomError('FORBIDDEN')
            connected = {str(a['user_id']) for a in room.connections.values()}
            if str(actor['user_id']) not in connected:
                raise RoomError('LEADER_DISCONNECTED')
            if current['state_version'] != command.expectedStateVersion:
                raise RoomError('STALE_STATE_VERSION', {'currentStateVersion':current['state_version']})
            if command.targetUserId is not None:
                target = (await conn.execute(text("SELECT role FROM memberships WHERE trip_id=:trip AND user_id=:uid AND status='active'"),
                    {'trip':room.trip_id,'uid':command.targetUserId})).mappings().first()
                if not target:
                    raise RoomError('TARGET_UNAVAILABLE')
                if target['role'] == 'leader':
                    raise RoomError('INVALID_TARGET')
                if command.action == 'transfer' and (target['role'] != 'planner' or str(command.targetUserId) not in connected):
                    raise RoomError('INVALID_TARGET')
            params = {'trip':room.trip_id,'target':command.targetUserId}
            leader = current['leader_user_id']
            locked = current['room_locked']
            if command.action in ('mute', 'unmute'):
                await conn.execute(text('UPDATE memberships SET muted=:muted WHERE trip_id=:trip AND user_id=:target'),
                    params | {'muted':command.action == 'mute'})
            elif command.action == 'remove':
                await conn.execute(text("UPDATE memberships SET status='removed' WHERE trip_id=:trip AND user_id=:target"), params)
            elif command.action == 'transfer':
                await conn.execute(text("UPDATE memberships SET role='planner' WHERE trip_id=:trip AND user_id=:uid AND role='leader'"),
                    {'trip':room.trip_id,'uid':actor['user_id']})
                await conn.execute(text("UPDATE memberships SET role='leader' WHERE trip_id=:trip AND user_id=:target"), params)
                leader = command.targetUserId
            else:
                locked = command.action == 'lockRoom'
            seq = room.seq + 1
            version = current['state_version'] + 1
            result = await conn.execute(text('''UPDATE trips SET state_version=:version,room_seq=:seq,committed_seq=:seq,
                leader_user_id=:leader,room_locked=:locked WHERE id=:trip AND state_version=:base_version
                AND committed_seq=:base_seq RETURNING id'''),
                {'trip':room.trip_id,'version':version,'seq':seq,'leader':leader,'locked':locked,
                 'base_version':current['state_version'],'base_seq':room.seq})
            if not result.first():
                raise RuntimeError('durable moderation version mismatch')
            rows = (await conn.execute(text('''SELECT m.user_id,m.role,m.can_pin,m.muted,u.display_name FROM memberships m
                JOIN users u ON u.id=m.user_id WHERE m.trip_id=:trip AND m.status='active' ORDER BY m.user_id'''),
                {'trip':room.trip_id})).mappings().all()
            leaders = [r for r in rows if r['role'] == 'leader']
            if len(leaders) != 1 or leaders[0]['user_id'] != leader:
                raise RuntimeError('invalid Leader ownership')
            active_ids = {str(r['user_id']) for r in rows}
            payload = {'action':command.action,'targetUserId':str(command.targetUserId) if command.targetUserId else None,
                'stateVersion':version,'roomSeq':seq,'roomEpoch':room.epoch,'durable':True,
                'commandId':str(command.commandId),'correlationId':str(command.correlationId),'eventId':str(uuid4()),
                'roomLocked':locked,'leaderUserId':str(leader),'leaderConnected':str(leader) in connected,
                'connectedUsers':sorted(connected & active_ids),
                'members':[{'userId':str(r['user_id']),'displayName':r['display_name'],'role':r['role'],
                            'canPin':r['can_pin'],'muted':r['muted']} for r in rows]}
            await conn.execute(text('''INSERT INTO room_events (trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
                VALUES (:trip,:seq,:event,:command,:session,:actor,'trip.moderation.update',CAST(:payload AS jsonb))'''),
                {'trip':room.trip_id,'seq':seq,'event':UUID(payload['eventId']),'command':command.commandId,
                 'session':current['planning_session_id'],'actor':actor['user_id'],
                 'payload':json.dumps(payload | {'commandHash':fingerprint})})
        room.seq = room.committed = seq
        if command.action == 'remove':
            for queue, identity in tuple(room.connections.items()):
                if identity['user_id'] == command.targetUserId:
                    room.subscribers.discard(queue)
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait({'closeCode':1008})
        if command.action in ('mute', 'remove'):
            uid = str(command.targetUserId)
            task = room.typing_tasks.pop(uid, None)
            if task:
                task.cancel()
            room.typing_last.pop(uid, None)
            room.publish(envelope('trip.chat.typing.update',room.trip_id,{'userId':uid,'isTyping':False,'expiresAt':None}))
        room.publish(envelope('trip.moderation.update',room.trip_id,payload))
        room.audit('trip.moderation.committed',command.correlationId)
        return {'commandId':str(command.commandId),'status':'committed','roomSeq':seq,
                'stateVersion':version,'durable':True,'committedSeq':seq}
