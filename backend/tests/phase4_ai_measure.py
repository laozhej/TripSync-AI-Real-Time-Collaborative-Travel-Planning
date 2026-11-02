"""Isolated actual-model HTTP latency after compact selection optimization."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4
import httpx
from websockets.asyncio.client import connect
from phase4_measure_stats import distribution


async def main():
    base = os.environ['TRIPSYNC_API_TARGET']
    samples = []
    async with httpx.AsyncClient(base_url=base, timeout=15, trust_env=False) as client:
        tokens = []
        for n in range(2):
            body = {'email': 'ai-measure-'+uuid4().hex+'@example.invalid',
                'password': 'synthetic measurement password', 'displayName': 'Traveler '+str(n)}
            assert (await client.post('/api/v1/auth/register', json=body)).status_code == 201
            response = await client.post('/api/v1/auth/login', json={k: body[k] for k in ('email', 'password')})
            assert response.status_code == 200
            tokens.append(response.json()['accessToken'])
        def headers(n): return {'Authorization': 'Bearer '+tokens[n]}
        response = await client.post('/api/v1/trips', headers=headers(0) | {'Idempotency-Key': str(uuid4())}, json={
            'destination': 'Bengaluru, India', 'startDate': '2026-11-10', 'endDate': '2026-11-14',
            'totalBudget': '10000.00', 'currency': 'INR', 'maxParticipants': 50})
        assert response.status_code == 201
        room = response.json()
        assert (await client.post('/api/v1/trips/join', headers=headers(1) | {'Idempotency-Key': str(uuid4())},
            json={'inviteCode': room['inviteCode']})).status_code == 200
        root = '/api/v1/trips/'+room['tripId']
        async with connect(base.replace('http:', 'ws:')+'/ws/v1/trips/'+room['tripId'],
                origin=os.environ['BROWSER_BASE_URL'], additional_headers=headers(0)) as peer:
            snapshot = json.loads(await peer.recv())['payload']
            response = await client.post(root+'/constraints', headers=headers(0), json={'commandId': str(uuid4()),
                'correlationId': str(uuid4()), 'expectedStateVersion': snapshot['stateVersion'], 'categoryCeilingsMinor': {'food': 50000}})
            assert response.status_code == 200
            async def drain():
                async for _ in peer: pass
            reader = asyncio.create_task(drain())
            async with httpx.AsyncClient(base_url=os.getenv('CONCIERGE_MODEL_URL', 'http://127.0.0.1:11434'), timeout=60, trust_env=False) as inference:
                model = os.getenv('CONCIERGE_MODEL', 'qwen2.5:1.5b')
                (await inference.post('/api/generate', json={'model': model, 'keep_alive': 0})).raise_for_status()
                for n in range(101):
                    if n == 1:
                        t = time.perf_counter()
                        (await inference.post('/api/chat', json={'model': model, 'messages': [], 'stream': False, 'keep_alive': '5m'})).raise_for_status()
                        preload_ms = (time.perf_counter()-t)*1000
                    t = time.perf_counter()
                    response = await client.post(root+'/ai/ask', headers=headers(0) | {'Idempotency-Key': str(uuid4())}, json={
                        'question': 'Find synthetic vegetarian food', 'category': 'food', 'ceilingMinor': 50000,
                        'startTime': '2026-11-10T06:30:00Z', 'endTime': '2026-11-10T07:30:00Z'})
                    samples.append({'profile': 'cold' if n == 0 else 'warm', 'ms': (time.perf_counter()-t)*1000,
                        'httpStatus': response.status_code, 'status': response.json().get('status')})
                    assert response.status_code == 200
                    for citation in response.json().get('sourceEvents', []):
                        source = await client.get(root+'/ai/sources/'+citation, headers=headers(0))
                        assert source.status_code == 200 and source.json()['pricePerPersonMinor'] <= 50000
                runtime = (await inference.get('/api/version')).json()
                loaded = (await inference.get('/api/ps')).json()
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
    summary = {'completedUtc': datetime.now(timezone.utc).isoformat(), 'runtime': runtime, 'loadedModel': loaded,
        'method': 'HTTP dispatch to complete grounded JSON; unique idempotency keys; one unloaded cold request, disclosed completed preload, 100 repeated warm requests; excludes browser paint',
        'preloadMs': preload_ms, 'failures': sum(s['httpStatus'] != 200 for s in samples),
        'distributions': {profile: {status: distribution([s['ms'] for s in samples if s['profile'] == profile and s['status'] == status])
            for status in sorted({s['status'] for s in samples if s['profile'] == profile})} for profile in ('cold', 'warm')}}
    out = Path('evidence/performance')
    out.mkdir(parents=True, exist_ok=True)
    (out/'ai-samples.json').write_text(json.dumps(samples, indent=2), encoding='utf-8')
    (out/'ai-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


asyncio.run(main())
