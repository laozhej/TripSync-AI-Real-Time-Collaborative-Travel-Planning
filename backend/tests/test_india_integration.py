"""Indian currency and IST flow; inference mocked here, real inference tested in browser."""
import json
from uuid import uuid4
import httpx
import pytest
from test_moderation_integration import group,client,DB,app,receive_event
from test_concierge_integration import configure

pytestmark=pytest.mark.skipif(not DB,reason='requires disposable PostgreSQL')

@pytest.mark.parametrize('group',[{'destination':'Bengaluru, India','currency':'INR','totalBudget':'25000.00'}],indirect=True)
def test_indian_room_budget_events_and_grounded_currency(client,group):
    trip=group['trip'];headers=group['headers'](0)
    info=client.get('/api/v1/trips/'+trip,headers=headers).json()
    assert info['currency']=='INR' and info['timezone']=='Asia/Kolkata'
    assert info['totalBudgetMinor']==2500000
    catalog=client.get('/api/v1/destinations/Bengaluru%2C%20India/venues',headers=headers).json()
    venue=next(v for v in catalog['venues'] if v['sourceId']=='venue:v_1@1')
    assert venue['pricePerPerson']=='350.00'
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers|{'origin':'http://testserver'}) as socket:
        assert receive_event(socket)['payload']['budgets']['currency']=='INR'
        socket.send_json({'event':'trip.board.pin','payload':{
            'commandId':str(uuid4()),'correlationId':str(uuid4()),'venueId':venue['venueId'],
            'dayIndex':0,'startTime':'2026-11-10T12:00:00+05:30','endTime':'2026-11-10T13:00:00+05:30',
            'attendeeIds':[],'splitMode':'even'}})
        update=receive_event(socket)
        assert update['payload']['budgetSummary']['currency']=='INR'
        assert configure(client,group,ceilings={'food':50000}).status_code==200
        async def generate(request):
            data={'sourceId':'v_1'}
            return httpx.Response(200,json={'message':{'content':json.dumps(data)}})
        original=app.state.model_client
        fake=httpx.AsyncClient(transport=httpx.MockTransport(generate),base_url='http://127.0.0.1:11434')
        app.state.model_client=fake
        try:
            response=client.post('/api/v1/trips/'+trip+'/ai/ask',headers=headers|{'Idempotency-Key':str(uuid4())},json={
                'question':'Suggest vegetarian lunch in Bengaluru','category':'food',
                'startTime':'2026-11-10T12:00:00+05:30','endTime':'2026-11-10T13:00:00+05:30'})
            assert response.status_code==200
            assert response.json()['status']=='grounded'
            assert 'INR350.00' in response.json()['answer'] and 'EUR' not in response.json()['answer']
            source=client.get('/api/v1/trips/'+trip+'/ai/sources/venue:v_1@1',headers=headers).json()
            assert source['currency']=='INR' and source['pricePerPersonMinor']==35000
        finally:
            app.state.model_client=original
            client.portal.call(fake.aclose)
