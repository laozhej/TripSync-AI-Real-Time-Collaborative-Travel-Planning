"""Opt-in integration checks against an explicitly designated disposable database."""
import asyncio
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.main import app
from app.api.auth import _attempts
from app.realtime.rooms import RoomManager

DB = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB, reason="set TEST_DATABASE_URL to a disposable migrated database")


@pytest.fixture
def client(monkeypatch):
    _attempts.clear()
    monkeypatch.setenv("DATABASE_URL", DB)
    monkeypatch.setenv("JWT_SIGNING_KEY", "integration-test-key-" + "x" * 40)
    monkeypatch.setenv("JWT_ISSUER", "test")
    monkeypatch.setenv("JWT_AUDIENCE", "test-client")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://testserver")
    with TestClient(app) as c:
        yield c


async def cleanup(user_id):
    engine = create_async_engine(DB)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM users WHERE id=:id"), {"id": UUID(user_id)})
    finally:
        await engine.dispose()


def test_registration_login_refresh_reuse_and_logout(client):
    assert client.get('/api/v1/health/ready').status_code == 200
    assert client.get('/api/v1/health/gateway').status_code == 200
    async def search_index_works():
        engine = create_async_engine(DB)
        try:
            async with engine.connect() as conn:
                matches = (await conn.execute(text("SELECT count(*) FROM venue_metadata WHERE search_vector @@ plainto_tsquery('english','synthetic')"))).scalar_one()
                index = (await conn.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='ix_venue_search_vector'"))).scalar_one()
                return matches, index
        finally:
            await engine.dispose()
    matches, index = asyncio.run(search_index_works())
    assert matches > 0 and 'USING gin' in index
    email = f"test-{secrets.token_hex(12)}@example.invalid"
    password = "test password of sufficient length"
    assert client.post('/api/v1/auth/register', headers={'origin':'https://evil.invalid'}, json={"email":email, "password":password, "displayName":"Test"}).status_code == 403
    register = client.post('/api/v1/auth/register', json={"email":email, "password":password, "displayName":"Test"})
    assert register.status_code == 201, register.text
    user_id = register.json()['userId']
    try:
        assert client.post('/api/v1/auth/register', json={"email":email, "password":password, "displayName":"Test", "isAdmin":True}).status_code == 422
        assert client.post('/api/v1/auth/login', json={"email":email, "password":"incorrect password"}).status_code == 401
        assert client.post('/api/v1/auth/login', headers={'origin':'https://evil.invalid'}, json={"email":email, "password":password}).status_code == 403
        login = client.post('/api/v1/auth/login', json={"email":email, "password":password})
        assert login.status_code == 200, login.text
        access = login.json()['accessToken']
        headers = {"authorization":"Bearer " + access}
        url = '/api/v1/destinations/Lisbon%2C%20Portugal/venues'
        catalog = client.get(url, headers=headers, params={"limit":2})
        assert catalog.status_code == 200, catalog.text
        assert len(catalog.json()['venues']) == 2
        assert catalog.json()['nextCursor']
        second = client.get(url, headers=headers, params={"limit":2, "cursor":catalog.json()['nextCursor']})
        assert second.status_code == 200
        assert second.json()['venues'][0]['venueId'] != catalog.json()['venues'][0]['venueId']
        assert client.get(url, headers=headers, params={"radiusKm":2}).status_code == 422
        assert client.get(url, headers=headers, params={"near":"not-a-location"}).status_code == 422
        nearby = client.get(url, headers=headers, params={"near":"38.7139,-9.1394", "radiusKm":2})
        assert nearby.status_code == 200
        source_ids = {venue['sourceId'] for venue in nearby.json()['venues']}
        assert 'venue:v_1@1' in source_ids and 'venue:v_6@1' not in source_ids
        from app.api.catalog import distance_km
        boundary = distance_km(38.7139, -9.1394, 38.7140, -9.1390)
        at_boundary = client.get(url, headers=headers, params={'near':'38.7139,-9.1394','radiusKm':boundary})
        outside_boundary = client.get(url, headers=headers, params={'near':'38.7139,-9.1394','radiusKm':boundary-0.0001})
        assert 'venue:v_2@1' in {v['sourceId'] for v in at_boundary.json()['venues']}
        assert 'venue:v_2@1' not in {v['sourceId'] for v in outside_boundary.json()['venues']}
        old_refresh = client.cookies.get('tripsync_refresh')
        csrf = client.cookies.get('tripsync_csrf')
        assert client.post('/api/v1/auth/refresh', headers={"origin":"http://evil.invalid", "x-csrf-token":csrf}).status_code == 403
        rotation = client.post('/api/v1/auth/refresh', headers={"origin":"http://testserver", "x-csrf-token":csrf})
        assert rotation.status_code == 200, rotation.text
        assert client.cookies.get('tripsync_refresh') != old_refresh
        rotated_access = rotation.json()['accessToken']
        csrf = client.cookies.get('tripsync_csrf')
        client.cookies.set('tripsync_refresh', old_refresh, domain='testserver.local', path='/api/v1/auth')
        reuse = client.post('/api/v1/auth/refresh', headers={"origin":"http://testserver", "x-csrf-token":csrf})
        assert reuse.status_code == 401
        denied = client.post('/api/v1/auth/logout', headers={"origin":"http://testserver", "x-csrf-token":csrf, "authorization":"Bearer " + rotated_access})
        assert denied.status_code == 401
    finally:
        asyncio.run(cleanup(user_id))


def test_two_users_create_and_join_with_idempotency(client, monkeypatch):
    from uuid import uuid4
    from datetime import datetime, timezone, timedelta
    password = 'a strong test password'
    ids, emails = [], []
    trip_id = None
    foreign_dataset, foreign_venue = uuid4(), uuid4()
    async def cleanup_trip():
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                if trip_id:
                    await conn.execute(text('DELETE FROM item_attendees WHERE item_id IN (SELECT id FROM itinerary_items WHERE trip_id=:id)'), {'id': UUID(trip_id)})
                    await conn.execute(text('DELETE FROM room_events WHERE trip_id=:id'), {'id': UUID(trip_id)})
                    await conn.execute(text('DELETE FROM itinerary_items WHERE trip_id=:id'), {'id': UUID(trip_id)})
                    for table in ('invites', 'memberships'):
                        await conn.execute(text(f'DELETE FROM {table} WHERE trip_id=:id'), {'id': UUID(trip_id)})
                    await conn.execute(text('DELETE FROM trips WHERE id=:id'), {'id': UUID(trip_id)})
                await conn.execute(text('DELETE FROM venue_metadata WHERE dataset_id=:id'), {'id':foreign_dataset})
                await conn.execute(text('DELETE FROM datasets WHERE id=:id'), {'id':foreign_dataset})
                for uid in ids:
                    await conn.execute(text('DELETE FROM http_idempotency WHERE user_id=:id'), {'id':UUID(uid)})
                    await conn.execute(text('DELETE FROM users WHERE id=:id'), {'id':UUID(uid)})
        finally:
            await engine.dispose()
    async def set_role(role):
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('UPDATE memberships SET role=:role WHERE trip_id=:trip AND user_id=:uid'),
                                   {'role':role, 'trip':UUID(trip_id), 'uid':UUID(ids[1])})
        finally:
            await engine.dispose()
    async def set_admin(user_id):
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('UPDATE users SET is_admin=true WHERE id=:id'), {'id':UUID(user_id)})
        finally:
            await engine.dispose()
    async def set_status(status):
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                await conn.execute(text('UPDATE memberships SET status=:status WHERE trip_id=:trip AND user_id=:uid'),
                                   {'status':status, 'trip':UUID(trip_id), 'uid':UUID(ids[1])})
        finally:
            await engine.dispose()
    async def expire_invite(invite_id):
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("UPDATE invites SET expires_at=now()-interval '1 second' WHERE id=:id"),
                                   {'id':UUID(invite_id)})
        finally:
            await engine.dispose()
    async def add_foreign_venue():
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("""INSERT INTO datasets (id,destination,version,timezone,currency,status,provenance,checksum)
                    SELECT :id,:destination,1,timezone,currency,'staging',provenance,:checksum FROM datasets
                    WHERE destination='Lisbon, Portugal' AND status='active'"""),
                    {'id':foreign_dataset, 'destination':'foreign-test-'+foreign_dataset.hex, 'checksum':foreign_dataset.hex})
                await conn.execute(text("""INSERT INTO venue_metadata (id,dataset_id,source_id,name,category,price_per_person_minor,
                    currency,latitude,longitude,rating,description,hours) SELECT :venue,:dataset,'foreign',name,category,
                    price_per_person_minor,currency,latitude,longitude,rating,description,hours FROM venue_metadata LIMIT 1"""),
                    {'venue':foreign_venue, 'dataset':foreign_dataset})
        finally:
            await engine.dispose()
    try:
        tokens = []
        for _ in range(3):
            email = f'test-{secrets.token_hex(12)}@example.invalid'
            emails.append(email)
            r = client.post('/api/v1/auth/register', json={'email':email,'password':password,'displayName':'Traveler'})
            assert r.status_code == 201, r.text
            ids.append(r.json()['userId'])
            login = client.post('/api/v1/auth/login', json={'email':email, 'password':password})
            assert login.status_code == 200, login.text
            tokens.append(login.json()['accessToken'])
        key = str(uuid4())
        headers = {'authorization':'Bearer ' + tokens[0], 'Idempotency-Key':key}
        body = {'destination':'Lisbon, Portugal', 'startDate':'2026-11-10', 'endDate':'2026-11-14',
                'totalBudget':'1200.00', 'currency':'EUR', 'maxParticipants':3}
        created = client.post('/api/v1/trips', json=body, headers=headers)
        assert created.status_code == 201, created.text
        trip_id = created.json()['tripId']
        expired = jwt.encode({'sub':ids[0], 'sid':str(uuid4()), 'iss':'test', 'aud':'test-client',
                              'iat':datetime.now(timezone.utc)-timedelta(minutes=2),
                              'nbf':datetime.now(timezone.utc)-timedelta(minutes=2),
                              'exp':datetime.now(timezone.utc)-timedelta(minutes=1)},
                             'integration-test-key-'+'x'*40, algorithm='HS256')
        assert client.get('/api/v1/trips/'+trip_id, headers={'authorization':'Bearer '+expired}).status_code == 401
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws/v1/trips/'+trip_id, headers={'authorization':'Bearer '+expired, 'origin':'http://testserver'}):
                pass
        assert client.get('/api/v1/trips/' + trip_id, headers={'authorization':'Bearer ' + tokens[1]}).status_code == 404
        from app.cli import create_admin
        monkeypatch.setattr('builtins.input', lambda _: emails[2])
        asyncio.run(create_admin())
        assert client.get('/api/v1/trips/' + trip_id, headers={'authorization':'Bearer ' + tokens[2]}).status_code == 404
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect('/ws/v1/trips/'+trip_id, headers={'authorization':'Bearer '+tokens[2], 'origin':'http://testserver'}):
                pass
        assert client.post('/api/v1/trips', json=body, headers=headers).json() == created.json()
        assert client.post('/api/v1/trips', json=body | {'totalBudget':'999.00'}, headers=headers).status_code == 409
        join_headers = {'authorization':'Bearer ' + tokens[1], 'Idempotency-Key':str(uuid4())}
        joined = client.post('/api/v1/trips/join', json={'inviteCode':created.json()['inviteCode']}, headers=join_headers)
        assert joined.status_code == 200, joined.text
        assert joined.json() == {'tripId':trip_id, 'role':'planner'}
        assert client.post('/api/v1/trips/join', json={'inviteCode':created.json()['inviteCode']}, headers=join_headers).json() == joined.json()
        trip = client.get('/api/v1/trips/' + trip_id, headers={'authorization':'Bearer ' + tokens[1]})
        assert trip.status_code == 200 and trip.json()['role'] == 'planner'
        assert len(trip.json()['members']) == 2 and trip.json()['status'] == 'live'
        invite_body = {'role':'viewer', 'maxUses':1, 'expiresAt':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        invite_path = '/api/v1/trips/' + trip_id + '/invites'
        assert client.post(invite_path, headers={'authorization':'Bearer '+tokens[1]}, json=invite_body).status_code == 403
        assert client.post(invite_path, headers={'authorization':'Bearer '+tokens[2]}, json=invite_body).status_code == 404
        issued = client.post(invite_path, headers={'authorization':'Bearer '+tokens[0]}, json=invite_body)
        assert issued.status_code == 201 and issued.json()['role'] == 'viewer'
        revoked = client.delete(invite_path+'/'+issued.json()['inviteId'], headers={'authorization':'Bearer '+tokens[0]})
        assert revoked.status_code == 204
        denied = client.post('/api/v1/trips/join', headers={'authorization':'Bearer '+tokens[2], 'Idempotency-Key':str(uuid4())},
                             json={'inviteCode':issued.json()['inviteCode']})
        assert denied.status_code == 403
        expired_invite = client.post(invite_path, headers={'authorization':'Bearer '+tokens[0]}, json=invite_body)
        asyncio.run(expire_invite(expired_invite.json()['inviteId']))
        denied_expired = client.post('/api/v1/trips/join', headers={'authorization':'Bearer '+tokens[2], 'Idempotency-Key':str(uuid4())},
                                     json={'inviteCode':expired_invite.json()['inviteCode']})
        assert denied_expired.status_code == 403
        viewer_invite = client.post(invite_path, headers={'authorization':'Bearer '+tokens[0]}, json=invite_body)
        viewer_join = client.post('/api/v1/trips/join', headers={'authorization':'Bearer '+tokens[2], 'Idempotency-Key':str(uuid4())},
                                  json={'inviteCode':viewer_invite.json()['inviteCode']})
        assert viewer_join.status_code == 200 and viewer_join.json()['role'] == 'viewer'
        catalog = client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues', headers={'authorization':'Bearer '+tokens[0]})
        venue = catalog.json()['venues'][0]['venueId']
        ws_url = '/ws/v1/trips/' + trip_id
        with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+tokens[0], 'origin':'http://testserver'}) as leader:
            leader_snapshot = leader.receive_json()
            assert leader_snapshot['event'] == 'trip.snapshot'
            with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+tokens[1], 'origin':'http://testserver'}) as planner:
                planner_snapshot = planner.receive_json()
                assert planner_snapshot['event'] == 'trip.snapshot'
                assert planner_snapshot['payload']['sessionId'] == leader_snapshot['payload']['sessionId']
                command = {'commandId':str(uuid4()), 'correlationId':str(uuid4()), 'venueId':venue, 'dayIndex':0,
                           'startTime':'2026-11-10T12:00:00+00:00', 'endTime':'2026-11-10T13:00:00+00:00',
                           'attendeeIds':ids[:2], 'splitMode':'even'}
                asyncio.run(add_foreign_venue())
                invalid_venue = client.post('/api/v1/trips/' + trip_id + '/items',
                    headers={'authorization':'Bearer '+tokens[1]}, json=command | {'venueId':str(foreign_venue)})
                assert invalid_venue.status_code == 422
                planner.send_json({'event':'trip.board.pin','payload':command | {'venueId':str(foreign_venue)}})
                assert planner.receive_json()['payload']['code'] == 'INVALID_VENUE'
                admin_denied = client.post('/api/v1/trips/' + trip_id + '/items',
                    headers={'authorization':'Bearer '+tokens[2]}, json=command)
                assert admin_denied.status_code == 403
                with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+tokens[2], 'origin':'http://testserver'}) as viewer:
                    assert viewer.receive_json()['event'] == 'trip.snapshot'
                    viewer.send_json({'event':'trip.board.pin','payload':command})
                    assert viewer.receive_json()['payload']['code'] == 'FORBIDDEN'
                planner.send_json({'event':'trip.board.pin','payload':command})
                left, right = leader.receive_json(), planner.receive_json()
                assert left['event'] == right['event'] == 'trip.board.update'
                assert left['payload']['item'] == right['payload']['item']
                assert left['payload']['durable'] is False
                ack = planner.receive_json()
                assert ack['event'] == 'trip.command.ack' and ack['payload']['status'] == 'applied'
                committed = leader.receive_json()
                assert committed['event'] == 'trip.persistence.committed' and committed['payload']['committedSeq'] == 1
                assert planner.receive_json()['event'] == 'trip.persistence.committed'
                planner.send_json({'event':'trip.board.pin','payload':command})
                duplicate = planner.receive_json()
                assert duplicate['event'] == 'trip.command.ack' and duplicate['payload']['status'] == 'duplicate'
                assert duplicate['payload']['durable'] is True
                planner.send_json({'event':'trip.board.pin','payload':command | {'dayIndex':1}})
                assert planner.receive_json()['payload']['code'] == 'COMMAND_ID_REUSE'
                asyncio.run(set_role('viewer'))
                asyncio.run(set_admin(ids[1]))
                planner.send_json({'event':'trip.board.pin','payload':command | {'commandId':str(uuid4())}})
                rejected = planner.receive_json()
                assert rejected['event'] == 'trip.command.error' and rejected['payload']['code'] == 'FORBIDDEN'
                http_rejected = client.post('/api/v1/trips/' + trip_id + '/items',
                    headers={'authorization':'Bearer '+tokens[1]}, json=command | {'commandId':str(uuid4())})
                assert http_rejected.status_code == 403
                asyncio.run(set_role('planner'))
        async def restart_rooms():
            await app.state.rooms.close()
            app.state.rooms = RoomManager(app.state.engine)
            app.state.rooms.task = asyncio.create_task(app.state.rooms.run())
        client.portal.call(restart_rooms)
        with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+tokens[1], 'origin':'http://testserver'}) as removed:
            removed.receive_json()
            asyncio.run(set_status('removed'))
            removed.send_json({'event':'trip.snapshot.request','payload':{}})
            with pytest.raises(WebSocketDisconnect):
                removed.receive_json()
            assert client.get('/api/v1/trips/'+trip_id, headers={'authorization':'Bearer '+tokens[1]}).status_code == 404
        asyncio.run(set_status('active'))
        with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+tokens[1], 'origin':'http://testserver'}) as reopened:
            snapshot = reopened.receive_json()
            assert snapshot['event'] == 'trip.snapshot' and snapshot['payload']['committedSeq'] == 1
            assert snapshot['payload']['items'][0]['itemId'] == left['payload']['itemId']
            assert snapshot['payload']['roomEpoch'] != left['payload']['roomEpoch']
            assert snapshot['payload']['sessionId'] == leader_snapshot['payload']['sessionId']
            cost = snapshot['payload']['items'][0]['pricePerPersonMinor']
            assert snapshot['payload']['budgets']['proposedMinor'] == 2 * cost
            assert sum(x['proposedMinor'] for x in snapshot['payload']['budgets']['perPerson']) == 2 * cost
            assert len(snapshot['payload']['members']) == 3
            planner_pin = client.post('/api/v1/trips/' + trip_id + '/items',
                headers={'authorization':'Bearer '+tokens[1]}, json=command | {'commandId':str(uuid4())})
            assert planner_pin.status_code == 201
            assert reopened.receive_json()['event'] == 'trip.board.update'
            assert reopened.receive_json()['event'] == 'trip.persistence.committed'
            csrf = client.cookies.get('tripsync_csrf')
            logged_out = client.post('/api/v1/auth/logout', headers={'authorization':'Bearer '+tokens[1], 'origin':'http://testserver', 'x-csrf-token':csrf})
            assert logged_out.status_code == 204
            with pytest.raises(WebSocketDisconnect):
                reopened.receive_json()
        with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+tokens[0], 'origin':'http://testserver'}) as leader:
            assert leader.receive_json()['event'] == 'trip.snapshot'
            leader_pin = client.post('/api/v1/trips/' + trip_id + '/items',
                headers={'authorization':'Bearer '+tokens[0]}, json=command | {'commandId':str(uuid4())})
            assert leader_pin.status_code == 201 and leader_pin.json()['durable'] is False
            assert leader.receive_json()['event'] == 'trip.board.update'
            assert leader.receive_json()['event'] == 'trip.persistence.committed'
            leader.send_json({'event':'trip.board.pin','payload':command | {'commandId':str(uuid4())}})
            assert leader.receive_json()['event'] == 'trip.board.update'
            assert leader.receive_json()['event'] == 'trip.command.ack'
            assert leader.receive_json()['event'] == 'trip.persistence.committed'
        claims = jwt.decode(tokens[0], 'integration-test-key-'+'x'*40, algorithms=['HS256'], audience='test-client', issuer='test')
        claims['exp'] = datetime.now(timezone.utc) + timedelta(seconds=1)
        short_token = jwt.encode(claims, 'integration-test-key-'+'x'*40, algorithm='HS256')
        with client.websocket_connect(ws_url, headers={'authorization':'Bearer '+short_token, 'origin':'http://testserver'}) as expiring:
            assert expiring.receive_json()['event'] == 'trip.snapshot'
            with pytest.raises(WebSocketDisconnect):
                expiring.receive_json()
    finally:
        asyncio.run(cleanup_trip())


def test_concurrent_invite_redemption_respects_capacity(client):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    ids, tokens = [], []
    trip_id = None
    password = 'capacity test password'
    async def cleanup_case():
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                if trip_id:
                    for table in ('invites', 'memberships'):
                        await conn.execute(text(f'DELETE FROM {table} WHERE trip_id=:id'), {'id':UUID(trip_id)})
                    await conn.execute(text('DELETE FROM trips WHERE id=:id'), {'id':UUID(trip_id)})
                for uid in ids:
                    await conn.execute(text('DELETE FROM http_idempotency WHERE user_id=:id'), {'id':UUID(uid)})
                    await conn.execute(text('DELETE FROM users WHERE id=:id'), {'id':UUID(uid)})
        finally:
            await engine.dispose()
    try:
        for _ in range(3):
            email = f'capacity-{secrets.token_hex(12)}@example.invalid'
            result = client.post('/api/v1/auth/register', json={'email':email,'password':password,'displayName':'Traveler'})
            assert result.status_code == 201
            ids.append(result.json()['userId'])
            result = client.post('/api/v1/auth/login', json={'email':email,'password':password})
            assert result.status_code == 200
            tokens.append(result.json()['accessToken'])
        create = client.post('/api/v1/trips', headers={'authorization':'Bearer '+tokens[0], 'Idempotency-Key':str(uuid4())},
            json={'destination':'Lisbon, Portugal','startDate':'2026-11-10','endDate':'2026-11-14',
                  'totalBudget':'1000.00','currency':'EUR','maxParticipants':2})
        assert create.status_code == 201
        trip_id = create.json()['tripId']
        invite_body = {'role':'planner', 'maxUses':2, 'expiresAt':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}
        issued = client.post('/api/v1/trips/'+trip_id+'/invites',
                             headers={'authorization':'Bearer '+tokens[0]}, json=invite_body)
        assert issued.status_code == 201
        code = issued.json()['inviteCode']
        def join(token):
            return client.post('/api/v1/trips/join', headers={'authorization':'Bearer '+token,'Idempotency-Key':str(uuid4())}, json={'inviteCode':code})
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(join, tokens[1:]))
        assert sorted(r.status_code for r in responses) == [200,409]
        leader = client.get('/api/v1/trips/'+trip_id, headers={'authorization':'Bearer '+tokens[0]})
        assert len(leader.json()['members']) == 2
    finally:
        asyncio.run(cleanup_case())


def test_membership_join_commits_pending_pins_atomically(client):
    from uuid import uuid4
    from fastapi import HTTPException
    password = 'atomic test password'
    ids, tokens = [], []
    trip_id = None
    async def pause_flush():
        app.state.rooms.task.cancel()
        await asyncio.gather(app.state.rooms.task, return_exceptions=True)
    async def query_count():
        engine = create_async_engine(DB)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text('SELECT count(*) FROM itinerary_items WHERE trip_id=:id'), {'id':UUID(trip_id)})).scalar_one()
        finally:
            await engine.dispose()
    async def reject_after_persist():
        room = app.state.rooms.get(UUID(trip_id))
        try:
            async with room.lock, room.transaction_locked():
                raise HTTPException(409, 'test rejection')
        except HTTPException:
            pass
        assert room.committed == 0 and len(room.pending) == 1
    async def cleanup_case():
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                if trip_id:
                    await conn.execute(text('DELETE FROM item_attendees WHERE item_id IN (SELECT id FROM itinerary_items WHERE trip_id=:id)'), {'id':UUID(trip_id)})
                    for table in ('room_events','itinerary_items','invites','memberships'):
                        await conn.execute(text(f'DELETE FROM {table} WHERE trip_id=:id'), {'id':UUID(trip_id)})
                    await conn.execute(text('DELETE FROM trips WHERE id=:id'), {'id':UUID(trip_id)})
                for uid in ids:
                    await conn.execute(text('DELETE FROM http_idempotency WHERE user_id=:id'), {'id':UUID(uid)})
                    await conn.execute(text('DELETE FROM users WHERE id=:id'), {'id':UUID(uid)})
        finally:
            await engine.dispose()
    try:
        for _ in range(2):
            email = f'atomic-{secrets.token_hex(12)}@example.invalid'
            registered = client.post('/api/v1/auth/register', json={'email':email,'password':password,'displayName':'Traveler'})
            assert registered.status_code == 201
            ids.append(registered.json()['userId'])
            login = client.post('/api/v1/auth/login', json={'email':email,'password':password})
            assert login.status_code == 200
            tokens.append(login.json()['accessToken'])
        created = client.post('/api/v1/trips', headers={'authorization':'Bearer '+tokens[0], 'Idempotency-Key':str(uuid4())},
            json={'destination':'Lisbon, Portugal','startDate':'2026-11-10','endDate':'2026-11-14',
                  'totalBudget':'1000.00','currency':'EUR','maxParticipants':2})
        assert created.status_code == 201
        trip_id = created.json()['tripId']
        catalog = client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues', headers={'authorization':'Bearer '+tokens[0]})
        venue = catalog.json()['venues'][0]['venueId']
        client.portal.call(pause_flush)
        command = {'commandId':str(uuid4()), 'correlationId':str(uuid4()), 'venueId':venue, 'dayIndex':0,
                   'startTime':'2026-11-10T12:00:00+00:00', 'endTime':'2026-11-10T13:00:00+00:00', 'attendeeIds':[ids[0]], 'splitMode':'even'}
        pin = client.post('/api/v1/trips/'+trip_id+'/items', headers={'authorization':'Bearer '+tokens[0]}, json=command)
        assert pin.status_code == 201 and pin.json()['durable'] is False
        assert asyncio.run(query_count()) == 0
        client.portal.call(reject_after_persist)
        assert asyncio.run(query_count()) == 0
        joined = client.post('/api/v1/trips/join', headers={'authorization':'Bearer '+tokens[1], 'Idempotency-Key':str(uuid4())},
                             json={'inviteCode':created.json()['inviteCode']})
        assert joined.status_code == 200
        assert asyncio.run(query_count()) == 1
    finally:
        asyncio.run(cleanup_case())
