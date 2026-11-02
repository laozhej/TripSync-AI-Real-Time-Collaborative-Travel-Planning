"""Consolidated later-feature identity/isolation and transport rejection checks."""
from uuid import uuid4
import pytest
from starlette.websockets import WebSocketDisconnect
from test_auth_integration import DB, app, client, receive_event
from test_moderation_integration import group

pytestmark = pytest.mark.skipif(not DB, reason='requires disposable PostgreSQL')


def test_later_reads_and_mutations_do_not_allow_outsider_admin(client, group):
    root = '/api/v1/trips/' + group['trip']
    h = group['headers']
    for route in ('planning', 'budgets', 'conflicts', 'analytics', 'recommendations'):
        for role in (0, 1, 2):
            assert client.get(root+'/'+route, headers=h(role)).status_code == 200
        assert client.get(root+'/'+route, headers=h(3)).status_code == 404
    for role in (0, 1):
        assert client.get('/api/v1/admin/datasets', headers=h(role)).status_code == 403
        assert client.post('/api/v1/admin/datasets', headers=h(role), json={}).status_code == 403
    # Viewer with Admin account privileges still has no Planner/Leader privilege.
    for path, body in (
        ('votes', {'expectedVersions': {str(uuid4()): 1, str(uuid4()): 1}, 'durationSeconds': 10}),
        ('finalize', {'expectedStateVersion': 1}),
    ):
        command = {'commandId': str(uuid4()), 'correlationId': str(uuid4()), **body}
        assert client.post(root+'/'+path, headers=h(3), json=command).status_code == 404
        assert client.post(root+'/'+path, headers=h(2), json=command).status_code in (403, 404, 409)
    before = client.get(root+'/planning', headers=h(1)).json()['roomSeq']
    for body in ({'body': 'x'*2001}, {'body': 'hello', 'userId': group['ids'][0]}, {'body': '\u0000'}):
        assert client.post(root+'/chat', headers=h(1), json=body).status_code == 422
    assert client.post(root+'/interactions', headers=h(1), json={
        'venueId': str(uuid4()), 'kind': 'like', 'eventId': str(uuid4())}).status_code == 422
    assert client.get(root+'/planning', headers=h(1)).json()['roomSeq'] == before


def test_binary_oversized_and_malformed_socket_input(client, group):
    url = '/ws/v1/trips/'+group['trip']
    headers = group['headers'](1) | {'origin': 'http://testserver'}
    for binary, size, code in ((True, 1, 1003), (False, 65537, 1009)):
        with client.websocket_connect(url, headers=headers) as peer:
            receive_event(peer)
            if binary:
                peer.send_bytes(b'x'*size)
            else:
                peer.send_text('x'*size)
            with pytest.raises(WebSocketDisconnect) as exc:
                while True:
                    peer.receive_json()
            assert exc.value.code == code
    with client.websocket_connect(url, headers=headers) as peer:
        receive_event(peer)
        for body in ('null', '[]', '{', '{"event": "unknown", "payload": {}}'):
            peer.send_text(body)
            assert receive_event(peer)['payload']['code'] == 'INVALID_COMMAND'
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(url, headers=group['headers'](0) | {'origin': 'https://evil.invalid'}):
            pass
