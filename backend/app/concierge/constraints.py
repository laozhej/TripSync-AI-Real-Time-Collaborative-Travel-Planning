"""Deterministic eligibility and ranking; no model or transport dependencies."""
from datetime import datetime, timedelta, timezone
import math
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, StrictInt, model_validator
from app.datasets.schema import Coordinates, Strict, Venue


def distance_km(a, b, c, d):
    phi1, phi2 = math.radians(a), math.radians(c)
    x = math.sin((phi2-phi1)/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(math.radians(d-b)/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, x))))


class Constraints(Strict):
    category: Literal['food', 'activity', 'lodging', 'transit']
    ceilingMinor: StrictInt = Field(gt=0, le=10**12)
    requiredDiets: set[Literal['vegetarian','vegan','halal','gluten-free']] = Field(default_factory=set)
    start: datetime
    end: datetime
    timezone: str
    bufferMinutes: StrictInt = Field(default=30, ge=0, le=1440)
    anchor: Coordinates | None = None
    radiusKm: float = Field(default=2, gt=0, le=20)

    @model_validator(mode='after')
    def valid_slot(self):
        try:
            ZoneInfo(self.timezone)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError('invalid destination timezone') from None
        if self.start.utcoffset() is None or self.end.utcoffset() is None or self.end <= self.start:
            raise ValueError('ordered offset-bearing times required')
        if self.end - self.start > timedelta(days=7):
            raise ValueError('slot too long')
        return self


def _utc(local, zone):
    # Unknown/ambiguous authored wall-clock boundaries fail closed.
    first, second = local.replace(tzinfo=zone, fold=0), local.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        return None
    value = first.astimezone(timezone.utc)
    return value if value.astimezone(zone).replace(tzinfo=None) == local else None


def fits_hours(venue, request):
    if venue.hours.exceptions:
        return False
    zone = ZoneInfo(request.timezone)
    start = request.start.astimezone(timezone.utc) - timedelta(minutes=request.bufferMinutes)
    end = request.end.astimezone(timezone.utc)
    day = start.astimezone(zone).date() - timedelta(days=1)
    last = end.astimezone(zone).date()
    while day <= last:
        for window in venue.hours.weekly:
            if day.isoweekday() not in window.days:
                continue
            opening = _utc(datetime.combine(day, window.open), zone)
            closing = _utc(datetime.combine(day + timedelta(days=window.closeDayOffset), window.close), zone)
            if opening is not None and closing is not None and opening <= start and end <= closing:
                return True
        day += timedelta(days=1)
    return False


def rank_candidates(venues: list[Venue], request: Constraints):
    """Filter before scoring. The caller resolves ceilings and attendee diet union."""
    valid = []
    for venue in venues:
        price = int(venue.pricePerPerson * 100)
        if venue.category != request.category or price > request.ceilingMinor:
            continue
        if not request.requiredDiets.issubset(venue.dietaryTags) or not fits_hours(venue, request):
            continue
        distance = None
        if request.anchor is not None:
            distance = distance_km(request.anchor.lat, request.anchor.lng, venue.coordinates.lat, venue.coordinates.lng)
            if distance > request.radiusKm + 1e-6:
                continue
        proximity = 1 if distance is None else max(0, 1-distance/request.radiusKm)
        score = .4*proximity + .3*(float(venue.rating or 0)/5) + .3*((request.ceilingMinor-price)/request.ceilingMinor)
        valid.append({'sourceId':venue.sourceId,'score':score,'distanceKm':distance,'priceMinor':price})
    return sorted(valid, key=lambda candidate: (-candidate['score'], candidate['sourceId']))
