"""Opt-in real local-model integration; never substituted by a mock or fallback."""
import os
from uuid import uuid4
import pytest
from test_moderation_integration import group,client,DB,receive_event,app
from test_concierge_integration import configure,SLOT

pytestmark=[pytest.mark.skipif(not DB,reason='requires disposable PostgreSQL'),
            pytest.mark.skipif(os.getenv('RUN_LIVE_MODEL')!='1',reason='set RUN_LIVE_MODEL=1 for actual local inference')]


def test_real_model_answer_and_citation_resolve(client,group):
    async def warmup():
        response=await app.state.model_client.post('/api/chat',json={'model':os.getenv('CONCIERGE_MODEL','qwen2.5:1.5b'),
            'messages':[],'stream':False,'keep_alive':'5m'},timeout=60)
        response.raise_for_status()
    client.portal.call(warmup)
    trip,headers=group['trip'],group['headers']
    with client.websocket_connect('/ws/v1/trips/'+trip,headers=headers(0)|{'origin':'http://testserver'}) as leader:
        receive_event(leader)
        assert configure(client,group,ceilings={'food':2500}).status_code==200
        receive_event(leader)
        response=client.post('/api/v1/trips/'+trip+'/ai/ask',headers=headers(0)|{'Idempotency-Key':str(uuid4())},json=SLOT)
        assert response.status_code==200
        result=response.json()
        assert result['status']=='grounded', 'Real inference must pass; fallback is not live-model evidence'
        assert result['sourceEvents']==['venue:v_1@1']
        assert receive_event(leader)['payload']['questionId']==result['questionId']
        source=client.get('/api/v1/trips/'+trip+'/ai/sources/'+result['sourceEvents'][0],headers=headers(0))
        assert source.status_code==200 and source.json()['pricePerPersonMinor']==2200
