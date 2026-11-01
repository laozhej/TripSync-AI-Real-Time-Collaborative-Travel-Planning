import pytest
from app.budget.engine import allocate, summarize

@pytest.mark.parametrize('total,weights,expected',[(1000,{'A':1,'B':1,'C':1},{'A':334,'B':333,'C':333}),(1,{'A':1,'B':1,'C':1},{'A':1,'B':0,'C':0}),(1000,{'A':1,'B':2,'C':3},{'A':167,'B':333,'C':500}),(100,{'A':0,'B':1},{'A':0,'B':100})])
def test_manual_exact_allocations(total,weights,expected):
    assert allocate(total,weights)==expected
    assert allocate(total,dict(reversed(list(weights.items()))))==expected

@pytest.mark.parametrize('weights',[{}, {'A':-1}, {'A':0}, {'A':True}])
def test_invalid_weights(weights):
    with pytest.raises(ValueError): allocate(100,weights)

def test_conservation_and_vote_reservations():
    for total in range(101):
        result=allocate(total,{'A':0,'B':7,'C':11})
        assert sum(result.values())==total and min(result.values())>=0
    items=[{'itemId':str(i),'pricePerPersonMinor':price,'attendeeIds':['A','B'],'weights':{'A':1,'B':3},'splitMode':'weighted','lifecycleStage':'voting'} for i,price in enumerate([100,150])]
    summary=summarize(items,'INR',[{'status':'open','optionIds':['0','1']}])
    assert summary['proposedMinor']==300 and summary['lockedMinor']==0
    assert [p['proposedMinor'] for p in summary['perPerson']]==[75,225]
