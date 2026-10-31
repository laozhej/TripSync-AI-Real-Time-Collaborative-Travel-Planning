"""Real process-kill and PostgreSQL-outage drill in a disposable database.

The test-only server holds the flusher before each intentional crash. Opening its
file gate resumes the unmodified production 100-ms loop. No production test API.
"""
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

from dotenv import dotenv_values
import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[2]
url=make_url(dotenv_values(ROOT/'.env')['DATABASE_URL'])
name='tripsync_recovery_'+uuid4().hex
assert name.isidentifier() and name.startswith('tripsync_recovery_')
gate=(ROOT/'.local'/('recovery-'+uuid4().hex+'.gate')).resolve()
assert gate.is_relative_to((ROOT/'.local').resolve())
gate.parent.mkdir(exist_ok=True)
env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'backend')
env['DATABASE_URL']=url.set(database=name).render_as_string(hide_password=False)
env['JWT_SIGNING_KEY']='temporary-recovery-key-'+secrets.token_hex(32)
env['ALLOWED_ORIGINS']='http://127.0.0.1:8001';env['RECOVERY_FLUSH_GATE']=str(gate)
process=None
admin=create_async_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
created=False


def run(command):
    subprocess.run(command,cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)


def start():
    global process
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    process=subprocess.Popen([sys.executable,'-m','uvicorn','recovery_server:app','--app-dir','backend/tests',
        '--host','127.0.0.1','--port','8001','--workers','1'],cwd=ROOT,env=env,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    for _ in range(80):
        if process.poll() is not None: raise RuntimeError('recovery server exited')
        try:
            if httpx.get('http://127.0.0.1:8001/api/v1/health/ready',timeout=1,trust_env=False).status_code==200: return
        except httpx.HTTPError: pass
        time.sleep(.1)
    raise RuntimeError('recovery server not ready')


def crash():
    global process
    if process and process.poll() is None:
        process.kill();process.wait(timeout=10)
    process=None


def until(peer,event):
    for _ in range(100):
        message=json.loads(peer.recv(timeout=8))
        if message['event']==event: return message['payload']
    raise AssertionError('expected event absent')


def send(peer,event,**payload):
    command={'commandId':str(uuid4()),'correlationId':str(uuid4()),**payload}
    peer.send(json.dumps({'event':event,'payload':command}))
    return command


async def allow_connections(enabled):
    async with admin.connect() as conn:
        await conn.execute(text(f'ALTER DATABASE "{name}" ALLOW_CONNECTIONS '+('true' if enabled else 'false')))
        if not enabled:
            await conn.execute(text('SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:db AND pid<>pg_backend_pid()'),{'db':name})


async def drill():
    global created
    sockets=ExitStack()
    with socket.socket() as probe: probe.bind(('127.0.0.1',8001))
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'CREATE DATABASE "{name}"'));created=True
        run([sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'])
        run([sys.executable,'-m','app.cli','import-dataset','data/destinations/lisbon.json'])
        start()
        with httpx.Client(base_url='http://127.0.0.1:8001',timeout=10,trust_env=False) as client:
            users=[];tokens=[]
            for i in range(2):
                email='recovery-'+uuid4().hex+'@example.invalid';password='recovery test password only'
                registration=client.post('/api/v1/auth/register',json={'email':email,'password':password,'displayName':'Traveler '+str(i)})
                assert registration.status_code==201;users.append(registration.json()['userId'])
                login=client.post('/api/v1/auth/login',json={'email':email,'password':password});assert login.status_code==200;tokens.append(login.json()['accessToken'])
            def headers(i): return {'Authorization':'Bearer '+tokens[i]}
            room=client.post('/api/v1/trips',headers=headers(0)|{'Idempotency-Key':str(uuid4())},json={
                'destination':'Lisbon, Portugal','startDate':'2026-11-10','endDate':'2026-11-14','totalBudget':'1000.00','currency':'EUR','maxParticipants':4})
            assert room.status_code==201;trip=room.json()['tripId']
            assert client.post('/api/v1/trips/join',headers=headers(1)|{'Idempotency-Key':str(uuid4())},json={'inviteCode':room.json()['inviteCode']}).status_code==200
            venue=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=headers(0)).json()['venues'][0]['venueId']
            ws='ws://127.0.0.1:8001/ws/v1/trips/'+trip
            def join(i): return sockets.enter_context(connect(ws,additional_headers=headers(i),origin='http://127.0.0.1:8001',open_timeout=5,close_timeout=2))
            leader,planner=join(0),join(1)
            original=until(leader,'trip.snapshot');until(planner,'trip.snapshot')
            first=send(leader,'trip.board.pin',venueId=venue,dayIndex=0,startTime='2026-11-10T12:00:00Z',endTime='2026-11-10T13:00:00Z')
            item=until(leader,'trip.board.update')['item'];assert until(leader,'trip.command.ack')['durable'] is False
            send(leader,'trip.board.lock',itemId=item['itemId'],expectedPositionVersion=1)
            assert until(leader,'trip.board.update')['durable'] is True;until(leader,'trip.command.ack')
            send(planner,'trip.chat.send',body='Durable before crash')
            message=until(planner,'trip.chat.message');until(planner,'trip.command.ack')
            send(leader,'trip.chat.react',messageId=message['messageId'],emoji='👍',active=True)
            until(leader,'trip.chat.reaction.update');until(leader,'trip.command.ack')
            send(leader,'trip.moderation.command',action='transfer',targetUserId=users[1],expectedStateVersion=original['stateVersion'])
            transfer=until(leader,'trip.moderation.update');until(leader,'trip.command.ack')
            baseline=transfer['roomSeq'];assert baseline==5
            send(leader,'trip.board.pin',venueId=venue,dayIndex=1,startTime='2026-11-11T12:00:00Z',endTime='2026-11-11T13:00:00Z')
            assert until(leader,'trip.command.ack')['durable'] is False
            crash();leader.close();planner.close()
            start();reconnected=join(1);snapshot=until(reconnected,'trip.snapshot')
            assert snapshot['roomEpoch']!=original['roomEpoch'] and snapshot['roomSeq']==snapshot['committedSeq']==baseline
            assert len(snapshot['items'])==1 and snapshot['items'][0]['lifecycleStage']=='locked'
            assert snapshot['items'][0]['positionVersion']==2
            assert snapshot['sessionId']==original['sessionId']
            assert snapshot['chat']['items'][0]['body']=='Durable before crash'
            assert snapshot['chat']['items'][0]['reactions']==[{'emoji':'👍','userIds':[users[0]]}]
            assert snapshot['budgets']['lockedMinor']==snapshot['items'][0]['pricePerPersonMinor']*2
            assert {m['userId']:m['role'] for m in snapshot['members']}=={users[0]:'planner',users[1]:'leader'}
            replay=client.post('/api/v1/trips/'+trip+'/items',headers=headers(0),json=first)
            assert replay.status_code==201 and replay.json()['status']=='duplicate' and replay.json()['durable']
            send(reconnected,'trip.board.pin',venueId=venue,dayIndex=1,startTime='2026-11-11T14:00:00Z',endTime='2026-11-11T15:00:00Z')
            assert until(reconnected,'trip.command.ack')['durable'] is False
            await allow_connections(False);gate.touch()
            degraded=until(reconnected,'trip.persistence.degraded');assert degraded['committedSeq']==baseline
            await allow_connections(True)
            assert client.get('/api/v1/health/ready').status_code==503
            denied=client.post('/api/v1/trips/'+trip+'/items',headers=headers(1),json=first|{'commandId':str(uuid4())})
            assert denied.status_code==503
            second_epoch=snapshot['roomEpoch'];crash();reconnected.close();start()
            with join(1) as final:
                restored=until(final,'trip.snapshot')
                assert restored['roomEpoch']!=second_epoch and restored['roomSeq']==restored['committedSeq']==baseline
                assert len(restored['items'])==1 and restored['budgets']==snapshot['budgets']
            print('PASS: actual process kills discard only volatile pins; durable board/chat/reactions/leadership/budgets/session restore with new epochs')
            print('PASS: PostgreSQL connection outage freezes the batch and mutations; restart restores committed watermark '+str(baseline))
    finally:
        crash()
        sockets.close()
        if created:
            await allow_connections(True)
            async with admin.connect() as conn: await conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            print('Disposable recovery database removed')
        if gate.exists(): gate.unlink()
        await admin.dispose()


asyncio.run(drill())
