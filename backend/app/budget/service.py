"""Versioned attendee and split edits, frozen during elections."""
import hashlib
from uuid import UUID
from typing import Literal,Annotated
from pydantic import Field,StrictInt,model_validator
from sqlalchemy import text
from app.voting.service import Command,member,prior,write_event,sync_conflicts
from app.budget.engine import item_allocations,summarize
from app.realtime.rooms import RoomError,envelope

class SplitUpdate(Command):
    itemId:UUID
    expectedPositionVersion:StrictInt=Field(ge=1)
    attendeeIds:list[UUID]=Field(min_length=1,max_length=50)
    splitMode:Literal['even','weighted']='even'
    weights:dict[UUID,Annotated[StrictInt,Field(ge=0,le=2**31-1)]]=Field(default_factory=dict,max_length=50)
    @model_validator(mode='after')
    def valid_weights(self):
        if len(set(self.attendeeIds))!=len(self.attendeeIds):raise ValueError('duplicate attendee')
        if self.splitMode=='weighted' and (set(self.weights)!=set(self.attendeeIds) or sum(self.weights.values())<=0):raise ValueError('invalid weights')
        if self.splitMode=='even' and self.weights:raise ValueError('even split has no weights')
        return self

async def update_split(room,actor,command):
    await room.load();fingerprint=hashlib.sha256(command.model_dump_json().encode()).hexdigest()
    async with room.lock:
        async with room.transaction_locked() as conn:
            m=await member(conn,room,actor)
            duplicate=await prior(conn,room,actor,command,fingerprint)
            if duplicate:return duplicate
            if m['role'] not in ('planner','leader') or (m['role']=='planner' and not m['can_pin']) or m['room_locked'] or m['status']=='finalized':raise RoomError('FORBIDDEN')
            item=room.items.get(str(command.itemId))
            if not item:raise RoomError('NOT_FOUND')
            if item['positionVersion']!=command.expectedPositionVersion:raise RoomError('STALE_POSITION_VERSION',{'commandId':str(command.commandId),'itemId':item['itemId'],'expectedPositionVersion':command.expectedPositionVersion,'currentPositionVersion':item['positionVersion'],'currentItem':item,'roomSeq':room.seq})
            if item['lifecycleStage']!='drafting':raise RoomError('FORBIDDEN')
            count=(await conn.execute(text("SELECT count(*) FROM memberships WHERE trip_id=:trip AND user_id=ANY(:users) AND status='active'"),{'trip':room.trip_id,'users':command.attendeeIds})).scalar_one()
            if count!=len(command.attendeeIds):raise RoomError('INVALID_ATTENDEES')
            weights={str(uid):1 for uid in command.attendeeIds} if command.splitMode=='even' else {str(uid):w for uid,w in command.weights.items()}
            changed=item|{'attendeeIds':sorted(weights),'weights':weights,'splitMode':command.splitMode,'positionVersion':item['positionVersion']+1}
            try:item_allocations(changed)
            except ValueError:raise RoomError('INVALID_WEIGHTS') from None
            result=await conn.execute(text('UPDATE itinerary_items SET split_mode=:mode,position_version=:next WHERE id=:id AND trip_id=:trip AND position_version=:base RETURNING id'),{'mode':command.splitMode,'next':changed['positionVersion'],'id':command.itemId,'trip':room.trip_id,'base':item['positionVersion']})
            if not result.first():raise RuntimeError('durable item mismatch')
            await conn.execute(text('DELETE FROM item_attendees WHERE item_id=:id'),{'id':command.itemId})
            for uid,w in weights.items():await conn.execute(text('INSERT INTO item_attendees VALUES(:item,:uid,:w)'),{'item':command.itemId,'uid':UUID(uid),'w':w})
            items=room.items|{changed['itemId']:changed}
            await sync_conflicts(conn,room,items,seq=room.seq+1)
            payload=await write_event(conn,room,'trip.board.update',{'operation':'split','itemId':changed['itemId'],'item':changed,'budgetSummary':summarize(items.values(),room.currency,room.votes)},command,actor,fingerprint)
        room.items=items;room.seq=room.committed=payload['roomSeq'];room.publish(envelope('trip.board.update',room.trip_id,payload));return payload
