"""Versioned trip category defaults and each member's own declared constraints."""
import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from sqlalchemy import text
from app.realtime.rooms import RoomError, envelope

Category=Literal['food','activity','lodging','transit']
Diet=Literal['vegetarian','vegan','halal','gluten-free']
Minor=Annotated[StrictInt,Field(gt=0,le=10**12)]


class Preferences(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dietaryTags: list[Diet]=Field(default_factory=list,max_length=4)
    categoryCeilingsMinor: dict[Category,Minor]=Field(default_factory=dict)

    @model_validator(mode='after')
    def unique_diets(self):
        if len(self.dietaryTags)!=len(set(self.dietaryTags)): raise ValueError('duplicate dietary tag')
        return self


class ConstraintsUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    commandId: UUID
    correlationId: UUID
    expectedStateVersion: StrictInt=Field(ge=0)
    categoryCeilingsMinor: dict[Category,Minor] | None=None
    constraints: Preferences | None=None
    targetUserId: UUID | None=None

    @model_validator(mode='after')
    def one_scope(self):
        group=self.categoryCeilingsMinor is not None
        if group == (self.constraints is not None) or (group and self.targetUserId is not None) or (not group and self.targetUserId is None):
            raise ValueError('supply either group ceilings or member constraints with targetUserId')
        return self


async def update_constraints(room,actor,command):
    await room.load()
    fingerprint=hashlib.sha256(json.dumps(command.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
    async with room.lock:
        async with room.transaction_locked() as conn:
            current=(await conn.execute(text('''SELECT t.state_version,t.planning_session_id,t.status,t.category_ceilings,m.role
                FROM trips t JOIN memberships m ON m.trip_id=t.id JOIN auth_sessions s ON s.user_id=m.user_id
                WHERE t.id=:trip AND m.user_id=:uid AND m.status='active' AND s.id=:session
                AND s.revoked_at IS NULL AND s.expires_at>now()'''),
                {'trip':room.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).mappings().first()
            if not current: raise RoomError('NOT_FOUND')
            prior=(await conn.execute(text('SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:command'),
                {'trip':room.trip_id,'command':command.commandId})).mappings().first()
            if prior:
                if str(prior['actor_id'])!=str(actor['user_id']) or prior['payload'].get('commandHash')!=fingerprint:
                    raise RoomError('COMMAND_ID_REUSE')
                return {'commandId':str(command.commandId),'status':'duplicate','roomSeq':prior['payload']['roomSeq'],'durable':True,'committedSeq':room.seq}
            if current['status']=='finalized': raise RoomError('FORBIDDEN')
            group=command.categoryCeilingsMinor is not None
            if group:
                if current['role']!='leader': raise RoomError('FORBIDDEN')
                if not any(a['user_id']==actor['user_id'] for a in room.connections.values()): raise RoomError('LEADER_DISCONNECTED')
            elif command.targetUserId!=actor['user_id']:
                raise RoomError('FORBIDDEN')
            if current['state_version']!=command.expectedStateVersion:
                raise RoomError('STALE_STATE_VERSION',{'currentStateVersion':current['state_version']})
            ceilings=command.categoryCeilingsMinor if group else current['category_ceilings']
            seq, version=room.seq+1,current['state_version']+1
            result=await conn.execute(text('''UPDATE trips SET state_version=:version,category_ceilings=CAST(:ceilings AS jsonb),
                room_seq=:seq,committed_seq=:seq WHERE id=:trip AND state_version=:base_version AND committed_seq=:base_seq RETURNING id'''),
                {'trip':room.trip_id,'version':version,'ceilings':json.dumps(ceilings),'seq':seq,
                 'base_version':current['state_version'],'base_seq':room.seq})
            if not result.first(): raise RuntimeError('durable constraints version mismatch')
            if not group:
                await conn.execute(text('UPDATE memberships SET constraints=CAST(:constraints AS jsonb) WHERE trip_id=:trip AND user_id=:uid'),
                    {'trip':room.trip_id,'uid':actor['user_id'],'constraints':command.constraints.model_dump_json()})
            payload={'roomSeq':seq,'roomEpoch':room.epoch,'stateVersion':version,'durable':True,
                     'commandId':str(command.commandId),'correlationId':str(command.correlationId),'eventId':str(uuid4()),
                     'targetUserId':str(command.targetUserId) if command.targetUserId else None,'categoryCeilingsMinor':ceilings}
            await conn.execute(text('''INSERT INTO room_events (trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
                VALUES (:trip,:seq,:event,:command,:session,:actor,'trip.constraints.update',CAST(:payload AS jsonb))'''),
                {'trip':room.trip_id,'seq':seq,'event':UUID(payload['eventId']),'command':command.commandId,
                 'session':current['planning_session_id'],'actor':actor['user_id'],
                 'payload':json.dumps(payload | {'commandHash':fingerprint})})
        room.seq=room.committed=seq
        room.publish(envelope('trip.constraints.update',room.trip_id,payload))
        room.audit('trip.constraints.committed',command.correlationId)
        return {'commandId':str(command.commandId),'status':'committed','roomSeq':seq,'stateVersion':version,'durable':True,'committedSeq':seq}
