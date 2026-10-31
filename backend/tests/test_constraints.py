from datetime import datetime
from pathlib import Path
import pytest
from app.datasets.schema import Dataset, Venue
from app.concierge.constraints import Constraints, rank_candidates

DATA = Dataset.model_validate_json(Path('data/destinations/lisbon.json').read_text())


def request(**changes):
    return Constraints.model_validate(dict(category='food',ceilingMinor=2200,start='2026-11-10T12:00:00Z',
        end='2026-11-10T13:00:00Z',timezone='Europe/Lisbon') | changes)


@pytest.mark.parametrize('ceiling,expected',[(1,False),(2199,False),(2200,True),(2201,True),(3500,True)])
def test_exact_price_boundary(ceiling,expected):
    result=rank_candidates(DATA.venues[:1],request(ceilingMinor=ceiling))
    assert bool(result) is expected


@pytest.mark.parametrize('diet',[[],['vegan'],['halal'],['gluten-free'],['vegan','halal','gluten-free','vegetarian']])
def test_all_attendee_diets(diet):
    assert rank_candidates(DATA.venues[:1],request(requiredDiets=diet))


@pytest.mark.parametrize('start,end,expected',[
    ('11:29','12:00',False),('11:30','12:00',True),('21:00','22:00',True),
    ('21:00','22:01',False),('10:00','11:00',False)])
def test_full_buffered_interval(start,end,expected):
    assert bool(rank_candidates(DATA.venues[:1],request(start=f'2026-11-10T{start}:00Z',end=f'2026-11-10T{end}:00Z'))) is expected


@pytest.mark.parametrize('radius,expected',[(.001,False),(.1,True),(1,True),(2,True),(20,True)])
def test_anchor_radius(radius,expected):
    assert bool(rank_candidates(DATA.venues[:1],request(anchor={'lat':38.714,'lng':-9.139},radiusKm=radius))) is expected


def test_missing_diet_is_excluded():
    assert rank_candidates([DATA.venues[4]],request(requiredDiets={'halal'},start='2026-11-10T23:00:00Z',end='2026-11-11T00:00:00Z')) == []


def test_previous_day_overnight_hours():
    assert rank_candidates([DATA.venues[4]],request(start='2026-11-11T00:30:00Z',end='2026-11-11T01:30:00Z'))


def test_no_anchor_normalization_and_stable_ties():
    venue=DATA.venues[0]
    twin=Venue.model_validate(venue.model_dump(mode='json') | {'sourceId':'a'})
    result=rank_candidates([venue,twin],request())
    assert [c['sourceId'] for c in result] == ['a',venue.sourceId]
    assert result[0]['score'] == pytest.approx(.64)


def test_unknown_category_excludes():
    assert rank_candidates(DATA.venues[:1],request(category='activity')) == []


def test_naive_time_rejected():
    with pytest.raises(ValueError): request(start='2026-11-10T12:00:00')

@pytest.mark.parametrize('end,expected',[('21:00',True),('21:01',False)])
def test_summer_timezone_conversion(end,expected):
    assert bool(rank_candidates(DATA.venues[:1],request(start='2026-07-10T19:00:00Z',end=f'2026-07-10T{end}:00Z'))) is expected


def test_numeric_radius_boundary():
    from app.concierge.constraints import distance_km
    anchor={'lat':38.714,'lng':-9.139}
    distance=distance_km(anchor['lat'],anchor['lng'],DATA.venues[0].coordinates.lat,DATA.venues[0].coordinates.lng)
    assert rank_candidates(DATA.venues[:1],request(anchor=anchor,radiusKm=distance))
    assert rank_candidates(DATA.venues[:1],request(anchor=anchor,radiusKm=distance-.00001))==[]


@pytest.mark.parametrize('date',['2026-03-29','2026-10-25'])
def test_nonexistent_or_ambiguous_opening_boundary_fails_closed(date):
    data=DATA.venues[0].model_dump(mode='json')
    data['hours']={'weekly':[{'days':[7],'open':'01:30','close':'04:00','closeDayOffset':0}],'exceptions':[]}
    venue=Venue.model_validate(data)
    assert rank_candidates([venue],request(start=date+'T02:30:00Z',end=date+'T03:00:00Z',bufferMinutes=0))==[]
