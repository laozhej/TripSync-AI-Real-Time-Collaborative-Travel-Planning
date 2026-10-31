"""Pure, provisional board rules. Callers serialize commands and authorize sessions."""
from datetime import timezone


class BoardConflict(Exception):
    def __init__(self, item):
        self.current_item = item.copy()
        super().__init__('STALE_POSITION_VERSION')


class BoardForbidden(Exception):
    pass


class BoardInvalid(ValueError):
    pass


def apply_change(item, operation, expected_version, *, role, can_pin, day_index=None,
                 start=None, end=None, reason=None):
    """Return a changed copy; deletion returns None. No storage or I/O occurs here."""
    if operation not in {'move', 'remove', 'lock', 'unlock'}:
        raise BoardInvalid('unknown operation')
    if role not in {'planner', 'leader'} or (role == 'planner' and not can_pin):
        raise BoardForbidden()
    if operation in {'lock', 'unlock'} and role != 'leader':
        raise BoardForbidden()
    if expected_version != item['positionVersion']:
        raise BoardConflict(item)
    stage = item['lifecycleStage']
    if (operation in {'move', 'remove', 'lock'} and stage != 'drafting') or (operation == 'unlock' and stage != 'locked'):
        raise BoardForbidden()
    result = item.copy()
    if operation == 'move':
        if (not isinstance(day_index, int) or isinstance(day_index, bool) or day_index < 0
                or start is None or end is None or start.utcoffset() is None or end.utcoffset() is None
                or start >= end):
            raise BoardInvalid('invalid day or time range')
        result.update(dayIndex=day_index, startTime=start.astimezone(timezone.utc).isoformat(),
                      endTime=end.astimezone(timezone.utc).isoformat())
    elif operation == 'remove':
        return None
    elif operation == 'lock':
        result['lifecycleStage'] = 'locked'
    else:
        if not isinstance(reason, str) or not reason.strip():
            raise BoardInvalid('unlock requires a reason')
        result['lifecycleStage'] = 'drafting'
    result['positionVersion'] += 1
    return result


def _vote_items(items, expected_versions, stage):
    if len(items)<2 or len({item['itemId'] for item in items})!=len(items):
        raise BoardInvalid('a contested slot requires distinct options')
    if set(expected_versions)!={item['itemId'] for item in items}:
        raise BoardInvalid('every option requires an expected version')
    first=items[0]
    slot=(first['dayIndex'],first['startTime'],first['endTime'],set(first.get('attendeeIds',[])))
    if len({item['venueId'] for item in items})!=len(items):
        raise BoardInvalid('candidate venues must be distinct')
    for item in items:
        if item['positionVersion']!=expected_versions[item['itemId']]: raise BoardConflict(item)
        if item['lifecycleStage']!=stage: raise BoardForbidden()
        if (item['dayIndex'],item['startTime'],item['endTime'],set(item.get('attendeeIds',[])))!=slot:
            raise BoardInvalid('vote options must share one slot and attendee set')


def begin_voting(items, expected_versions):
    """Internal lifecycle primitive for TASK-016's authorized election service.

    Not a public command: eligibility, deadlines and atomic durable vote records
    belong to the later voting service. Never set Voting from a client request.
    """
    _vote_items(items,expected_versions,'drafting')
    return [item | {'lifecycleStage':'voting','positionVersion':item['positionVersion']+1} for item in items]


def resolve_voting(items, expected_versions, winner_item_id=None):
    """Return versioned active/archive projections for one durable resolution.

    A cancelled (zero-ballot) election returns all options to active Drafting.
    The future election service must persist this projection with its result.
    """
    _vote_items(items,expected_versions,'voting')
    if winner_item_id is not None and winner_item_id not in expected_versions:
        raise BoardInvalid('winner is not an option')
    active,archived=[],[]
    for item in items:
        winner=item['itemId']==winner_item_id
        updated=item | {'positionVersion':item['positionVersion']+1,'lifecycleStage':'locked' if winner else 'drafting'}
        (active if winner_item_id is None or winner else archived).append(updated)
    return {'activeItems':active,'archivedItems':archived}
