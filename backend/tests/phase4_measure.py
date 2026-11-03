"""Single-host real HTTP/socket/model measurements; run via browser_clean_setup.

Only synthetic identifiers and numeric measurements leave the disposable DB.
Clock is perf_counter on one process. Socket apply is not browser paint.
"""
import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time
from uuid import uuid4
import httpx
from websockets.asyncio.client import connect
from phase4_measure_stats import distribution

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/os.getenv('MEASUREMENT_OUTPUT', 'evidence/performance')


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = os.environ['TRIPSYNC_API_TARGET']
    origin = os.environ['BROWSER_BASE_URL']
    samples, api, joins, ai, conflicts, races = [], [], [], [], [], []
    started = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(base_url=base, timeout=15, trust_env=False) as client, AsyncExitStack() as stack:
        tokens, users = [], []
        for i in range(5):
            email = 'load-'+uuid4().hex+'@example.invalid'
            body = {'email': email, 'password': 'synthetic measurement password', 'displayName': 'Traveler '+str(i)}
            r = await client.post('/api/v1/auth/register', json=body)
            assert r.status_code == 201
            users.append(r.json()['userId'])
            r = await client.post(
                '/api/v1/auth/login', json={k: body[k] for k in ('email', 'password')})
            assert r.status_code == 200
            tokens.append(r.json()['accessToken'])
        def headers(i): return {'Authorization': 'Bearer '+tokens[i]}
        rooms = []
        for leader, members in ((0, [1, 2]), (3, [4])):
            r = await client.post('/api/v1/trips', headers=headers(leader) | {'Idempotency-Key': str(uuid4())}, json={
                'destination': 'Bengaluru, India', 'startDate': '2026-11-10', 'endDate': '2026-11-14',
                'totalBudget': '100000.00', 'currency': 'INR', 'maxParticipants': 50})
            assert r.status_code == 201
            rooms.append(r.json()['tripId'])
            for member in members:
                joined = await client.post('/api/v1/trips/join', headers=headers(member) | {'Idempotency-Key': str(uuid4())},
                    json={'inviteCode': r.json()['inviteCode']})
                assert joined.status_code == 200
        venues = (await client.get('/api/v1/destinations/Bengaluru%2C%20India/venues', headers=headers(0))).json()['venues']
        sockets, states, pending = [], [], {}
        conflict_waiters = {}

        async def reader(index, peer):
            async for raw in peer:
                event = json.loads(raw)
                payload = event['payload']
                if event['event'] == 'trip.board.update':
                    item = payload.get('item')
                    if item:
                        states[index][item['itemId']] = item
                    elif payload.get('operation') == 'remove':
                        states[index].pop(payload['itemId'], None)
                    key = payload.get('commandId')
                    if (key, index) in pending:
                        pending[(key, index)].set_result((time.perf_counter(), payload))
                elif event['event'] == 'trip.board.conflict':
                    for (room_index, peer_index), future in list(conflict_waiters.items()):
                        if peer_index == index and not future.done():
                            future.set_result(time.perf_counter())
                elif event['event'] == 'trip.board.edit.conflict':
                    races.append(payload)

        tasks = []
        for room_index, identities in enumerate(([0, 1, 2, 0, 1], [3, 4, 3, 4, 3])):
            for identity in identities:
                t = time.perf_counter()
                peer = await stack.enter_async_context(connect(base.replace('http:', 'ws:')+'/ws/v1/trips/'+rooms[room_index],
                    origin=origin, additional_headers=headers(identity)))
                while True:
                    event = json.loads(await peer.recv())
                    if event['event'] == 'trip.snapshot': break
                joins.append((time.perf_counter()-t)*1000)
                states.append({i['itemId']: i for i in event['payload']['items']})
                sockets.append(peer)
                tasks.append(asyncio.create_task(reader(len(sockets)-1, peer)))

        async def mutate(room_index, event, body, measure=True):
            key = str(uuid4())
            indices = range(room_index*5, room_index*5+5)
            for index in indices: pending[(key, index)] = asyncio.get_running_loop().create_future()
            t = time.perf_counter()
            await sockets[room_index*5].send(json.dumps({'event': event, 'payload': {
                'commandId': key, 'correlationId': key, **body}}))
            results = await asyncio.wait_for(asyncio.gather(*(pending[(key, index)] for index in indices)), 10)
            for index in indices: del pending[(key, index)]
            if measure:
                times = [r[0] for r in results]
                samples.append({'commandId': key, 'room': room_index, 'event': event, 'allAppliedMs': (max(times)-t)*1000,
                    'spreadMs': (max(times)-min(times))*1000})
            return results[0][1]['item']

        items = []
        for room_index in range(2):
            items.append(await mutate(room_index, 'trip.board.pin', {'venueId': venues[0]['venueId'], 'dayIndex': 0,
                'startTime': '2026-11-10T06:30:00Z', 'endTime': '2026-11-10T07:30:00Z'}, False))
        # Explicit short warmup; not the proposed two-minute sustained profile.
        warmup_start = time.perf_counter()
        for n in range(20):
            room_index = n % 2
            items[room_index] = await mutate(room_index, 'trip.board.move', {
                'itemId': items[room_index]['itemId'], 'expectedPositionVersion': items[room_index]['positionVersion'],
                'dayIndex': 0, 'startTime': '2026-11-10T06:30:00Z', 'endTime': '2026-11-10T07:30:00Z'}, False)
            await asyncio.sleep(.04)
        warmup_seconds = time.perf_counter()-warmup_start
        for n in range(1000):
            room_index = n % 2
            item = items[room_index]
            minute = '30' if n % 4 < 2 else '35'
            items[room_index] = await mutate(room_index, 'trip.board.move', {'itemId': item['itemId'],
                'expectedPositionVersion': item['positionVersion'], 'dayIndex': 0,
                'startTime': f'2026-11-10T06:{minute}:00Z', 'endTime': f'2026-11-10T07:{minute}:00Z'})
            route = ('planning', 'budgets', 'recommendations', 'conflicts', 'analytics')[n % 5]
            t = time.perf_counter()
            response = await client.get('/api/v1/trips/'+rooms[room_index]+'/'+route, headers=headers(0 if room_index == 0 else 3))
            api.append({'route': route, 'ms': (time.perf_counter()-t)*1000, 'status': response.status_code})
            assert response.status_code == 200
            await asyncio.sleep(.025)
        # Barrier-dispatched stale-version contention, separate from load profile.
        for n in range(20):
            item = items[0]
            payload = {'itemId': item['itemId'], 'expectedPositionVersion': item['positionVersion'], 'dayIndex': 0,
                'startTime': '2026-11-10T06:30:00Z', 'endTime': '2026-11-10T07:30:00Z'}
            before = len(races)
            await asyncio.gather(*(sockets[i].send(json.dumps({'event': 'trip.board.move', 'payload': {
                'commandId': str(uuid4()), 'correlationId': str(uuid4()), **payload}})) for i in (0, 1)))
            for _ in range(100):
                if len(races) > before and states[0][item['itemId']]['positionVersion'] == item['positionVersion']+1: break
                await asyncio.sleep(.01)
            assert len(races) == before+1
            items[0] = states[0][item['itemId']]
        # Distinct overlapping intervals avoid automatic identical-slot elections.
        for n in range(20):
            waiter = asyncio.get_running_loop().create_future()
            conflict_waiters[(0, 0)] = waiter
            t = time.perf_counter()
            extra = await mutate(0, 'trip.board.pin', {'venueId': venues[1]['venueId'], 'dayIndex': 0,
                'startTime': '2026-11-10T06:45:00Z', 'endTime': '2026-11-10T07:15:00Z'}, False)
            notified = await asyncio.wait_for(waiter, 5)
            conflicts.append((notified-t)*1000)
            conflict_waiters.clear()
            await mutate(0, 'trip.board.remove', {'itemId': extra['itemId'], 'expectedPositionVersion': extra['positionVersion']}, False)
            await asyncio.sleep(.12)
        # Compare all aggregates and REST authoritative state after a reconnect.
        for room_index in range(2):
            authoritative = (await client.get('/api/v1/trips/'+rooms[room_index]+'/planning', headers=headers(0 if room_index == 0 else 3))).json()
            active = {i['itemId']: i for i in authoritative['items']}
            for state in states[room_index*5:room_index*5+5]:
                assert all(state[k] == v for k, v in active.items())
            t = time.perf_counter()
            async with connect(base.replace('http:', 'ws:')+'/ws/v1/trips/'+rooms[room_index], origin=origin,
                    additional_headers=headers(0 if room_index == 0 else 3)) as peer:
                snapshot = json.loads(await peer.recv())['payload']
                assert snapshot['items'] == authoritative['items'] and snapshot['budgets'] == authoritative['budgets']
                joins.append((time.perf_counter()-t)*1000)
        print('PASS: 10 sockets / 5 distinct planners / 2 rooms; 1000 moves, 1000 HTTP reads, 20 stale races, 20 conflicts, aggregate/reconnect equality')
        tags = {}
        if os.getenv('MEASURE_BOARD_ONLY') != '1':
            model_url = os.getenv('CONCIERGE_MODEL_URL', 'http://127.0.0.1:11434')
            model = os.getenv('CONCIERGE_MODEL', 'qwen2.5:1.5b')
            state = (await client.get('/api/v1/trips/'+rooms[0]+'/planning', headers=headers(0))).json()
            configured = await client.post('/api/v1/trips/'+rooms[0]+'/constraints', headers=headers(0), json={
                'commandId': str(uuid4()), 'correlationId': str(uuid4()), 'expectedStateVersion': state['stateVersion'],
                'categoryCeilingsMinor': {'food': 50000}})
            assert configured.status_code == 200
            async with httpx.AsyncClient(base_url=model_url, timeout=60, trust_env=False) as inference:
                tags = (await inference.get('/api/tags')).json()
                # Explicit unload gives a genuine cold application request, not preload timing.
                (await inference.post('/api/generate', json={'model': model, 'keep_alive': 0})).raise_for_status()
                for n in range(101):
                    if n == 1:
                        # A deadline-cancelled cold request may cancel model loading.
                        # Warm samples require a disclosed completed preload first.
                        warm = await inference.post('/api/chat', json={'model': model, 'messages': [],
                            'stream': False, 'keep_alive': '5m'})
                        warm.raise_for_status()
                    t = time.perf_counter()
                    r = await client.post('/api/v1/trips/'+rooms[0]+'/ai/ask', headers=headers(0) | {'Idempotency-Key': str(uuid4())}, json={
                        'question': 'Find synthetic vegetarian food', 'category': 'food', 'ceilingMinor': 50000,
                        'startTime': '2026-11-10T06:30:00Z', 'endTime': '2026-11-10T07:30:00Z'})
                    ai.append({'profile': 'cold' if n == 0 else 'warm', 'ms': (time.perf_counter()-t)*1000,
                        'httpStatus': r.status_code, 'status': r.json().get('status')})
                    assert r.status_code == 200
                    if r.json().get('suggestedVenueId'):
                        for citation in r.json()['sourceEvents']:
                            source = await client.get('/api/v1/trips/'+rooms[0]+'/ai/sources/'+citation, headers=headers(0))
                            assert source.status_code == 200 and source.json()['pricePerPersonMinor'] <= 50000
        if os.getenv('BROWSER_SERVER') == 'sync_profile_server:app':
            profile = (await client.get('/__test/sync-profile')).json()
            (OUT/'server-profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    summary = {'startedUtc': started, 'finishedUtc': datetime.now(timezone.utc).isoformat(),
        'os': platform.platform(), 'python': platform.python_version(), 'clock': 'one-process perf_counter; loopback; socket aggregate apply, excludes browser paint',
        'clients': 10, 'distinctUsers': 5, 'rooms': 2, 'warmupSeconds': warmup_seconds, 'mutations': distribution([s['allAppliedMs'] for s in samples]),
        'interClientSpread': distribution([s['spreadMs'] for s in samples]), 'joinSnapshot': distribution(joins),
        'conflictDispatchToNotification': distribution(conflicts), 'staleRaces': len(races),
        'api': {route: distribution([s['ms'] for s in api if s['route'] == route]) for route in sorted({s['route'] for s in api})},
        'httpFailures': sum(s['status'] != 200 for s in api), 'model': tags,
        'ai': {profile: {status: distribution([s['ms'] for s in ai if s['profile'] == profile and s['status'] == status])
            for status in sorted({s['status'] for s in ai if s['profile'] == profile})} for profile in ('cold', 'warm')},
        'datasetSha256': hashlib.sha256((ROOT/'data/destinations/bengaluru.json').read_bytes()).hexdigest()}
    (OUT/'samples.json').write_text(json.dumps({'board': samples, 'http': api, 'joinsMs': joins, 'conflictsMs': conflicts, 'ai': ai}, indent=2), encoding='utf-8')
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


asyncio.run(main())
