from app.recommendations.engine import train,rank

def test_hybrid_changes_with_fresh_history_and_cold_item_has_content():
    venues=[{'key':str(i),'category':'food' if i<3 else 'activity','destination':'Bengaluru','price_per_person_minor':10000,'tags':[]} for i in range(6)]
    rows=[{'user':u,'key':key,'kind':'like'} for u,keys in [('a',['0','1']),('b',['0','1']),('c',['3','4'])] for key in keys]
    artifact=train(venues,rows)
    ranked=rank(artifact,[{'key':'0','kind':'like'}],excluded=['0'])
    assert ranked[0]['key']=='1' and ranked[0]['reason']=='content+collaborative'
    assert rank(artifact,[{'key':'3','kind':'like'}],excluded=['3'])[0]['key']=='4'
    assert next(r for r in ranked if r['key']=='2')['contentScore']>0
    assert len(rank(train(venues,[]),[]))==6

def test_training_has_no_access_to_future_test_interactions():
    venues=[{'key':str(i),'category':'activity','destination':'Bengaluru','price_per_person_minor':100,'tags':[]} for i in range(6)]
    artifact=train(venues,[{'user':'a','key':'0','kind':'view'}])
    assert artifact['popularity']=={'0':1}
