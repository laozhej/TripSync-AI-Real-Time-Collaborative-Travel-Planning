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
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import text
from app.auth.policy import Capability, Membership, Role, permitted


def envelope(event, trip_id, payload):
    return {"event": event, "tripId": str(trip_id), "payload": payload,
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000)}


class RoomError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Room:
    def __init__(self, manager, trip_id):
        self.manager, self.trip_id = manager, trip_id
        self.lock = asyncio.Lock()
        self.epoch = str(uuid4())
        self.seq = self.committed = 0
        self.items = {}
        self.commands = {}
        self.pending = []
        self.subscribers = set()
        self.loaded = False
        self.frozen = False

    async def load(self):
        async with self.lock:
            if self.loaded:
                return
            async with self.manager.engine.begin() as conn:
                trip = (await conn.execute(text("SELECT committed_seq FROM trips WHERE id=:id"), {"id":self.trip_id})).mappings().first()
                if trip is None:
                    raise RoomError("NOT_FOUND")
                self.seq = self.committed = trip['committed_seq']
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
        async with self.manager.engine.connect() as conn:
            if actor is not None:
                visible = (await conn.execute(text("""SELECT 1 FROM memberships m JOIN auth_sessions s ON s.user_id=m.user_id
                    WHERE m.trip_id=:trip AND m.user_id=:uid AND m.status='active' AND s.id=:session
                    AND s.revoked_at IS NULL AND s.expires_at>now()"""),
                    {'trip':self.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).first()
                if not visible:
                    raise RoomError('FORBIDDEN')
            trip = (await conn.execute(text("SELECT currency,status,room_locked,state_version,planning_session_id FROM trips WHERE id=:id"),
                                       {'id':self.trip_id})).mappings().one()
            rows = (await conn.execute(text("""SELECT m.user_id,m.role,m.can_pin,u.display_name FROM memberships m
                JOIN users u ON u.id=m.user_id WHERE m.trip_id=:trip AND m.status='active'
                ORDER BY m.joined_at,m.user_id"""), {'trip':self.trip_id})).mappings().all()
        return {'roomEpoch':self.epoch,'roomSeq':self.seq,'committedSeq':self.committed,
                'stateVersion':trip['state_version'],'sessionId':str(trip['planning_session_id']),
                'trip':{'status':trip['status'],'roomLocked':trip['room_locked']},'items':list(self.items.values()),
                'budgets':self.budget_summary(trip['currency']),
                'members':[{'userId':str(row['user_id']),'displayName':row['display_name'],
                            'role':row['role'],'canPin':row['can_pin']} for row in rows]}

    async def subscribe(self, actor=None):
        await self.load()
        async with self.lock:
            queue = asyncio.Queue(maxsize=100)
            snapshot = await self.snapshot_locked(actor)
            queue.put_nowait(envelope("trip.snapshot", self.trip_id, snapshot))
            self.subscribers.add(queue)
            return queue

    async def unsubscribe(self, queue):
        async with self.lock:
            self.subscribers.discard(queue)

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
                if command.endTime <= command.startTime or local_date != trip['start_date'] + timedelta(days=command.dayIndex) or local_date > trip['end_date']:
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
        self.publish(envelope('trip.persistence.degraded',self.trip_id,{"committedSeq":self.committed,"reason":"commit failed; reconnect after recovery"}))

    def committed_locked(self, target):
        if target is None:
            return
        self.committed = target
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
            await room.flush()
