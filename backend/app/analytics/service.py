"""Durable session finalization and ledger time boundaries."""
import hashlib
from pydantic import StrictInt,Field
from sqlalchemy import text
from app.voting.service import Command,member,prior,sync_conflicts,write_event
from app.realtime.rooms import RoomError,envelope

class Finalize(Command):
    expectedStateVersion:StrictInt=Field(ge=0)

async def finalize(room,actor,command):
    await room.load();fingerprint=hashlib.sha256(command.model_dump_json().encode()).hexdigest()
    async with room.lock:
        async with room.transaction_locked() as conn:
            m=await member(conn,room,actor)
            duplicate=await prior(conn,room,actor,command,fingerprint)
            if duplicate:return duplicate
            if m['role']!='leader' or m['room_locked'] or m['status']=='finalized':raise RoomError('FORBIDDEN')
            if not any(a['user_id']==actor['user_id'] for a in room.connections.values()):raise RoomError('LEADER_DISCONNECTED')
            version=(await conn.execute(text('SELECT state_version FROM trips WHERE id=:trip'),{'trip':room.trip_id})).scalar_one()
            if version!=command.expectedStateVersion:raise RoomError('STALE_STATE_VERSION')
            await sync_conflicts(conn,room)
            conflict=(await conn.execute(text("SELECT 1 FROM conflicts WHERE trip_id=:trip AND status='open' LIMIT 1"),{'trip':room.trip_id})).first()
            if conflict or any(v['status']=='open' for v in room.votes) or any(i['lifecycleStage']!='locked' for i in room.items.values()):raise RoomError('UNRESOLVED_PLAN')
            result=await conn.execute(text("UPDATE trips SET status='finalized',state_version=state_version+1 WHERE id=:trip AND state_version=:version RETURNING id"),{'trip':room.trip_id,'version':version})
            if not result.first():raise RuntimeError('durable settings mismatch')
            await conn.execute(text('UPDATE session_boundaries SET ended_at=now() WHERE trip_id=:trip AND ended_at IS NULL'),{'trip':room.trip_id})
            payload=await write_event(conn,room,'session.ended',{'stateVersion':version+1,'finalBudget':room.budget_summary(room.currency)},command,actor,fingerprint)
        room.seq=room.committed=payload['roomSeq'];room.publish(envelope('session.ended',room.trip_id,payload));return payload
