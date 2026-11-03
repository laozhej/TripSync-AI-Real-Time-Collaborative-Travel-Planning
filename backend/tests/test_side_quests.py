"""Destination discovery and persistence of user-entered board activities."""
import asyncio
from uuid import UUID, uuid4

import pytest

from test_moderation_integration import DB, client, group, receive_event


@pytest.mark.skipif(not DB, reason='requires disposable PostgreSQL')
@pytest.mark.parametrize('group', [{'destination': 'Goa, India', 'currency': 'INR'}], indirect=True)
def test_goa_catalog_and_personal_activity(client, group):
    trip = group['trip']
    endpoint = '/api/v1/destinations'
    headers = group['headers'](0)
    assert client.get(endpoint).status_code == 401
    destinations = client.get(endpoint, headers=headers).json()['destinations']
    assert {'destination': 'Goa, India', 'currency': 'INR', 'timezone': 'Asia/Kolkata'} in destinations
    assert client.get('/api/v1/trips/' + trip, headers=headers).json()['destination'] == 'Goa, India'

    def socket(member):
        return client.websocket_connect('/ws/v1/trips/' + trip,
            headers=group['headers'](member) | {'origin': 'http://testserver'})

    command = {'event': 'trip.board.pin', 'payload': {
        'commandId': str(uuid4()), 'correlationId': str(uuid4()),
        'personalActivity': {'name': 'Visit a friend', 'pricePerPersonMinor': 0},
        'dayIndex': 0, 'startTime': '2026-11-10T12:00:00+05:30',
        'endTime': '2026-11-10T13:00:00+05:30',
    }}
    with socket(2) as viewer:
        receive_event(viewer)
        viewer.send_json(command)
        assert receive_event(viewer)['payload']['code'] == 'FORBIDDEN'

    with socket(0) as leader, socket(1) as planner:
        receive_event(leader)
        receive_event(planner)
        planner.send_json(command)
        item = receive_event(leader)['payload']['item']
        assert item['venueId'] is None
        assert item['name'] == 'Visit a friend'
        assert item['pricePerPersonMinor'] == 0
        assert receive_event(planner)['payload']['item'] == item
        while True:
            message = receive_event(planner)
            if message['event'] == 'trip.persistence.committed':
                break

    rows = asyncio.run(group['sql'](
        'SELECT personal_name, venue_id, price_snapshot_minor FROM itinerary_items WHERE id=:id',
        {'id': UUID(item['itemId'])}))
    assert dict(rows[0]) == {'personal_name': 'Visit a friend', 'venue_id': None, 'price_snapshot_minor': 0}

