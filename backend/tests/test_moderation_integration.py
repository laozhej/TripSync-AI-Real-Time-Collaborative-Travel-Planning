"""Database-backed moderation acceptance, using a disposable migrated database."""
import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.websockets import WebSocketDisconnect

from test_auth_integration import DB, app, client, receive_event
from app.realtime.rooms import RoomManager

pytestmark = pytest.mark.skipif(not DB, reason='set TEST_DATABASE_URL to a disposable migrated database')


@pytest.fixture
def group(client,request):
    settings=getattr(request,'param',{})
    ids, tokens, trips = [], [], []
    async def sql(query, params):
        engine = create_async_engine(DB)
        try:
            async with engine.begin() as conn:
                rows = await conn.execute(text(query), params)
                return rows.mappings().all() if rows.returns_rows else None
        finally:
            await engine.dispose()
    def headers(i): return {'authorization':'Bearer '+tokens[i]}
    try:
        for i in range(4):
            email = 'moderation-'+secrets.token_hex(12)+'@example.invalid'
            body = {'email':email,'password':'moderation test password','displayName':['Leader','Planner','Viewer','Admin'][i]}
            registration = client.post('/api/v1/auth/register',json=body)
            assert registration.status_code == 201
            ids.append(registration.json()['userId'])
            login = client.post('/api/v1/auth/login',json={'email':email,'password':body['password']})
            assert login.status_code == 200
            tokens.append(login.json()['accessToken'])
        asyncio.run(sql('UPDATE users SET is_admin=true WHERE id=ANY(:ids)',{'ids':[UUID(ids[2]),UUID(ids[3])]}))
        def create(i):
            response = client.post('/api/v1/trips',headers=headers(i) | {'Idempotency-Key':str(uuid4())},json={
                'destination':settings.get('destination','Lisbon, Portugal'),'startDate':'2026-11-10','endDate':'2026-11-14',
                'totalBudget':settings.get('totalBudget','1000.00'),'currency':settings.get('currency','EUR'),'maxParticipants':5})
            assert response.status_code == 201
            trips.append(response.json()['tripId'])
            return response.json()
        main = create(0)
        other = create(3)
        trip = main['tripId']
        joined = client.post('/api/v1/trips/join',headers=headers(1) | {'Idempotency-Key':str(uuid4())},json={'inviteCode':main['inviteCode']})
        assert joined.status_code == 200
        issued = client.post('/api/v1/trips/'+trip+'/invites',headers=headers(0),json={
            'role':'viewer','maxUses':3,'expiresAt':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
        assert issued.status_code == 201
        code = issued.json()['inviteCode']
        viewer_key=str(uuid4())
        joined = client.post('/api/v1/trips/join',headers=headers(2) | {'Idempotency-Key':viewer_key},json={'inviteCode':code})
        assert joined.status_code == 200
        yield {'ids':ids,'tokens':tokens,'trip':trip,'headers':headers,'sql':sql,'invite':code,'other':other['tripId'],'viewerJoinKey':viewer_key}
    finally:
        for trip in trips:
            params={'trip':UUID(trip)}
            asyncio.run(sql('DELETE FROM reactions WHERE message_id IN (SELECT id FROM chat_messages WHERE trip_id=:trip)',params))
            asyncio.run(sql('DELETE FROM item_attendees WHERE item_id IN (SELECT id FROM itinerary_items WHERE trip_id=:trip)',params))
            for table in ('ai_questions','chat_messages','room_events','room_snapshots','itinerary_items','invites','memberships','trips'):
                column = 'id' if table == 'trips' else 'trip_id'
                asyncio.run(sql(f'DELETE FROM {table} WHERE {column}=:trip',params))
        for uid in ids:
            asyncio.run(sql('DELETE FROM http_idempotency WHERE user_id=:uid',{'uid':UUID(uid)}))
            asyncio.run(sql('DELETE FROM users WHERE id=:uid',{'uid':UUID(uid)}))


def test_moderation_permissions_versions_transfer_removal_and_recovery(client,group):
    ids, trip, headers = group['ids'], group['trip'], group['headers']
    endpoint = '/api/v1/trips/'+trip+'/moderation'
    wsurl = '/ws/v1/trips/'+trip
    def command(action, version, target=None):
        body = {'commandId':str(uuid4()),'correlationId':str(uuid4()),'action':action,'expectedStateVersion':version}
        if target is not None: body['targetUserId']=target
        return body
    def socket(i): return client.websocket_connect(wsurl,headers=headers(i) | {'origin':'http://testserver'})
    version = client.get('/api/v1/trips/'+trip,headers=headers(0)).json()['stateVersion']
    assert client.post(endpoint,headers=headers(0),json=command('lockRoom',version)).json()['detail']['code']=='LEADER_DISCONNECTED'
    with socket(0) as leader, socket(1) as planner, socket(0) as leader_tab:
        receive_event(leader); receive_event(leader_tab)
        snapshot = receive_event(planner)['payload']
        assert snapshot['leaderConnected'] and len(snapshot['connectedUsers']) >= 2
        planner.send_json({'event':'trip.moderation.command','payload':command('lockRoom',version)})
        assert receive_event(planner)['payload']['code']=='FORBIDDEN'
        with socket(2) as viewer_admin:
            receive_event(viewer_admin)
            viewer_admin.send_json({'event':'trip.moderation.command','payload':command('lockRoom',version)})
            assert receive_event(viewer_admin)['payload']['code']=='FORBIDDEN'
        with pytest.raises(WebSocketDisconnect):
            with socket(3): pass
        for i,status in ((1,403),(2,403),(3,404)):
            assert client.post(endpoint,headers=headers(i),json=command('mute',version,ids[1])).status_code == status
        assert client.post(endpoint,headers=headers(0),json=command('mute',version,ids[3])).json()['detail']['code']=='TARGET_UNAVAILABLE'
        assert client.post(endpoint,headers=headers(0),json=command('mute',version,ids[0])).json()['detail']['code']=='INVALID_TARGET'
        muted = client.post(endpoint,headers=headers(0),json=command('mute',version,ids[1]))
        assert muted.status_code == 200 and muted.json()['durable']
        version += 1
        for peer in (leader,planner,leader_tab):
            update=receive_event(peer)
            assert update['event']=='trip.chat.typing.update' or update['event']=='trip.moderation.update'
            if update['event']=='trip.chat.typing.update': update=receive_event(peer)
            assert update['payload']['stateVersion']==version
        assert client.post('/api/v1/trips/'+trip+'/chat',headers=headers(1),json={'body':'Denied'}).status_code==403
        planner.send_json({'event':'trip.chat.typing','payload':{'isTyping':True}})
        assert receive_event(planner)['payload']['code']=='FORBIDDEN'
        stale=client.post(endpoint,headers=headers(0),json=command('unmute',version-1,ids[1]))
        assert stale.status_code==409 and stale.json()['detail']['currentStateVersion']==version
        unmute=command('unmute',version,ids[1])
        leader.send_json({'event':'trip.moderation.command','payload':unmute})
        assert receive_event(leader)['event']=='trip.moderation.update'
        assert receive_event(leader)['payload']['status']=='committed'
        receive_event(planner); receive_event(leader_tab)
        version+=1
        leader.send_json({'event':'trip.moderation.command','payload':unmute})
        assert receive_event(leader)['payload']['status']=='duplicate'
        leader.send_json({'event':'trip.moderation.command','payload':unmute | {'action':'mute'}})
        assert receive_event(leader)['payload']['code']=='COMMAND_ID_REUSE'
        assert client.post(endpoint,headers=headers(0),json=command('lockRoom',version)).status_code==200
        version+=1
        for peer in (leader,planner,leader_tab): assert receive_event(peer)['payload']['roomLocked']
        join=client.post('/api/v1/trips/join',headers=headers(3) | {'Idempotency-Key':str(uuid4())},json={'inviteCode':group['invite']})
        assert join.status_code==403
        catalog=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=headers(1)).json()
        pin={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':catalog['venues'][0]['venueId'],
             'dayIndex':0,'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}
        assert client.post('/api/v1/trips/'+trip+'/items',headers=headers(1),json=pin).status_code==403
        # Read/chat remain available under a room lock.
        assert client.post('/api/v1/trips/'+trip+'/chat',headers=headers(2),json={'body':'Viewer chat'}).status_code==201
        for peer in (leader,planner,leader_tab): assert receive_event(peer)['event']=='trip.chat.message'
        assert client.post(endpoint,headers=headers(0),json=command('unlockRoom',version)).status_code==200
        version+=1
        for peer in (leader,planner,leader_tab): assert receive_event(peer)['payload']['roomLocked'] is False
        assert client.post(endpoint,headers=headers(0),json=command('transfer',version,ids[2])).json()['detail']['code']=='INVALID_TARGET'
        transfer=command('transfer',version,ids[1])
        result=client.post(endpoint,headers=headers(0),json=transfer)
        assert result.status_code==200
        version+=1
        for peer in (leader,planner,leader_tab):
            update=receive_event(peer)['payload']
            assert update['leaderUserId']==ids[1] and update['stateVersion']==version
        rows=asyncio.run(group['sql']("SELECT t.leader_user_id,m.user_id FROM trips t JOIN memberships m ON m.trip_id=t.id WHERE t.id=:trip AND m.role='leader' AND m.status='active'",{'trip':UUID(trip)}))
        assert len(rows)==1 and str(rows[0]['leader_user_id'])==str(rows[0]['user_id'])==ids[1]
        assert client.post(endpoint,headers=headers(0),json=transfer).json()['status']=='duplicate'
        assert client.post(endpoint,headers=headers(0),json=command('lockRoom',version)).status_code==403
        leader.send_json({'event':'trip.moderation.command','payload':command('lockRoom',version)})
        assert receive_event(leader)['payload']['code']=='FORBIDDEN'
        planner.send_json({'event':'trip.moderation.command','payload':command('remove',version,ids[0])})
        # Removal closes all sessions/tabs of that membership immediately.
        for peer in (leader,leader_tab):
            with pytest.raises(WebSocketDisconnect) as closed: receive_event(peer)
            assert closed.value.code==1008
        update=receive_event(planner)
        if update['event']=='trip.chat.typing.update': update=receive_event(planner)
        assert update['event']=='trip.moderation.update'
        assert receive_event(planner)['payload']['durable']
        assert client.get('/api/v1/trips/'+trip,headers=headers(0)).status_code==404
        assert client.post('/api/v1/trips/join',headers=headers(0) | {'Idempotency-Key':str(uuid4())},json={'inviteCode':group['invite']}).status_code==403
        with pytest.raises(WebSocketDisconnect):
            with socket(0): pass
    async def restart():
        await app.state.rooms.close()
        app.state.rooms=RoomManager(app.state.engine)
        app.state.rooms.task=asyncio.create_task(app.state.rooms.run())
    client.portal.call(restart)
    with socket(1) as recovered:
        snapshot=receive_event(recovered)['payload']
        assert snapshot['stateVersion']==version+1 and snapshot['trip']['roomLocked'] is False
        assert {m['userId']:m['role'] for m in snapshot['members']}=={ids[1]:'leader',ids[2]:'viewer'}
        assert client.post(endpoint,headers=headers(1),json=command('remove',version+1,ids[2])).status_code==200
        replay=client.post('/api/v1/trips/join',headers=headers(2) | {'Idempotency-Key':group['viewerJoinKey']},json={'inviteCode':group['invite']})
        assert replay.status_code==403


def test_failed_moderation_commit_rolls_back_pending_pin_and_freezes_room(client,group):
    from contextlib import asynccontextmanager
    trip, headers = group['trip'], group['headers']
    actual_engine=app.state.rooms.engine
    class FailedCommit:
        def connect(self): return actual_engine.connect()
        @asynccontextmanager
        async def begin(self):
            async with actual_engine.begin() as conn:
                yield conn
                raise ConnectionError('injected commit failure')
    async def stop_flush():
        app.state.rooms.task.cancel()
        await asyncio.gather(app.state.rooms.task,return_exceptions=True)
    try:
        with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers(0) | {'origin':'http://testserver'}) as leader:
            before=receive_event(leader)['payload']
            client.portal.call(stop_flush)
            catalog=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=headers(0)).json()
            pin={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':catalog['venues'][0]['venueId'],
                 'dayIndex':0,'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}
            assert client.post('/api/v1/trips/'+trip+'/items',headers=headers(0),json=pin).json()['durable'] is False
            assert receive_event(leader)['event']=='trip.board.update'
            app.state.rooms.engine=FailedCommit()
            command={'commandId':str(uuid4()),'correlationId':str(uuid4()),'action':'lockRoom',
                     'expectedStateVersion':before['stateVersion']}
            failed=client.post('/api/v1/trips/'+trip+'/moderation',headers=headers(0),json=command)
            assert failed.status_code==503
            assert receive_event(leader)['event']=='trip.persistence.degraded'
            room=app.state.rooms.get(UUID(trip))
            assert room.frozen and len(room.pending)==1 and room.committed==0
            rows=asyncio.run(group['sql']('SELECT room_locked,state_version,committed_seq FROM trips WHERE id=:trip',{'trip':UUID(trip)}))
            assert rows[0]['room_locked'] is False and rows[0]['state_version']==before['stateVersion'] and rows[0]['committed_seq']==0
            assert asyncio.run(group['sql']('SELECT id FROM itinerary_items WHERE trip_id=:trip',{'trip':UUID(trip)}))==[]
    finally:
        app.state.rooms.engine=actual_engine


def test_last_leader_tab_drop_and_reconnect_do_not_promote_planner(client,group):
    trip,headers=group['trip'],group['headers']; url='/ws/v1/trips/'+trip
    def connect(i): return client.websocket_connect(url,headers=headers(i)|{'origin':'http://testserver'})
    def presence(peer,action=None):
        while True:
            event=peer.receive_json()
            if event['event']=='trip.presence.update' and (action is None or event['payload']['action']==action): return event['payload']
    with connect(1) as planner:
        assert receive_event(planner)['payload']['leaderConnected'] is False
        presence(planner)
        with connect(0) as leader:
            snapshot=receive_event(leader)['payload']; version=snapshot['stateVersion']
            assert presence(planner,'joined')['leaderConnected'] is True
            with connect(0) as second:
                assert receive_event(second)['payload']['leaderConnected'] is True
                assert presence(planner,'updated')['participantCount']==2
            assert presence(planner,'updated')['leaderConnected'] is True
        left=presence(planner,'left')
        assert left['leaderConnected'] is False and left['participantCount']==1
        command={'commandId':str(uuid4()),'correlationId':str(uuid4()),'expectedStateVersion':version,'action':'lockRoom'}
        assert client.post('/api/v1/trips/'+trip+'/moderation',headers=headers(0),json=command).json()['detail']['code']=='LEADER_DISCONNECTED'
        detail=client.get('/api/v1/trips/'+trip,headers=headers(1)).json()
        assert {m['userId']:m['role'] for m in detail['members']}[group['ids'][1]]=='planner'
        with connect(0) as reconnected:
            assert receive_event(reconnected)['payload']['leaderConnected'] is True
            command['commandId']=str(uuid4())
            assert client.post('/api/v1/trips/'+trip+'/moderation',headers=headers(0),json=command).status_code==200
            assert receive_event(planner)['payload']['roomLocked'] is True


def test_actual_room_concurrent_moves_have_one_winner_and_one_conflict(client,group):
    from app.api.auth import auth_config
    from app.auth.tokens import decode_access_token
    from app.realtime.gateway import Move
    from app.realtime.rooms import RoomError
    trip,headers=group['trip'],group['headers']
    actors=[]
    for token in group['tokens'][:2]:
        uid,sid=decode_access_token(token,**auth_config());actors.append({'user_id':uid,'session_id':sid})
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers(0)|{'origin':'http://testserver'}) as leader:
        receive_event(leader)
        catalog=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=headers(0)).json()
        pin={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':catalog['venues'][0]['venueId'],
             'dayIndex':0,'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}
        assert client.post('/api/v1/trips/'+trip+'/items',headers=headers(0),json=pin).status_code==201
        item=receive_event(leader)['payload']['item']
        async def concurrent():
            room=app.state.rooms.get(UUID(trip))
            for version in (1,2,3):
                await room.change_item(actors[0],Move(commandId=uuid4(),correlationId=uuid4(),itemId=item['itemId'],expectedPositionVersion=version,
                    dayIndex=0,startTime='2026-11-10T12:00:00Z',endTime='2026-11-10T13:00:00Z'),'move')
            commands=[Move(commandId=uuid4(),correlationId=uuid4(),itemId=item['itemId'],expectedPositionVersion=4,
                dayIndex=1,startTime=f'2026-11-11T{hour}:00:00Z',endTime=f'2026-11-11T{int(hour)+1}:00:00Z') for hour in ('12','14')]
            barrier=asyncio.Event()
            async def move(actor,command):
                await barrier.wait()
                return await room.change_item(actor,command,'move')
            tasks=[asyncio.create_task(move(actor,command)) for actor,command in zip(actors,commands)]
            await asyncio.sleep(0)
            barrier.set()
            results=await asyncio.gather(*tasks,return_exceptions=True)
            await room.flush()
            async with room.lock: snapshot=await room.snapshot_locked(actors[0])
            return results,snapshot
        results,snapshot=client.portal.call(concurrent)
        assert sum(isinstance(value,dict) for value in results)==1
        losers=[value for value in results if isinstance(value,RoomError)]
        assert len(losers)==1 and losers[0].code=='STALE_POSITION_VERSION'
        assert losers[0].details['currentPositionVersion']==5
        assert snapshot['items'][0]['positionVersion']==5 and snapshot['roomSeq']==snapshot['committedSeq']==5


def test_chat_reactions_enforce_trip_scope_and_muted_removed_members(client,group):
    trip,other,headers=group['trip'],group['other'],group['headers']
    own=client.post('/api/v1/trips/'+trip+'/chat',headers=headers(0),json={'body':'Main trip only'})
    foreign=client.post('/api/v1/trips/'+other+'/chat',headers=headers(3),json={'body':'Other trip only'})
    assert own.status_code==foreign.status_code==201
    for i in (0,1,2):
        history=client.get('/api/v1/trips/'+trip+'/chat',headers=headers(i))
        assert history.status_code==200 and [m['body'] for m in history.json()['items']]==['Main trip only']
    assert client.get('/api/v1/trips/'+trip+'/chat',headers=headers(3)).status_code==404
    wsurl='/ws/v1/trips/'+trip
    def until(peer,event):
        for _ in range(100):
            message=peer.receive_json()
            if message['event']==event:return message['payload']
        raise AssertionError('expected event absent')
    with client.websocket_connect(wsurl,headers=headers(0)|{'origin':'http://testserver'}) as leader, client.websocket_connect(wsurl,headers=headers(1)|{'origin':'http://testserver'}) as planner, client.websocket_connect(wsurl,headers=headers(2)|{'origin':'http://testserver'}) as viewer:
        snapshot=until(leader,'trip.snapshot');until(planner,'trip.snapshot');until(viewer,'trip.snapshot')
        def react(peer,message,active=True):
            peer.send_json({'event':'trip.chat.react','payload':{'commandId':str(uuid4()),'correlationId':str(uuid4()),'messageId':message,'emoji':'👍','active':active}})
        react(planner,foreign.json()['messageId'])
        assert until(planner,'trip.command.error')['code']=='NOT_FOUND'
        command={'commandId':str(uuid4()),'correlationId':str(uuid4()),'expectedStateVersion':snapshot['stateVersion'],'action':'mute','targetUserId':group['ids'][1]}
        assert client.post('/api/v1/trips/'+trip+'/moderation',headers=headers(0),json=command).status_code==200
        for peer in (leader,planner,viewer):until(peer,'trip.moderation.update')
        react(planner,own.json()['messageId'])
        assert until(planner,'trip.command.error')['code']=='FORBIDDEN'
        planner.send_json({'event':'trip.chat.send','payload':{'commandId':str(uuid4()),'correlationId':str(uuid4()),'body':'Muted'}})
        assert until(planner,'trip.command.error')['code']=='FORBIDDEN'
        # Account Admin has the same chat capabilities as its Viewer membership.
        for active in (True,True,False,False):
            react(viewer,own.json()['messageId'],active)
            expected=[{'emoji':'👍','userIds':[group['ids'][2]]}] if active else []
            assert until(viewer,'trip.chat.reaction.update')['reactions']==expected
            assert until(viewer,'trip.command.ack')['durable']
            for peer in (leader,planner):until(peer,'trip.chat.reaction.update')
        command.update(commandId=str(uuid4()),expectedStateVersion=snapshot['stateVersion']+1,action='remove')
        assert client.post('/api/v1/trips/'+trip+'/moderation',headers=headers(0),json=command).status_code==200
        with pytest.raises(WebSocketDisconnect):until(planner,'trip.moderation.update')
        assert client.get('/api/v1/trips/'+trip+'/chat',headers=headers(1)).status_code==404
        assert client.post('/api/v1/trips/'+trip+'/chat',headers=headers(1),json={'body':'Removed'}).status_code==404


def test_chat_history_sequence_cursor_and_snapshot_boundaries(client,group):
    trip,headers=group['trip'],group['headers'];url='/api/v1/trips/'+trip+'/chat'
    ids=[]
    for i in range(105):
        response=client.post(url,headers=headers(0),json={'body':'History '+str(i)})
        assert response.status_code==201;ids.append(response.json()['messageId'])
    first=client.get(url,headers=headers(1)).json()
    assert len(first['items'])==50 and [m['messageId'] for m in first['items']]==ids[55:]
    assert first['nextCursor']=='56'
    # A newly committed message must not shift the older page boundary.
    assert client.post(url,headers=headers(0),json={'body':'New message'}).status_code==201
    second=client.get(url,params={'before':first['nextCursor']},headers=headers(1)).json()
    third=client.get(url,params={'before':second['nextCursor']},headers=headers(1)).json()
    assert [m['messageId'] for m in second['items']]==ids[5:55]
    assert [m['messageId'] for m in third['items']]==ids[:5] and third['nextCursor'] is None
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers(0)|{'origin':'http://testserver'}) as leader:
        history=receive_event(leader)['payload']['chat']
        assert len(history['items'])==100 and history['nextCursor']=='7'
        assert history['items'][-1]['body']=='New message'


def test_lost_commit_ack_recovers_durable_result_without_reapplying(client,group):
    from contextlib import asynccontextmanager
    trip,headers=group['trip'],group['headers'];engine=app.state.rooms.engine
    class LostAcknowledgement:
        def connect(self): return engine.connect()
        @asynccontextmanager
        async def begin(self):
            async with engine.begin() as conn: yield conn
            raise ConnectionError('injected acknowledgement loss after commit')
    async def stop():
        app.state.rooms.task.cancel();await asyncio.gather(app.state.rooms.task,return_exceptions=True)
    try:
        with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers(0)|{'origin':'http://testserver'}) as leader:
            old=receive_event(leader)['payload'];client.portal.call(stop)
            venue=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=headers(0)).json()['venues'][0]['venueId']
            pin={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':venue,'dayIndex':0,
                'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}
            assert client.post('/api/v1/trips/'+trip+'/items',headers=headers(0),json=pin).status_code==201
            item=receive_event(leader)['payload']['item']
            command={'commandId':str(uuid4()),'correlationId':str(uuid4()),'itemId':item['itemId'],'expectedPositionVersion':1}
            app.state.rooms.engine=LostAcknowledgement()
            leader.send_json({'event':'trip.board.lock','payload':command})
            assert receive_event(leader)['event']=='trip.persistence.degraded'
            assert receive_event(leader)['payload']['code']=='PERSISTENCE_DEGRADED'
            room=app.state.rooms.get(UUID(trip));assert room.frozen and room.committed==0
            rows=asyncio.run(group['sql']('SELECT committed_seq FROM trips WHERE id=:trip',{'trip':UUID(trip)}))
            assert rows[0]['committed_seq']==2
            app.state.rooms.engine=engine
    finally: app.state.rooms.engine=engine
    async def restart():
        await app.state.rooms.close();app.state.rooms=RoomManager(engine);app.state.rooms.task=asyncio.create_task(app.state.rooms.run())
    client.portal.call(restart)
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers(0)|{'origin':'http://testserver'}) as recovered:
        snapshot=receive_event(recovered)['payload']
        assert snapshot['roomEpoch']!=old['roomEpoch'] and snapshot['roomSeq']==snapshot['committedSeq']==2
        assert len(snapshot['items'])==1 and snapshot['items'][0]['positionVersion']==2 and snapshot['items'][0]['lifecycleStage']=='locked'
        recovered.send_json({'event':'trip.board.lock','payload':command})
        duplicate=receive_event(recovered)
        assert duplicate['event']=='trip.command.ack' and duplicate['payload']['status']=='duplicate' and duplicate['payload']['durable']
        assert duplicate['payload']['roomSeq']==2
