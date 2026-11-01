from app.concierge.conflicts import detect
from app.budget.engine import summarize

def test_overlap_touching_intervals_and_personal_vs_group_ceilings():
    def item(key,start,end,attendees):return {'itemId':key,'startTime':f'2026-11-10T{start}:00+05:30','endTime':f'2026-11-10T{end}:00+05:30','attendeeIds':attendees,'pricePerPersonMinor':100,'lifecycleStage':'drafting'}
    a=item('a','12:00','13:00',['A']);b=item('b','13:00','14:00',['A'])
    budget=summarize([a,b],'INR')
    found=detect([a,b],budget,1000,{'A':150})
    assert len(found)==1 and next(iter(found.values()))['details']['userId']=='A'
    b=item('b','12:30','13:30',['A'])
    assert len(detect([a,b],budget,100,{'A':150}))==3
    assert detect([a,b],budget,100,{'A':150})==detect([b,a],budget,100,{'A':150})
