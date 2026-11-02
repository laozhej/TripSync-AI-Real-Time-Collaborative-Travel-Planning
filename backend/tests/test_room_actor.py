import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest
from app.rooms.actor import Forbidden, InvalidPin, RoomActor


@pytest.mark.asyncio
async def test_concurrent_pins_are_ordered_and_snapshot_consistent():
    room = RoomActor(uuid4())
    now = datetime.now(timezone.utc)
    async def pin():
        return await room.pin(actor_id=uuid4(), can_pin=True, command_id=uuid4(), venue_id=uuid4(),
                              day_index=0, start=now, end=now + timedelta(hours=1))
    results = await asyncio.gather(*(pin() for _ in range(10)))
    snapshot = await room.snapshot()
    assert sorted(result["roomSeq"] for result in results) == list(range(1, 11))
    assert snapshot["roomSeq"] == len(snapshot["items"]) == 10
    assert snapshot["committedSeq"] == 0
    assert all(not result["durable"] for result in results)


@pytest.mark.asyncio
async def test_denied_and_reused_commands_do_not_mutate_room():
    room = RoomActor(uuid4())
    now = datetime.now(timezone.utc)
    args = dict(actor_id=uuid4(), can_pin=True, command_id=uuid4(), venue_id=uuid4(), day_index=0,
                start=now, end=now + timedelta(hours=1))
    with pytest.raises(Forbidden):
        await room.pin(**(args | {"can_pin": False}))
    first = await room.pin(**args)
    assert await room.pin(**args) == first
    with pytest.raises(InvalidPin):
        await room.pin(**(args | {"venue_id": uuid4()}))
    assert (await room.snapshot())["roomSeq"] == 1


@pytest.mark.asyncio
async def test_failed_persistence_freezes_room_and_keeps_pending():
    from app.realtime.rooms import Room
    class OfflineEngine:
        def begin(self):
            raise ConnectionError('database unavailable')
    class Manager:
        engine = OfflineEngine()
    room = Room(Manager(), uuid4())
    room.loaded = True
    room.seq = 1
    room.pending.append({'command':uuid4()})
    queue = asyncio.Queue(maxsize=100)
    room.subscribers.add(queue)
    await room.flush()
    assert room.frozen and room.committed == 0 and len(room.pending) == 1
    assert (await queue.get())['event'] == 'trip.persistence.degraded'


def test_room_audit_contains_only_safe_operational_fields(caplog):
    import json
    from app.realtime.rooms import Room,logger
    room=Room(None,uuid4());correlation=uuid4()
    logger.addHandler(caplog.handler)
    try: room.audit('trip.persistence.degraded',correlation)
    finally: logger.removeHandler(caplog.handler)
    record=json.loads(caplog.records[-1].getMessage())
    assert set(record)=={'event','tripId','sessionId','roomEpoch','roomSeq','committedSeq','correlationId','ts'}
    assert record['tripId']==str(room.trip_id) and record['correlationId']==str(correlation)
    assert record['committedSeq']==0


def test_slow_subscriber_is_disconnected_without_blocking_other_clients():
    from app.realtime.rooms import Room
    room = Room(None, uuid4())
    slow, healthy = asyncio.Queue(maxsize=1), asyncio.Queue(maxsize=4)
    slow.put_nowait({'old': 'frame'})
    room.subscribers.update((slow, healthy))
    event = {'event': 'trip.board.update'}
    room.publish(event)
    assert healthy.get_nowait() == event
    assert slow.get_nowait() is None
    assert slow not in room.subscribers and healthy in room.subscribers
