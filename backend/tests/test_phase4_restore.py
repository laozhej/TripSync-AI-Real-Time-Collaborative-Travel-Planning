"""Actual pg_dump/pg_restore plus overdue-vote recovery in isolated databases."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from uuid import UUID, uuid4
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from test_auth_integration import DB, app, client, receive_event
from test_moderation_integration import group

pytestmark = pytest.mark.skipif(not DB, reason='requires disposable PostgreSQL')
ROOT = Path(__file__).resolve().parents[2]


async def manifest(engine):
    result = {}
    async with engine.connect() as conn:
        tables = (await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))).scalars().all()
        for table in tables:
            assert table.replace('_', '').isalnum()
            rows = (await conn.execute(text(f'SELECT row_to_json(t)::text FROM "{table}" t ORDER BY row_to_json(t)::text'))).scalars().all()
            result[table] = {'rows': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    return result


@pytest.mark.parametrize('group', [{'destination': 'Bengaluru, India', 'currency': 'INR', 'totalBudget': '100000.00'}], indirect=True)
def test_logical_backup_exact_restore_and_overdue_vote_once(client, group):
    url = make_url(DB)
    assert url.database.startswith('tripsync_verify_'), 'Never dump a non-disposable database in this test'
    dump, restore = shutil.which('pg_dump'), shutil.which('pg_restore')
    assert dump and restore, 'Install PostgreSQL client tools; this test must not silently skip'
    name = 'tripsync_restore_'+uuid4().hex
    archive = (ROOT/'.local'/('restore-'+uuid4().hex+'.dump')).resolve()
    assert archive.is_relative_to((ROOT/'.local').resolve())
    archive.parent.mkdir(exist_ok=True)
    trip, headers = group['trip'], group['headers']
    root = '/api/v1/trips/'+trip

    async def stop():
        app.state.rooms.task.cancel()
        await asyncio.gather(app.state.rooms.task, return_exceptions=True)
    client.portal.call(stop)
    with client.websocket_connect('/ws/v1/trips/'+trip, headers=headers(0) | {'origin': 'http://testserver'}) as peer:
        receive_event(peer)
        venues = client.get('/api/v1/destinations/Bengaluru%2C%20India/venues', headers=headers(0)).json()['venues'][:2]
        for venue in venues:
            result = client.post(root+'/items', headers=headers(0), json={
                'commandId': str(uuid4()), 'correlationId': str(uuid4()), 'venueId': venue['venueId'], 'dayIndex': 0,
                'startTime': '2026-11-10T06:30:00Z', 'endTime': '2026-11-10T07:30:00Z',
                'attendeeIds': group['ids'][:2], 'splitMode': 'weighted', 'weights': {group['ids'][0]: 1, group['ids'][1]: 2}})
            assert result.status_code == 201
        state = client.get(root+'/planning', headers=headers(0)).json()
        opened = client.post(root+'/votes', headers=headers(0), json={'commandId': str(uuid4()),
            'correlationId': str(uuid4()), 'expectedVersions': {i['itemId']: i['positionVersion'] for i in state['items']}, 'durationSeconds': 10})
        assert opened.status_code == 200
        vote = opened.json()['vote']
        assert client.post(root+'/votes/cast', headers=headers(1), json={'commandId': str(uuid4()), 'correlationId': str(uuid4()),
            'voteId': vote['voteId'], 'choiceVenueId': venues[1]['venueId'], 'expectedBallotVersion': 0}).status_code == 200
    asyncio.run(group['sql']("UPDATE votes SET closes_at=now()-interval '1 second' WHERE id=:id", {'id': UUID(vote['voteId'])}))

    async def drill():
        from app.realtime.rooms import RoomManager
        admin = create_async_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
        source = create_async_engine(url)
        restored = create_async_engine(url.set(database=name))
        created = False
        manager = None
        env = os.environ.copy()
        env['PGPASSWORD'] = url.password or ''
        common = ['--host', url.host or '127.0.0.1', '--port', str(url.port or 5432), '--username', url.username]
        def run(args):
            result = subprocess.run(args, env=env, capture_output=True, timeout=60)
            assert result.returncode == 0, 'PostgreSQL backup/restore tool failed (diagnostics suppressed)'
        try:
            before = await manifest(source)
            async with source.connect() as conn:
                columns = (await conn.execute(text("SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position"))).mappings().all()
                indexes = (await conn.execute(text("SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname"))).mappings().all()
            contracts = ROOT/'evidence'/'contracts'
            contracts.mkdir(parents=True, exist_ok=True)
            (contracts/'schema.json').write_text(json.dumps({'columns': [dict(r) for r in columns], 'indexes': [dict(r) for r in indexes]}, indent=2), encoding='utf-8')
            (contracts/'openapi.json').write_text(json.dumps(app.openapi(), indent=2), encoding='utf-8')
            await asyncio.to_thread(run, [dump, *common, '--format=custom', '--no-owner', '--file', str(archive), '--dbname', url.database])
            async with admin.connect() as conn:
                await conn.execute(text(f'CREATE DATABASE "{name}"'))
                created = True
            await asyncio.to_thread(run, [restore, *common, '--no-owner', '--no-privileges', '--exit-on-error', '--dbname', name, str(archive)])
            after = await manifest(restored)
            assert before == after, 'Every public table must restore byte-identical logical rows'
            manager = RoomManager(restored)
            await manager.recover()
            room = manager.get(UUID(trip))
            await room.load()
            assert len(room.items) == 1
            winner = next(iter(room.items.values()))
            assert winner['venueId'] == venues[1]['venueId'] and winner['lifecycleStage'] == 'locked'
            assert room.epoch != state['roomEpoch']
            budgets = room.budget_summary('INR')
            # Independent integer fixture: two attendees, weights 1:2, remainder
            # assigned by fractional rank then user ID (not a call to split engine).
            total = winner['pricePerPersonMinor']*2
            allocation = {group['ids'][0]: total//3, group['ids'][1]: 2*total//3}
            if sum(allocation.values()) < total:
                target = group['ids'][0] if total % 3 > (2*total) % 3 else group['ids'][1]
                allocation[target] += 1
            assert budgets['lockedMinor'] == total
            assert {p['userId']: p['lockedMinor'] for p in budgets['perPerson'] if p['lockedMinor']} == allocation
            assert room.votes[0]['status'] == 'resolved'
            seq = room.seq
            from app.voting.service import tick
            await tick(room)
            assert room.seq == seq
            async with restored.connect() as conn:
                resolutions = (await conn.execute(text("SELECT count(*) FROM room_events WHERE trip_id=:trip AND type='trip.vote.resolved'"), {'trip': UUID(trip)})).scalar_one()
                assert resolutions == 1
            record = {'tables': before, 'allTableDigestsEqual': True, 'archiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                'newEpoch': True, 'overdueVoteResolutions': resolutions, 'lockedMinor': total,
                'independentWeightedAmounts': sorted(allocation.values()), 'repeatedTickNoDuplicate': True}
            output = ROOT/'evidence'/'operations'
            output.mkdir(parents=True, exist_ok=True)
            (output/'restore.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        finally:
            if manager: await manager.close()
            await source.dispose()
            await restored.dispose()
            if created:
                async with admin.connect() as conn:
                    await conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            await admin.dispose()
            archive.unlink(missing_ok=True)
    asyncio.run(drill())
