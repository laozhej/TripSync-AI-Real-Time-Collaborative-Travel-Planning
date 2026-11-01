"""Phase 3 acceptance against disposable PostgreSQL."""
import asyncio
from decimal import Decimal
from uuid import UUID,uuid4
import pytest
from test_auth_integration import DB,app,client,receive_event
from test_moderation_integration import group

pytestmark=pytest.mark.skipif(not DB,reason='requires disposable migrated database')

def test_weighted_budgets_vote_winner_and_recovery(client,group):
    trip,h=group['trip'],group['headers'];root='/api/v1/trips/'+trip
    def post(path,body,i=0):return client.post(root+path,headers=h(i),json=body)
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=h(0)|{'origin':'http://testserver'}) as leader:
        receive_event(leader)
        venues=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=h(0)).json()['venues'][:2]
        async def stop():
            app.state.rooms.task.cancel();await asyncio.gather(app.state.rooms.task,return_exceptions=True)
        client.portal.call(stop)
        for v in venues:
            response=post('/items',{'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':v['venueId'],'dayIndex':0,
                'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z','splitMode':'weighted',
                'attendeeIds':group['ids'][:2],'weights':{group['ids'][0]:1,group['ids'][1]:2}})
            assert response.status_code==201,response.text
        room=app.state.rooms.get(UUID(trip))
        versions={k:i['positionVersion'] for k,i in room.items.items()}
        command={'commandId':str(uuid4()),'correlationId':str(uuid4()),'expectedVersions':versions,'durationSeconds':10}
        assert post('/votes',command,1).status_code==403
        opened=post('/votes',command);assert opened.status_code==200,opened.text
        vote=opened.json()['vote']
        assert opened.json()['budgetSummary']['proposedMinor']==max(Decimal(v['pricePerPerson']) for v in venues)*200
        assert post('/votes',command).json()['status']=='duplicate'
        ballot={'commandId':str(uuid4()),'correlationId':str(uuid4()),'voteId':vote['voteId'],'choiceVenueId':venues[1]['venueId'],'expectedBallotVersion':0}
        assert post('/votes/cast',ballot,2).status_code==403
        assert post('/votes/cast',ballot,1).status_code==200
        assert post('/votes/cast',ballot,1).json()['status']=='duplicate'
        ballot['commandId']=str(uuid4())
        assert post('/votes/cast',ballot,1).json()['detail']['code']=='STALE_BALLOT_VERSION'
        asyncio.run(group['sql']("UPDATE votes SET closes_at=now()-interval '1 second' WHERE id=:id",{'id':UUID(vote['voteId'])}))
        async def restart():
            from app.realtime.rooms import RoomManager
            await app.state.rooms.close();app.state.rooms=RoomManager(app.state.engine)
            await app.state.rooms.recover()
            app.state.rooms.task=asyncio.create_task(app.state.rooms.run())
        client.portal.call(restart)
        result=client.get(root+'/planning',headers=h(1));assert result.status_code==200,result.text
        state=result.json();assert len(state['items'])==1 and state['items'][0]['venueId']==venues[1]['venueId']
        assert state['items'][0]['lifecycleStage']=='locked' and state['votes'][0]['status']=='resolved'
        assert not [c for c in state['conflicts'] if c['status']=='open']
        analytics=client.get(root+'/analytics',headers=h(0)).json()
        assert analytics['finalBudgets']==state['budgets'] and analytics['conflictsFlagged']==analytics['conflictsResolved']==1
        with client.websocket_connect('/ws/v1/trips/'+trip,headers=h(0)|{'origin':'http://testserver'}) as new_leader:
            receive_event(new_leader)
            ask={'question':'Check a food suggestion','category':'food','startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}
            key=str(uuid4())
            assert client.post(root+'/ai/ask',headers=h(0)|{'Idempotency-Key':key},json=ask).status_code==200
            assert client.post(root+'/ai/ask',headers=h(0)|{'Idempotency-Key':key},json=ask).status_code==200
            finalize={'commandId':str(uuid4()),'correlationId':str(uuid4()),'expectedStateVersion':state['stateVersion']}
            assert client.post(root+'/finalize',headers=h(1),json=finalize).status_code==403
            finalized=client.post(root+'/finalize',headers=h(0),json=finalize);assert finalized.status_code==200,finalized.text
            assert client.post(root+'/finalize',headers=h(0),json=finalize).json()['status']=='duplicate'
            final=client.get(root+'/analytics',headers=h(0)).json()
            from datetime import datetime
            assert final['sessionDurationSeconds']==(datetime.fromisoformat(final['sessionEndedAt'])-datetime.fromisoformat(final['sessionStartedAt'])).total_seconds()
            assert final['peakPlanners']==1 and final['aiCount']==1
            assert final['finalBudgets']['proposedMinor']==final['finalBudgets']['lockedMinor']==2400
            assert sorted(p['lockedMinor'] for p in final['finalBudgets']['perPerson'])==[800,1600]
            assert client.post(root+'/chat',headers=h(1),json={'body':'Finalized chat'}).status_code==403
    assert client.get(root+'/planning',headers=h(3)).status_code==404

def test_system_vote_cancels_once_and_split_stale_is_explicit(client,group):
    from app.voting.service import tick
    trip,h=group['trip'],group['headers'];root='/api/v1/trips/'+trip
    async def stop():
        app.state.rooms.task.cancel();await asyncio.gather(app.state.rooms.task,return_exceptions=True)
    client.portal.call(stop)
    venues=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=h(0)).json()['venues'][:2]
    for v in venues:
        result=client.post(root+'/items',headers=h(1),json={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':v['venueId'],
            'dayIndex':0,'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'})
        assert result.status_code==201
    room=app.state.rooms.get(UUID(trip))
    client.portal.call(tick,room)
    vote=room.votes[0];assert vote['openedBy']=='system' and vote['status']=='open'
    item=next(iter(room.items.values()))
    command={'commandId':str(uuid4()),'correlationId':str(uuid4()),'itemId':item['itemId'],'expectedPositionVersion':item['positionVersion'],
             'attendeeIds':group['ids'][:2],'splitMode':'weighted','weights':{group['ids'][0]:0,group['ids'][1]:1}}
    assert client.post(root+'/items/split',headers=h(1),json=command).status_code==403
    # Force the persisted deadline to be overdue, hydrate it, then run the managed tick.
    asyncio.run(group['sql']("UPDATE votes SET closes_at=now()-interval '1 second' WHERE id=:id",{'id':UUID(vote['voteId'])}))
    client.get(root+'/planning',headers=h(1))
    client.portal.call(tick,room);seq=room.seq
    client.portal.call(tick,room)
    assert room.seq==seq and room.votes[0]['status']=='cancelled'
    assert all(i['lifecycleStage']=='drafting' for i in room.items.values())
    assert client.post(root+'/items/split',headers=h(1),json=command).json()['detail']['code']=='STALE_POSITION_VERSION'
    command['expectedPositionVersion']=room.items[item['itemId']]['positionVersion']
    result=client.post(root+'/items/split',headers=h(1),json=command);assert result.status_code==200,result.text
    assert result.json()['budgetSummary']['itemAllocations'][item['itemId']][group['ids'][0]]==0
    command['commandId']=str(uuid4())
    assert client.post(root+'/items/split',headers=h(2),json=command).status_code==403

def test_dashboard_recommendations_and_admin_staging(client,group,monkeypatch):
    h=group['headers'];trip=group['trip'];root='/api/v1/trips/'+trip
    dashboard=client.get('/api/v1/me/dashboard',headers=h(0));assert dashboard.status_code==200
    assert trip in [t['tripId'] for t in dashboard.json()['trips']]
    import json
    from pathlib import Path
    bundle=json.loads(Path('data/destinations/bengaluru.json').read_text(encoding='utf-8'))
    bundle['destination']='Phase3-'+uuid4().hex
    assert client.post('/api/v1/admin/datasets',headers=h(0),json=bundle).status_code==403
    invalid=dict(bundle);invalid['venues']=[dict(bundle['venues'][0],pricePerPerson='-1')]
    assert client.post('/api/v1/admin/datasets',headers=h(3),json=invalid).status_code==422
    uploaded=client.post('/api/v1/admin/datasets',headers=h(3),json=bundle);assert uploaded.status_code==201,uploaded.text
    dataset=uploaded.json()['datasetId']
    assert client.post('/api/v1/admin/datasets/'+dataset+'/activate',headers=h(3)).status_code==200
    rail=client.get(root+'/recommendations',headers=h(1));assert rail.status_code==200,rail.text
    venue=rail.json()['items'][0]['venueId']
    body={'venueId':venue,'kind':'like','eventId':str(uuid4())}
    assert client.post(root+'/interactions',headers=h(1),json=body).status_code==201
    assert client.post(root+'/interactions',headers=h(3),json=body).status_code==404
    assert client.post(root+'/recommendations/train',headers=h(1)).status_code==403
    trained=client.post(root+'/recommendations/train',headers=h(3));assert trained.status_code==404
    trained=client.post(root+'/recommendations/train',headers=h(2));assert trained.status_code==200,trained.text
    rail=client.get(root+'/recommendations',headers=h(1)).json();assert rail['modelVersion']==trained.json()['modelVersion']
    # Both participants' real endpoint interactions create item-neighbor evidence.
    for i in (0,1):
        for option in rail['items'][:2]:
            assert client.post(root+'/interactions',headers=h(i),json={'venueId':option['venueId'],'kind':'like','eventId':str(uuid4())}).status_code==201
    assert client.post(root+'/recommendations/train',headers=h(2)).status_code==200
    updated=client.get(root+'/recommendations',headers=h(1)).json()
    assert any(i['reason']=='content+collaborative' for i in updated['items'])
    monkeypatch.setattr('app.recommendations.service.train',lambda *args:{'features':{},'neighbors':{}})
    with pytest.raises(ValueError,match='invalid artifact'):
        client.post(root+'/recommendations/train',headers=h(2))
    assert client.get(root+'/recommendations',headers=h(1)).json()['modelVersion']==updated['modelVersion']
    before=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',params={'tripId':trip},headers=h(1)).json()
    existing=json.loads(Path('data/destinations/lisbon.json').read_text(encoding='utf-8'))
    existing['provenance']['notice']+=' Phase 3 immutable activation check.'
    stage=client.post('/api/v1/admin/datasets',headers=h(3),json=existing);assert stage.status_code==201
    assert client.post('/api/v1/admin/datasets/'+stage.json()['datasetId']+'/activate',headers=h(3)).status_code==200
    assert client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',params={'tripId':trip},headers=h(1)).json()==before
    active=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=h(1)).json()
    assert active['venues'][0]['venueId']!=before['venues'][0]['venueId']
    assert client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',params={'tripId':trip},headers=h(3)).status_code==404

def test_vote_deadline_and_removed_ballots(client,group):
    from app.voting.service import tick
    trip,h=group['trip'],group['headers'];root='/api/v1/trips/'+trip
    async def stop():
        app.state.rooms.task.cancel();await asyncio.gather(app.state.rooms.task,return_exceptions=True)
    client.portal.call(stop)
    venues=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=h(0)).json()['venues'][:2]
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=h(0)|{'origin':'http://testserver'}) as leader:
        receive_event(leader)
        for v in venues:
            assert client.post(root+'/items',headers=h(1),json={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':v['venueId'],
                'dayIndex':0,'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}).status_code==201
        room=app.state.rooms.get(UUID(trip));client.portal.call(tick,room);vote=room.votes[0]
        def ballot(i,venue,version=0):return client.post(root+'/votes/cast',headers=h(i),json={'commandId':str(uuid4()),'correlationId':str(uuid4()),
            'voteId':vote['voteId'],'choiceVenueId':venue,'expectedBallotVersion':version})
        assert ballot(0,venues[0]['venueId']).status_code==200
        assert ballot(1,venues[1]['venueId']).status_code==200
        state=client.get(root+'/planning',headers=h(0)).json()
        # Removed Planner's ballot is invalidated in the same moderation commit.
        assert client.post(root+'/moderation',headers=h(0),json={'commandId':str(uuid4()),'correlationId':str(uuid4()),'action':'remove',
            'targetUserId':group['ids'][1],'expectedStateVersion':state['stateVersion']}).status_code==200
        assert asyncio.run(group['sql']('SELECT count(*) AS n FROM ballots WHERE vote_id=:vote',{'vote':UUID(vote['voteId'])}))[0]['n']==1
        assert ballot(1,venues[1]['venueId'],1).status_code==404
        asyncio.run(group['sql']("UPDATE votes SET closes_at=now()-interval '1 second' WHERE id=:id",{'id':UUID(vote['voteId'])}))
        client.get(root+'/planning',headers=h(0))
        assert ballot(0,venues[1]['venueId'],1).json()['detail']['code']=='VOTE_CLOSED'
        client.portal.call(tick,room)
        assert next(iter(room.items.values()))['venueId']==venues[0]['venueId']

def test_vote_failed_commit_never_announces_or_persists_election(client,group):
    from contextlib import asynccontextmanager
    trip,h=group['trip'],group['headers'];root='/api/v1/trips/'+trip
    engine=app.state.rooms.engine
    class FailedCommit:
        def connect(self):return engine.connect()
        @asynccontextmanager
        async def begin(self):
            async with engine.begin() as conn:
                yield conn
                raise ConnectionError('injected commit failure')
    async def stop():
        app.state.rooms.task.cancel();await asyncio.gather(app.state.rooms.task,return_exceptions=True)
    client.portal.call(stop)
    try:
        with client.websocket_connect('/ws/v1/trips/'+trip,headers=h(0)|{'origin':'http://testserver'}) as leader:
            receive_event(leader)
            venues=client.get('/api/v1/destinations/Lisbon%2C%20Portugal/venues',headers=h(0)).json()['venues'][:2]
            for v in venues:
                assert client.post(root+'/items',headers=h(1),json={'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':v['venueId'],
                    'dayIndex':0,'startTime':'2026-11-10T12:00:00Z','endTime':'2026-11-10T13:00:00Z'}).status_code==201
            room=app.state.rooms.get(UUID(trip));app.state.rooms.engine=FailedCommit()
            result=client.post(root+'/votes',headers=h(0),json={'commandId':str(uuid4()),'correlationId':str(uuid4()),'expectedVersions':{k:i['positionVersion'] for k,i in room.items.items()}})
            assert result.status_code==503 and room.frozen and room.votes==[]
            assert all(i['lifecycleStage']=='drafting' for i in room.items.values())
            assert asyncio.run(group['sql']('SELECT id FROM votes WHERE trip_id=:trip',{'trip':UUID(trip)}))==[]
            assert asyncio.run(group['sql']('SELECT id FROM itinerary_items WHERE trip_id=:trip',{'trip':UUID(trip)}))==[]
            app.state.rooms.engine=engine
    finally:app.state.rooms.engine=engine
