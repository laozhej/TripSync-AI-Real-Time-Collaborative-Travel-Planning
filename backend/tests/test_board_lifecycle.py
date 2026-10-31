from datetime import datetime, timezone

import pytest
from app.board.lifecycle import BoardConflict, BoardForbidden, BoardInvalid, apply_change


@pytest.fixture
def item():
    return {'itemId': 'item-1', 'positionVersion': 4, 'lifecycleStage': 'drafting',
            'dayIndex': 0, 'startTime': '2026-11-10T12:00:00+00:00',
            'endTime': '2026-11-10T13:00:00+00:00'}


def test_same_version_move_rejects_stale_and_supplies_current_item(item):
    moved = apply_change(item, 'move', 4, role='planner', can_pin=True,
                         day_index=1, start=datetime(2026, 11, 11, 12, tzinfo=timezone.utc),
                         end=datetime(2026, 11, 11, 13, tzinfo=timezone.utc))
    assert moved['positionVersion'] == 5 and moved['dayIndex'] == 1
    with pytest.raises(BoardConflict) as conflict:
        apply_change(moved, 'remove', 4, role='planner', can_pin=True)
    assert conflict.value.current_item == moved
    assert item['positionVersion'] == 4


@pytest.mark.parametrize('role,can_pin', [('viewer', False), ('planner', False)])
def test_insufficient_membership_cannot_move_or_remove(item, role, can_pin):
    with pytest.raises(BoardForbidden):
        apply_change(item, 'remove', 4, role=role, can_pin=can_pin)


def test_lock_and_override_require_leader_and_explicit_reason(item):
    with pytest.raises(BoardForbidden):
        apply_change(item, 'lock', 4, role='planner', can_pin=True)
    locked = apply_change(item, 'lock', 4, role='leader', can_pin=True)
    with pytest.raises(BoardForbidden):
        apply_change(locked, 'remove', 5, role='planner', can_pin=True)
    with pytest.raises(BoardInvalid):
        apply_change(locked, 'unlock', 5, role='leader', can_pin=True, reason='  ')
    unlocked = apply_change(locked, 'unlock', 5, role='leader', can_pin=True, reason='Change plan')
    assert unlocked['lifecycleStage'] == 'drafting' and unlocked['positionVersion'] == 6


def test_voting_items_are_not_directly_editable(item):
    item['lifecycleStage'] = 'voting'
    for operation in ('move', 'remove', 'lock', 'unlock'):
        with pytest.raises(BoardForbidden):
            apply_change(item, operation, 4, role='leader', can_pin=True)


@pytest.mark.parametrize('start,end,day', [
    (datetime(2026, 11, 10, 12), datetime(2026, 11, 10, 13), 0),
    (datetime(2026, 11, 10, 12, tzinfo=timezone.utc), datetime(2026, 11, 10, 12, tzinfo=timezone.utc), 0),
    (datetime(2026, 11, 10, 12, tzinfo=timezone.utc), datetime(2026, 11, 10, 13, tzinfo=timezone.utc), -1),
])
def test_invalid_moves_are_rejected(item, start, end, day):
    with pytest.raises(BoardInvalid):
        apply_change(item, 'move', 4, role='leader', can_pin=True, day_index=day, start=start, end=end)


def test_voting_lifecycle_freezes_options_then_applies_winner_or_cancels(item):
    from app.board.lifecycle import begin_voting,resolve_voting
    items=[item|{'venueId':'venue-a'},item|{'itemId':'item-2','venueId':'venue-b'}]
    versions={entry['itemId']:4 for entry in items}
    voting=begin_voting(items,versions)
    assert all(entry['lifecycleStage']=='voting' and entry['positionVersion']==5 for entry in voting)
    assert item['lifecycleStage']=='drafting' and item['positionVersion']==4
    for entry in voting:
        with pytest.raises(BoardForbidden):apply_change(entry,'remove',5,role='leader',can_pin=True)
    expected={entry['itemId']:5 for entry in voting}
    winner=resolve_voting(voting,expected,'item-1')
    assert winner['activeItems'][0]['lifecycleStage']=='locked' and winner['activeItems'][0]['positionVersion']==6
    assert winner['archivedItems'][0]['itemId']=='item-2' and winner['archivedItems'][0]['lifecycleStage']=='drafting'
    cancelled=resolve_voting(voting,expected)
    assert len(cancelled['activeItems'])==2 and cancelled['archivedItems']==[]
    assert all(entry['lifecycleStage']=='drafting' for entry in cancelled['activeItems'])
    with pytest.raises(BoardConflict):begin_voting(items,versions|{'item-1':3})
    with pytest.raises(BoardInvalid):resolve_voting(voting,expected,'unknown')


def test_voting_options_require_common_slot_and_distinct_venues(item):
    from app.board.lifecycle import begin_voting
    items=[item|{'venueId':'a'},item|{'itemId':'item-2','venueId':'a'}]
    versions={entry['itemId']:4 for entry in items}
    with pytest.raises(BoardInvalid):begin_voting(items,versions)
    items[1]['venueId']='b';items[1]['dayIndex']=1
    with pytest.raises(BoardInvalid):begin_voting(items,versions)
