"""Authenticated catalog access to the active authored dataset."""
import math
import base64
import json
import hashlib
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from app.api.auth import authenticated

router = APIRouter(prefix="/api/v1/destinations", tags=["catalog"])


@router.get("")
async def destinations(request: Request, actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT destination, currency, timezone FROM datasets
            WHERE status = 'active' ORDER BY destination
        """))).mappings().all()
    return {"destinations": [dict(row) for row in rows]}


def distance_km(a, b, c, d):
    phi1, phi2 = math.radians(a), math.radians(c)
    delta_phi, delta_lng = phi2-phi1, math.radians(d-b)
    x = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lng/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, x))))


@router.get("/{destination}/venues")
async def venues(destination: str, request: Request, near: str | None = None,
                 radiusKm: float | None = Query(default=None, gt=0, le=20, allow_inf_nan=False),
                 limit: int = Query(default=25, ge=1, le=100), cursor: str | None = None,
                 tripId: UUID | None = None, actor=Depends(authenticated)):
    if len(destination) > 200:
        raise HTTPException(422, "Invalid destination")
    coordinates = None
    if near is not None:
        try:
            values = near.split(',')
            if len(values) != 2:
                raise ValueError()
            lat, lng = map(float, values)
            if not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180:
                raise ValueError()
            coordinates = (lat, lng)
        except ValueError:
            raise HTTPException(422, "Invalid near coordinates") from None
    elif radiusKm is not None:
        raise HTTPException(422, "radiusKm requires near")
    async with request.app.state.engine.connect() as conn:
        if tripId is not None:
            dataset=(await conn.execute(text('''SELECT d.id,d.version FROM trips t JOIN datasets d ON d.id=t.dataset_id
                JOIN memberships m ON m.trip_id=t.id WHERE t.id=:trip AND t.destination=:destination
                AND m.user_id=:uid AND m.status='active' '''),{'trip':tripId,'destination':destination,'uid':actor['user_id']})).mappings().first()
        else:
            dataset = (await conn.execute(text("SELECT id,version FROM datasets WHERE destination=:destination AND status='active'"),
                                      {"destination": destination})).mappings().first()
        if not dataset:
            raise HTTPException(404, "Destination unavailable")
        rows = (await conn.execute(text("""SELECT v.id,v.source_id,v.name,v.category,v.price_per_person_minor,v.currency,
            v.latitude,v.longitude,v.rating,v.description,v.hours,
            COALESCE(array_agg(t.tag ORDER BY t.tag) FILTER (WHERE t.tag IS NOT NULL),ARRAY[]::varchar[]) AS tags
            FROM venue_metadata v LEFT JOIN venue_dietary_tags t ON t.venue_id=v.id AND t.dataset_id=v.dataset_id
            WHERE v.dataset_id=:id GROUP BY v.id,v.dataset_id ORDER BY v.source_id"""), {"id": dataset["id"]})).mappings().all()
    fingerprint = hashlib.sha256(f"{dataset['id']}:{near}:{radiusKm}".encode()).hexdigest()
    after = ""
    if cursor:
        try:
            if len(cursor) > 512:
                raise ValueError()
            token = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if token['filter'] != fingerprint or not isinstance(token['after'], str):
                raise ValueError()
            after = token['after']
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise HTTPException(422, "Invalid cursor") from None
    output = []
    for row in rows:
        if row['source_id'] <= after:
            continue
        lat, lng = float(row['latitude']), float(row['longitude'])
        if coordinates and distance_km(*coordinates, lat, lng) > (radiusKm or 2) + 1e-6:
            continue
        amount = row['price_per_person_minor']
        output.append((row['source_id'], {"venueId":str(row['id']), "name":row['name'], "category":row['category'],
                       "pricePerPerson":f"{amount // 100}.{amount % 100:02d}", "dietaryTags":row['tags'],
                       "hours":row['hours'], "coordinates":{"lat":lat,"lng":lng},
                       "rating":float(row['rating']) if row['rating'] is not None else None,
                       "sourceId":f"venue:{row['source_id']}@{dataset['version']}"}))
    next_cursor = None
    if len(output) > limit:
        token = json.dumps({"filter": fingerprint, "after": output[limit-1][0]}).encode()
        next_cursor = base64.urlsafe_b64encode(token).decode()
    return {"destination": destination, "venues": [entry for _, entry in output[:limit]], "nextCursor": next_cursor}
