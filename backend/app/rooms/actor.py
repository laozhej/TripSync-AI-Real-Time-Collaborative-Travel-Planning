"""In-memory ordering primitive; not yet wired to routes or persistence."""
import asyncio
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


class Forbidden(Exception):
    pass


class InvalidPin(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    itemId: str
    venueId: str
    dayIndex: int
    startTime: str
    endTime: str
    lifecycleStage: str = "drafting"
    positionVersion: int = 1


class RoomActor:
    """Serialize snapshot and pin operations at one room sequence boundary.

    This primitive is not a complete gateway: authorization must be re-read by
    the caller and persistence/epoch recovery is required before it is exposed.
    """
    def __init__(self, trip_id: UUID):
        self.trip_id = str(trip_id)
        self.epoch = str(uuid4())
        self.seq = 0
        self.committed_seq = 0
        self.items: dict[str, Item] = {}
        self._lock = asyncio.Lock()
        self._commands = {}

    async def pin(self, *, actor_id: UUID, can_pin: bool, command_id: UUID,
                  venue_id: UUID, day_index: int, start: datetime, end: datetime):
        if not can_pin:
            raise Forbidden()
        if day_index < 0 or start.utcoffset() is None or end.utcoffset() is None or start >= end:
            raise InvalidPin("invalid day or time range")
        body = (str(actor_id), str(venue_id), day_index, start, end)
        async with self._lock:
            key = str(command_id)
            if key in self._commands:
                previous_body, previous_result = self._commands[key]
                if previous_body != body:
                    raise InvalidPin("command ID reused for a different operation")
                return deepcopy(previous_result)
            item = Item(str(uuid4()), str(venue_id), day_index,
                        start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat())
            self.seq += 1
            self.items[item.itemId] = item
            result = {"item": asdict(item), "roomEpoch": self.epoch, "roomSeq": self.seq,
                      "committedSeq": self.committed_seq, "durable": False}
            self._commands[key] = (body, result)
            return deepcopy(result)

    async def snapshot(self):
        async with self._lock:
            return {"tripId": self.trip_id, "roomEpoch": self.epoch, "roomSeq": self.seq,
                    "committedSeq": self.committed_seq, "items": [asdict(item) for item in self.items.values()]}
