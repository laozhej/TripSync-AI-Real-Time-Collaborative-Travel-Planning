"""Process-local room authority for the initial pin/snapshot slice.

Only one application worker may use a database. Pending pins are volatile until
an atomic batch transaction advances committed_seq. A failed batch freezes the
actor rather than attempting an unsafe retry after an uncertain commit.
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import HTTPException
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from app.auth.policy import Capability, Membership, Role, permitted
from app.board.lifecycle import BoardConflict, BoardForbidden, BoardInvalid, apply_change

logger=logging.getLogger('tripsync.room')
if not logger.handlers:
    handler=logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate=False


def envelope(event, trip_id, payload):
    return {"event": event, "tripId": str(trip_id), "payload": payload,
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000)}


async def reaction_groups(conn, message_ids):
    if not message_ids:
        return {}
    rows = (await conn.execute(text('SELECT message_id,emoji,user_id FROM reactions WHERE message_id=ANY(:ids)'),
                               {'ids':list(message_ids)})).mappings().all()
    grouped = {}
    for row in rows:
        emojis = grouped.setdefault(str(row['message_id']), {})
        emojis.setdefault(row['emoji'], []).append(str(row['user_id']))
    return {mid:[{'emoji':emoji,'userIds':sorted(users)} for emoji,users in sorted(emojis.items())]
            for mid,emojis in grouped.items()}


class RoomError(Exception):
    def __init__(self, code, details=None):
        self.code = code
        self.details = details
        super().__init__(code)


class Room:
    def __init__(self, manager, trip_id):
        self.manager, self.trip_id = manager, trip_id
        self.lock = asyncio.Lock()
        self.epoch = str(uuid4())
        self.session_id = None
        self.seq = self.committed = 0
        self.items = {}
        self.commands = {}
        self.ai_locks = {}
        self.pending = []
        self.subscribers = set()
        self.connections = {}
        self.typing_tasks = {}
        self.typing_last = {}
        self.loaded = False
        self.frozen = False

    async def load(self):
        async with self.lock:
            if self.loaded:
                return
            async with self.manager.engine.begin() as conn:
                trip = (await conn.execute(text("SELECT committed_seq,planning_session_id FROM trips WHERE id=:id"), {"id":self.trip_id})).mappings().first()
                if trip is None:
                    raise RoomError("NOT_FOUND")
                self.seq = self.committed = trip['committed_seq']
                self.session_id = str(trip['planning_session_id'])
                # A fresh epoch makes any previously observed volatile future invalid.
                await conn.execute(text("UPDATE trips SET room_epoch=:epoch,room_seq=committed_seq WHERE id=:id"),
                                   {"epoch":UUID(self.epoch), "id":self.trip_id})
                rows = (await conn.execute(text("""SELECT i.id,i.venue_id,i.day_index,i.starts_at,i.ends_at,
                    i.lifecycle_stage,i.position_version,i.price_snapshot_minor,v.name,
                    ARRAY(SELECT a.user_id FROM item_attendees a WHERE a.item_id=i.id ORDER BY a.user_id) AS attendees FROM itinerary_items i
                    JOIN venue_metadata v ON v.id=i.venue_id AND v.dataset_id=i.dataset_id
                    WHERE i.trip_id=:id AND i.removed_at IS NULL ORDER BY i.id"""), {"id":self.trip_id})).mappings().all()
                for row in rows:
                    item = {"itemId":str(row['id']),"venueId":str(row['venue_id']),"name":row['name'],
                            "dayIndex":row['day_index'],"startTime":row['starts_at'].isoformat(),
                            "endTime":row['ends_at'].isoformat(),"lifecycleStage":row['lifecycle_stage'],
                            "positionVersion":row['position_version'],"pricePerPersonMinor":row['price_snapshot_minor'],
                            "attendeeIds":[str(uid) for uid in row['attendees']]}
                    self.items[item['itemId']] = item
            self.loaded = True
            self.audit('trip.room.loaded')

    def audit(self,event,correlation_id=None):
        # Whitelist only operational identifiers and watermarks. Never include
        # tokens, questions, messages, member preferences or raw exceptions.
        logger.info(json.dumps({'event':event,'tripId':str(self.trip_id),'sessionId':self.session_id,
            'roomEpoch':self.epoch,'roomSeq':self.seq,'committedSeq':self.committed,
            'correlationId':str(correlation_id) if correlation_id is not None else None,
            'ts':datetime.now(timezone.utc).isoformat()}))

    def publish(self, event):
        for queue in tuple(self.subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                self.subscribers.discard(queue)
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)

    def budget_summary(self, currency):
        proposed = locked = 0
        people = {}
        for item in self.items.values():
            price = item.get('pricePerPersonMinor', 0)
            attendees = item.get('attendeeIds', [])
            total = price * len(attendees)
            proposed += total
            if item['lifecycleStage'] == 'locked':
                locked += total
            for uid in attendees:
                person = people.setdefault(uid, {'userId':uid,'proposedMinor':0,'lockedMinor':0})
                person['proposedMinor'] += price
                if item['lifecycleStage'] == 'locked':
                    person['lockedMinor'] += price
        return {'currency':currency,'proposedMinor':proposed,'lockedMinor':locked,
                'perPerson':[people[key] for key in sorted(people)]}

    async def snapshot_locked(self, actor=None):
        own_constraints = {}
        async with self.manager.engine.connect() as conn:
            if actor is not None:
                visible = (await conn.execute(text("""SELECT m.constraints FROM memberships m JOIN auth_sessions s ON s.user_id=m.user_id
                    WHERE m.trip_id=:trip AND m.user_id=:uid AND m.status='active' AND s.id=:session
                    AND s.revoked_at IS NULL AND s.expires_at>now()"""),
                    {'trip':self.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).first()
                if not visible:
                    raise RoomError('FORBIDDEN')
                own_constraints = visible[0]
            trip = (await conn.execute(text("SELECT currency,status,room_locked,state_version,planning_session_id,category_ceilings,timezone FROM trips WHERE id=:id"),
                                       {'id':self.trip_id})).mappings().one()
            rows = (await conn.execute(text("""SELECT m.user_id,m.role,m.can_pin,m.muted,u.display_name FROM memberships m
                JOIN users u ON u.id=m.user_id WHERE m.trip_id=:trip AND m.status='active'
                ORDER BY m.joined_at,m.user_id"""), {'trip':self.trip_id})).mappings().all()
            messages = (await conn.execute(text('''SELECT id,user_id,body,created_at,room_seq FROM
                (SELECT id,user_id,body,created_at,room_seq FROM chat_messages WHERE trip_id=:trip
                 ORDER BY room_seq DESC LIMIT 101) recent ORDER BY room_seq'''), {'trip':self.trip_id})).mappings().all()
            has_more = len(messages) > 100
            messages = messages[-100:]
            reactions = await reaction_groups(conn, [m['id'] for m in messages])
            latest_answer = (await conn.execute(text('SELECT response FROM ai_questions WHERE trip_id=:trip ORDER BY created_at DESC,id DESC LIMIT 1'),
                {'trip':self.trip_id})).scalar_one_or_none()
        return {'roomEpoch':self.epoch,'roomSeq':self.seq,'committedSeq':self.committed,
                'connectedUsers':sorted({str(a['user_id']) for a in self.connections.values()}),
                'leaderConnected':any(row['role']=='leader' and any(str(a['user_id'])==str(row['user_id']) for a in self.connections.values()) for row in rows),
                'stateVersion':trip['state_version'],'sessionId':str(trip['planning_session_id']),
                'trip':{'status':trip['status'],'roomLocked':trip['room_locked'],'categoryCeilingsMinor':trip['category_ceilings'],'timezone':trip['timezone']},
                'preferences':own_constraints,'items':list(self.items.values()),
                'lastSuggestion':latest_answer,
                'budgets':self.budget_summary(trip['currency']),
                'chat':{'items':[{'messageId':str(m['id']),'userId':str(m['user_id']),'body':m['body'],
                    'tsSeconds':int(m['created_at'].timestamp()),'roomSeq':m['room_seq'],
                    'reactions':reactions.get(str(m['id']),[])} for m in messages],
                    'nextCursor':str(messages[0]['room_seq']) if has_more else None},
                'members':[{'userId':str(row['user_id']),'displayName':row['display_name'],
                            'role':row['role'],'canPin':row['can_pin'],'muted':row['muted']} for row in rows]}

    async def subscribe(self, actor=None):
        await self.load()
        async with self.lock:
            queue = asyncio.Queue(maxsize=100)
            snapshot = await self.snapshot_locked(actor)
            already_connected = actor is not None and any(a['user_id']==actor['user_id'] for a in self.connections.values())
            if actor is not None:
                self.connections[queue] = actor
                snapshot['connectedUsers'] = sorted({str(a['user_id']) for a in self.connections.values()})
                snapshot['leaderConnected'] = any(m['role']=='leader' and m['userId'] in snapshot['connectedUsers'] for m in snapshot['members'])
            queue.put_nowait(envelope("trip.snapshot", self.trip_id, snapshot))
            self.subscribers.add(queue)
            if actor is not None:
                await self.presence_locked(actor['user_id'], 'updated' if already_connected else 'joined')
            return queue

    async def unsubscribe(self, queue):
        async with self.lock:
            self.subscribers.discard(queue)
            actor = self.connections.pop(queue, None)
            if actor is not None:
                remaining = any(a['user_id']==actor['user_id'] for a in self.connections.values())
                await self.presence_locked(actor['user_id'], 'updated' if remaining else 'left')

    async def presence_locked(self, user_id, action):
        async with self.manager.engine.connect() as conn:
            state_version = (await conn.execute(text('SELECT state_version FROM trips WHERE id=:trip'),
                {'trip':self.trip_id})).scalar_one()
            rows = (await conn.execute(text('''SELECT m.user_id,m.role,m.can_pin,m.muted,u.display_name FROM memberships m
                JOIN users u ON u.id=m.user_id WHERE m.trip_id=:trip AND m.status='active' ORDER BY m.user_id'''),
                {'trip':self.trip_id})).mappings().all()
        active = {str(row['user_id']) for row in rows}
        connected = sorted({str(a['user_id']) for a in self.connections.values()} & active)
        self.publish(envelope('trip.presence.update', self.trip_id, {
            'stateVersion':state_version,
            'participantId':str(user_id),'action':action,'participantCount':len(connected),
            'connectedUsers':connected,'connectedPlanners':sum(str(r['user_id']) in connected and r['role'] in ('leader','planner') for r in rows),
            'leaderConnected':any(r['role']=='leader' and str(r['user_id']) in connected for r in rows),
            'members':[{'userId':str(r['user_id']),'displayName':r['display_name'],'role':r['role'],
                        'canPin':r['can_pin'],'muted':r['muted']} for r in rows]}))

    async def typing(self, actor, active):
        await self.load()
        uid = str(actor['user_id'])
        async with self.lock:
            async with self.manager.engine.connect() as conn:
                member = (await conn.execute(text('''SELECT 1 FROM memberships m JOIN trips t ON t.id=m.trip_id
                    JOIN auth_sessions s ON s.user_id=m.user_id WHERE m.trip_id=:trip AND m.user_id=:uid
                    AND m.status='active' AND NOT m.muted AND t.status<>'finalized'
                    AND s.id=:session AND s.revoked_at IS NULL AND s.expires_at>now()'''),
                    {'trip':self.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).first()
            if not member:
                raise RoomError('FORBIDDEN')
            now = time.monotonic()
            if active and now - self.typing_last.get(uid, 0) < 1:
                return
            if active:
                self.typing_last[uid] = now
            else:
                self.typing_last.pop(uid, None)
            prior = self.typing_tasks.pop(uid, None)
            if prior:
                prior.cancel()
            expires = datetime.now(timezone.utc) + timedelta(seconds=3)
            self.publish(envelope('trip.chat.typing.update', self.trip_id,
                {'userId':uid,'isTyping':active,'expiresAt':expires.isoformat() if active else None}))
            if active:
                async def expire():
                    try:
                        await asyncio.sleep(3)
                        async with self.lock:
                            if self.typing_tasks.get(uid) is asyncio.current_task():
                                self.typing_tasks.pop(uid, None)
                                self.typing_last.pop(uid, None)
                                self.publish(envelope('trip.chat.typing.update', self.trip_id,
                                    {'userId':uid,'isTyping':False,'expiresAt':None}))
                    except asyncio.CancelledError:
                        pass
                self.typing_tasks[uid] = asyncio.create_task(expire())

    async def send_chat(self, actor, command):
        await self.load()
        fingerprint = hashlib.sha256(json.dumps(['chat',command.model_dump(mode='json')],sort_keys=True).encode()).hexdigest()
        async with self.lock:
            if self.frozen:
                raise RoomError('PERSISTENCE_DEGRADED')
            async with self.manager.engine.connect() as conn:
                prior = (await conn.execute(text('SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:command'),
                    {'trip':self.trip_id,'command':command.commandId})).mappings().first()
                if prior:
                    if str(prior['actor_id']) != str(actor['user_id']) or prior['payload'].get('commandHash') != fingerprint:
                        raise RoomError('COMMAND_ID_REUSE')
                    previous = {key:value for key,value in prior['payload'].items() if key != 'commandHash'}
                    return {'commandId':str(command.commandId),'status':'duplicate','roomSeq':prior['payload']['roomSeq'],
                            'durable':True,'committedSeq':self.committed,'message':previous}
            next_seq, event_id, message_id = self.seq + 1, uuid4(), uuid4()
            now = datetime.now(timezone.utc)
            payload = {'messageId':str(message_id),'userId':str(actor['user_id']),'body':command.body,
                'tsSeconds':int(now.timestamp()),'roomSeq':next_seq,'roomEpoch':self.epoch,'eventId':str(event_id),
                'commandId':str(command.commandId),'correlationId':str(command.correlationId),'reactions':[], 'durable':True}
            async with self.transaction_locked() as conn:
                membership = (await conn.execute(text('''SELECT t.planning_session_id FROM trips t
                    JOIN memberships m ON m.trip_id=t.id JOIN auth_sessions s ON s.user_id=m.user_id
                    WHERE t.id=:trip AND m.user_id=:uid AND m.status='active' AND NOT m.muted
                    AND t.status<>'finalized' AND s.id=:session AND s.revoked_at IS NULL AND s.expires_at>now()'''),
                    {'trip':self.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).mappings().first()
                if not membership:
                    raise RoomError('FORBIDDEN')
                result = await conn.execute(text('''UPDATE trips SET room_seq=:next,committed_seq=:next
                    WHERE id=:trip AND committed_seq=:base RETURNING id'''),
                    {'trip':self.trip_id,'base':self.seq,'next':next_seq})
                if not result.first():
                    raise RuntimeError('durable sequence mismatch')
                await conn.execute(text('''INSERT INTO chat_messages (id,trip_id,user_id,body,created_at,room_seq)
                    VALUES (:id,:trip,:uid,:body,:created,:seq)'''),
                    {'id':message_id,'trip':self.trip_id,'uid':actor['user_id'],'body':command.body,'created':now,'seq':next_seq})
                await conn.execute(text('''INSERT INTO room_events (trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
                    VALUES (:trip,:seq,:event,:command,:session,:actor,'trip.chat.message',CAST(:payload AS jsonb))'''),
                    {'trip':self.trip_id,'seq':next_seq,'event':event_id,'command':command.commandId,
                     'session':membership['planning_session_id'],'actor':actor['user_id'],
                     'payload':json.dumps(payload | {'commandHash':fingerprint})})
            self.seq = self.committed = next_seq
            self.publish(envelope('trip.chat.message',self.trip_id,payload))
            self.audit('trip.chat.committed',command.correlationId)
            return {'commandId':str(command.commandId),'status':'committed','roomSeq':next_seq,
                    'durable':True,'committedSeq':next_seq,'message':payload}

    async def react_chat(self, actor, command):
        await self.load()
        fingerprint = hashlib.sha256(json.dumps(['reaction',command.model_dump(mode='json')],sort_keys=True).encode()).hexdigest()
        async with self.lock:
            if self.frozen:
                raise RoomError('PERSISTENCE_DEGRADED')
            async with self.manager.engine.connect() as conn:
                prior = (await conn.execute(text('SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:command'),
                    {'trip':self.trip_id,'command':command.commandId})).mappings().first()
                if prior:
                    if str(prior['actor_id']) != str(actor['user_id']) or prior['payload'].get('commandHash') != fingerprint:
                        raise RoomError('COMMAND_ID_REUSE')
                    return {'commandId':str(command.commandId),'status':'duplicate','roomSeq':prior['payload']['roomSeq'],
                            'durable':True,'committedSeq':self.committed}
            next_seq, event_id = self.seq + 1, uuid4()
            async with self.transaction_locked() as conn:
                membership = (await conn.execute(text('''SELECT t.planning_session_id FROM trips t
                    JOIN memberships m ON m.trip_id=t.id JOIN auth_sessions s ON s.user_id=m.user_id
                    WHERE t.id=:trip AND m.user_id=:uid AND m.status='active' AND NOT m.muted
                    AND t.status<>'finalized' AND s.id=:session AND s.revoked_at IS NULL AND s.expires_at>now()'''),
                    {'trip':self.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).mappings().first()
                if not membership:
                    raise RoomError('FORBIDDEN')
                exists = (await conn.execute(text('SELECT 1 FROM chat_messages WHERE trip_id=:trip AND id=:message'),
                    {'trip':self.trip_id,'message':command.messageId})).first()
                if not exists:
                    raise RoomError('NOT_FOUND')
                result = await conn.execute(text('''UPDATE trips SET room_seq=:next,committed_seq=:next
                    WHERE id=:trip AND committed_seq=:base RETURNING id'''),
                    {'trip':self.trip_id,'base':self.seq,'next':next_seq})
                if not result.first():
                    raise RuntimeError('durable sequence mismatch')
                params = {'message':command.messageId,'uid':actor['user_id'],'emoji':command.emoji}
                if command.active:
                    await conn.execute(text('INSERT INTO reactions (message_id,user_id,emoji) VALUES (:message,:uid,:emoji) ON CONFLICT DO NOTHING'),params)
                else:
                    await conn.execute(text('DELETE FROM reactions WHERE message_id=:message AND user_id=:uid AND emoji=:emoji'),params)
                groups = await reaction_groups(conn,[command.messageId])
                payload = {'messageId':str(command.messageId),'reactions':groups.get(str(command.messageId),[]),
                    'roomSeq':next_seq,'roomEpoch':self.epoch,'eventId':str(event_id),
                    'commandId':str(command.commandId),'correlationId':str(command.correlationId),'durable':True}
                await conn.execute(text('''INSERT INTO room_events (trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
                    VALUES (:trip,:seq,:event,:command,:session,:actor,'trip.chat.reaction.update',CAST(:payload AS jsonb))'''),
                    {'trip':self.trip_id,'seq':next_seq,'event':event_id,'command':command.commandId,
                     'session':membership['planning_session_id'],'actor':actor['user_id'],
                     'payload':json.dumps(payload | {'commandHash':fingerprint})})
            self.seq = self.committed = next_seq
            self.publish(envelope('trip.chat.reaction.update',self.trip_id,payload))
            self.audit('trip.chat.reaction.committed',command.correlationId)
            return {'commandId':str(command.commandId),'status':'committed','roomSeq':next_seq,
                    'durable':True,'committedSeq':next_seq}

    async def pin(self, actor, command):
        await self.load()
        data = command.model_dump(mode='json')
        fingerprint = hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        key = str(command.commandId)
        async with self.lock:
            if self.frozen:
                raise RoomError("PERSISTENCE_DEGRADED")
            if len(self.pending) >= 1000:
                raise RoomError("ROOM_BACKPRESSURE")
            prior = self.commands.get(key)
            if prior:
                if prior['hash'] != fingerprint or prior['actor'] != str(actor['user_id']):
                    raise RoomError("COMMAND_ID_REUSE")
                return prior['ack'] | {"status":"duplicate"}
            async with self.manager.engine.connect() as conn:
                previous = (await conn.execute(text("SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:command"),
                    {"trip":self.trip_id,"command":command.commandId})).mappings().first()
                if previous:
                    if str(previous['actor_id']) != str(actor['user_id']) or previous['payload'].get('commandHash') != fingerprint:
                        raise RoomError("COMMAND_ID_REUSE")
                    return {"commandId":key,"status":"duplicate","roomSeq":previous['payload']['roomSeq'],
                            "durable":True,"committedSeq":self.committed}
                trip = (await conn.execute(text("""SELECT t.dataset_id,t.start_date,t.end_date,t.timezone,t.room_locked,t.status,t.planning_session_id,
                    m.role,m.can_pin FROM trips t JOIN memberships m ON m.trip_id=t.id
                    JOIN auth_sessions s ON s.user_id=m.user_id WHERE t.id=:trip AND m.user_id=:uid AND m.status='active'
                    AND s.id=:session AND s.revoked_at IS NULL AND s.expires_at>now()"""),
                    dict(trip=self.trip_id,uid=actor['user_id'],session=actor['session_id']))).mappings().first()
                if not trip:
                    raise RoomError("FORBIDDEN")
                membership = Membership(Role(trip['role']), can_pin=trip['can_pin'])
                if trip['room_locked'] or trip['status']=='finalized' or not permitted(Capability.PIN, is_admin=False, membership=membership):
                    raise RoomError("FORBIDDEN")
                venue = (await conn.execute(text("SELECT id,name,price_per_person_minor FROM venue_metadata WHERE id=:id AND dataset_id=:dataset"),
                    {"id":command.venueId,"dataset":trip['dataset_id']})).mappings().first()
                if not venue:
                    raise RoomError("INVALID_VENUE")
                if command.startTime.utcoffset() is None or command.endTime.utcoffset() is None:
                    raise RoomError("INVALID_TIME")
                local_date = command.startTime.astimezone(ZoneInfo(trip['timezone'])).date()
                last_date = (command.endTime-timedelta(microseconds=1)).astimezone(ZoneInfo(trip['timezone'])).date()
                if command.endTime <= command.startTime or local_date != trip['start_date'] + timedelta(days=command.dayIndex) or local_date > trip['end_date'] or last_date > trip['end_date']:
                    raise RoomError("INVALID_TIME")
                attendees = command.attendeeIds
                if not attendees:
                    attendees = (await conn.execute(text("SELECT user_id FROM memberships WHERE trip_id=:trip AND status='active'"), {"trip":self.trip_id})).scalars().all()
                count = (await conn.execute(text("SELECT count(*) FROM memberships WHERE trip_id=:trip AND status='active' AND user_id=ANY(:ids)"),
                    {"trip":self.trip_id,"ids":list(attendees)})).scalar_one()
                if count != len(set(attendees)) or len(attendees) != len(set(attendees)):
                    raise RoomError("INVALID_ATTENDEES")
                if venue['price_per_person_minor'] * len(attendees) > 10**12:
                    raise RoomError("ITEM_COST_TOO_LARGE")
                current_total = sum(item['pricePerPersonMinor'] * len(item['attendeeIds']) for item in self.items.values())
                if current_total + venue['price_per_person_minor'] * len(attendees) > 10**12:
                    raise RoomError("ROOM_COST_TOO_LARGE")
            self.seq += 1
            item_id, event_id = uuid4(), uuid4()
            item = {"itemId":str(item_id),"venueId":str(venue['id']),"name":venue['name'],"dayIndex":command.dayIndex,
                    "startTime":command.startTime.astimezone(timezone.utc).isoformat(),
                    "endTime":command.endTime.astimezone(timezone.utc).isoformat(),"lifecycleStage":"drafting","positionVersion":1,
                    "pricePerPersonMinor":venue['price_per_person_minor'],"attendeeIds":sorted(str(uid) for uid in attendees)}
            self.items[str(item_id)] = item
            payload = item | {"operation":"pin","item":item,"commandId":key,"correlationId":str(command.correlationId),
                "eventId":str(event_id),"roomEpoch":self.epoch,"roomSeq":self.seq,"durable":False,
                "budgetSummary":self.budget_summary('EUR')}
            self.pending.append(dict(item=item, item_id=item_id, venue=venue['id'], dataset=trip['dataset_id'],
                actor=actor['user_id'], session=trip['planning_session_id'], attendees=attendees, price=venue['price_per_person_minor'],
                command=command.commandId, event=event_id, payload=payload | {"commandHash":fingerprint}))
            ack = {"commandId":key,"status":"applied","roomSeq":self.seq,"positionVersion":1,
                   "durable":False,"committedSeq":self.committed}
            self.commands[key] = {"hash":fingerprint,"actor":str(actor['user_id']),"ack":ack}
            self.publish(envelope('trip.board.update',self.trip_id,payload))
            self.audit('trip.board.pin.applied',command.correlationId)
            return ack

    async def change_item(self, actor, command, operation):
        await self.load()
        data = command.model_dump(mode='json')
        fingerprint = hashlib.sha256(json.dumps([operation, data], sort_keys=True).encode()).hexdigest()
        key = str(command.commandId)
        async with self.lock:
            if self.frozen:
                raise RoomError('PERSISTENCE_DEGRADED')
            if len(self.pending) >= 1000:
                raise RoomError('ROOM_BACKPRESSURE')
            prior = self.commands.get(key)
            if prior:
                if prior['hash'] != fingerprint or prior['actor'] != str(actor['user_id']):
                    raise RoomError('COMMAND_ID_REUSE')
                return prior['ack'] | {'status': 'duplicate'}
            async with self.manager.engine.connect() as conn:
                previous = (await conn.execute(text('SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:command'),
                    {'trip': self.trip_id, 'command': command.commandId})).mappings().first()
                if previous:
                    if str(previous['actor_id']) != str(actor['user_id']) or previous['payload'].get('commandHash') != fingerprint:
                        raise RoomError('COMMAND_ID_REUSE')
                    return {'commandId': key, 'status': 'duplicate', 'roomSeq': previous['payload']['roomSeq'],
                            'durable': True, 'committedSeq': self.committed}
                trip = (await conn.execute(text('''SELECT t.start_date,t.end_date,t.timezone,t.room_locked,t.status,t.planning_session_id,
                    m.role,m.can_pin FROM trips t JOIN memberships m ON m.trip_id=t.id
                    JOIN auth_sessions s ON s.user_id=m.user_id WHERE t.id=:trip AND m.user_id=:uid AND m.status='active'
                    AND s.id=:session AND s.revoked_at IS NULL AND s.expires_at>now()'''),
                    dict(trip=self.trip_id, uid=actor['user_id'], session=actor['session_id']))).mappings().first()
            if not trip or trip['room_locked'] or trip['status'] == 'finalized':
                raise RoomError('FORBIDDEN')
            if operation in ('lock', 'unlock') and trip['role']=='leader' and not any(a['user_id']==actor['user_id'] for a in self.connections.values()):
                raise RoomError('LEADER_DISCONNECTED')
            current = self.items.get(str(command.itemId))
            if current is None:
                raise RoomError('NOT_FOUND')
            if operation not in ('move', 'remove', 'lock', 'unlock'):
                raise RoomError('INVALID_COMMAND')
            if operation == 'move':
                if command.startTime.utcoffset() is None or command.endTime.utcoffset() is None:
                    raise RoomError('INVALID_TIME')
                local_date = command.startTime.astimezone(ZoneInfo(trip['timezone'])).date()
                last_date = (command.endTime-timedelta(microseconds=1)).astimezone(ZoneInfo(trip['timezone'])).date()
                if local_date != trip['start_date'] + timedelta(days=command.dayIndex) or local_date > trip['end_date'] or last_date > trip['end_date']:
                    raise RoomError('INVALID_TIME')
            try:
                item = apply_change(current, operation, command.expectedPositionVersion,
                    role=trip['role'], can_pin=trip['can_pin'], day_index=getattr(command, 'dayIndex', None),
                    start=getattr(command, 'startTime', None), end=getattr(command, 'endTime', None),
                    reason=getattr(command, 'reason', None))
            except BoardConflict as exc:
                raise RoomError('STALE_POSITION_VERSION', {'commandId': key, 'itemId': str(command.itemId),
                    'expectedPositionVersion': command.expectedPositionVersion,
                    'currentPositionVersion': exc.current_item['positionVersion'], 'currentItem': exc.current_item,
                    'roomSeq': self.seq}) from None
            except BoardForbidden:
                raise RoomError('FORBIDDEN') from None
            except BoardInvalid:
                raise RoomError('INVALID_COMMAND') from None
            if operation in ('lock', 'unlock'):
                # A lock transition is significant: persist earlier volatile commands
                # and this transition in one transaction before publishing success.
                event_id = uuid4()
                next_seq = self.seq + 1
                payload = {'operation': operation, 'itemId': str(command.itemId), 'item': item,
                    'commandId': key, 'correlationId': str(command.correlationId), 'eventId': str(event_id),
                    'roomEpoch': self.epoch, 'roomSeq': next_seq, 'durable': True}
                async with self.transaction_locked() as conn:
                    result = await conn.execute(text('''UPDATE itinerary_items SET lifecycle_stage=:stage,position_version=:next
                        WHERE trip_id=:trip AND id=:id AND position_version=:base AND removed_at IS NULL RETURNING id'''),
                        dict(stage=item['lifecycleStage'], next=item['positionVersion'], trip=self.trip_id,
                             id=command.itemId, base=current['positionVersion']))
                    if not result.first():
                        raise RuntimeError('durable item version mismatch')
                    result = await conn.execute(text('''UPDATE trips SET room_seq=:next,committed_seq=:next
                        WHERE id=:trip AND committed_seq=:base RETURNING id'''),
                        dict(next=next_seq, trip=self.trip_id, base=self.seq))
                    if not result.first():
                        raise RuntimeError('durable sequence mismatch')
                    await conn.execute(text('''INSERT INTO room_events (trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
                        VALUES (:trip,:seq,:event,:command,:session,:actor,'trip.board.update',CAST(:payload AS jsonb))'''),
                        dict(trip=self.trip_id, seq=next_seq, event=event_id, command=command.commandId,
                             session=trip['planning_session_id'], actor=actor['user_id'],
                             payload=json.dumps(payload | {'commandHash':fingerprint, 'reason':getattr(command,'reason',None)})))
                self.seq = self.committed = next_seq
                self.items[str(command.itemId)] = item
                payload['budgetSummary'] = self.budget_summary('EUR')
                self.publish(envelope('trip.board.update', self.trip_id, payload))
                self.audit('trip.board.transition.committed',command.correlationId)
                return {'commandId': key, 'status':'committed', 'roomSeq':next_seq,
                        'positionVersion':item['positionVersion'], 'durable':True, 'committedSeq':next_seq}
            self.seq += 1
            if item is None:
                del self.items[str(command.itemId)]
            else:
                self.items[str(command.itemId)] = item
            event_id = uuid4()
            payload = {'operation': operation, 'itemId': str(command.itemId), 'item': item,
                'commandId': key, 'correlationId': str(command.correlationId), 'eventId': str(event_id),
                'roomEpoch': self.epoch, 'roomSeq': self.seq, 'durable': False,
                'budgetSummary': self.budget_summary('EUR')}
            self.pending.append({'operation': operation, 'item': item, 'item_id': command.itemId,
                'base_version': current['positionVersion'], 'actor': actor['user_id'],
                'session': trip['planning_session_id'], 'command': command.commandId, 'event': event_id,
                'payload': payload | {'commandHash': fingerprint}})
            ack = {'commandId': key, 'status': 'applied', 'roomSeq': self.seq,
                   'positionVersion': current['positionVersion'] + 1, 'durable': False, 'committedSeq': self.committed}
            self.commands[key] = {'hash': fingerprint, 'actor': str(actor['user_id']), 'ack': ack}
            self.publish(envelope('trip.board.update', self.trip_id, payload))
            self.audit('trip.board.'+operation+'.applied',command.correlationId)
            return ack

    async def flush(self):
        async with self.lock:
            await self.flush_locked()

    async def persist_locked(self, conn):
        if not self.pending:
            return None
        target = self.seq
        result = await conn.execute(text("""UPDATE trips SET room_seq=:target,committed_seq=:target
            WHERE id=:trip AND committed_seq=:base RETURNING id"""),
            dict(target=target,trip=self.trip_id,base=self.committed))
        if not result.first():
            raise RuntimeError('durable sequence mismatch')
        for entry in self.pending:
            item = entry['item']
            if entry.get('operation') in ('move', 'remove'):
                if entry['operation'] == 'move':
                    result = await conn.execute(text('''UPDATE itinerary_items SET day_index=:day,starts_at=:start,ends_at=:end,
                        position_version=position_version+1 WHERE trip_id=:trip AND id=:id AND position_version=:base AND removed_at IS NULL RETURNING id'''),
                        dict(day=item['dayIndex'], start=datetime.fromisoformat(item['startTime']), end=datetime.fromisoformat(item['endTime']),
                             trip=self.trip_id, id=entry['item_id'], base=entry['base_version']))
                else:
                    result = await conn.execute(text('''UPDATE itinerary_items SET removed_at=now(),position_version=position_version+1
                        WHERE trip_id=:trip AND id=:id AND position_version=:base AND removed_at IS NULL RETURNING id'''),
                        dict(trip=self.trip_id, id=entry['item_id'], base=entry['base_version']))
                if not result.first():
                    raise RuntimeError('durable item version mismatch')
            else:
                await conn.execute(text("""INSERT INTO itinerary_items (id,trip_id,venue_id,dataset_id,day_index,
                starts_at,ends_at,lifecycle_stage,pinned_by_user_id,position_version,price_snapshot_minor,split_mode)
                VALUES (:id,:trip,:venue,:dataset,:day,:start,:end,'drafting',:actor,1,:price,'even')"""),
                dict(id=entry['item_id'],trip=self.trip_id,venue=entry['venue'],dataset=entry['dataset'],day=item['dayIndex'],
                     start=datetime.fromisoformat(item['startTime']),end=datetime.fromisoformat(item['endTime']),
                     actor=entry['actor'],price=entry['price']))
                for uid in entry['attendees']:
                    await conn.execute(text("INSERT INTO item_attendees (item_id,user_id,weight) VALUES (:item,:uid,1)"),
                                   {"item":entry['item_id'],"uid":uid})
            await conn.execute(text("""INSERT INTO room_events (trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
                VALUES (:trip,:seq,:event,:command,:session,:actor,'trip.board.update',CAST(:payload AS jsonb))"""),
                dict(trip=self.trip_id,seq=entry['payload']['roomSeq'],event=entry['event'],command=entry['command'],
                     session=entry['session'],actor=entry['actor'],payload=json.dumps(entry['payload'])))
        return target

    def fail_locked(self):
        self.frozen = True
        self.audit('trip.persistence.degraded')
        self.publish(envelope('trip.persistence.degraded',self.trip_id,{"committedSeq":self.committed,"reason":"commit failed; reconnect after recovery"}))

    def committed_locked(self, target):
        if target is None:
            return
        self.committed = target
        correlation = self.pending[-1]['payload'].get('correlationId') if self.pending else None
        self.audit('trip.persistence.committed',correlation)
        for entry in self.pending:
            self.commands.pop(str(entry['command']), None)
        self.pending.clear()
        self.publish(envelope('trip.persistence.committed',self.trip_id,{"committedSeq":target,"roomEpoch":self.epoch}))

    @asynccontextmanager
    async def transaction_locked(self):
        if self.frozen:
            raise RoomError('PERSISTENCE_DEGRADED')
        try:
            async with self.manager.engine.begin() as conn:
                target = await self.persist_locked(conn)
                yield conn
        except (HTTPException, RoomError):
            raise
        except asyncio.CancelledError:
            self.fail_locked()
            raise
        except Exception as exc:
            self.fail_locked()
            raise RoomError('PERSISTENCE_DEGRADED') from exc
        else:
            self.committed_locked(target)

    async def flush_locked(self):
        if not self.pending or self.frozen:
            return
        try:
            async with self.transaction_locked():
                pass
        except RoomError:
            pass

class RoomManager:
    def __init__(self, engine):
        self.engine = engine
        self.model_gate = asyncio.Semaphore(2)
        self.rooms = {}
        self.task = None

    def get(self, trip_id):
        return self.rooms.setdefault(trip_id, Room(self,trip_id))

    async def run(self):
        while True:
            await asyncio.sleep(.1)
            await asyncio.gather(*(room.flush() for room in list(self.rooms.values())))

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
        for room in list(self.rooms.values()):
            for task in list(room.typing_tasks.values()):
                task.cancel()
            if room.typing_tasks:
                await asyncio.gather(*room.typing_tasks.values(), return_exceptions=True)
            await room.flush()
