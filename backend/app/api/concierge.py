"""Member-authorized Concierge and constraints APIs."""
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text
from app.api.auth import authenticated
from app.concierge.preferences import ConstraintsUpdate, update_constraints
from app.concierge.service import Ask, ask
from app.realtime.rooms import RoomError

router=APIRouter(prefix='/api/v1/trips',tags=['concierge'])


async def require_member(conn,trip_id,actor):
    row=(await conn.execute(text("SELECT 1 FROM memberships WHERE trip_id=:trip AND user_id=:uid AND status='active'"),
        {'trip':trip_id,'uid':actor['user_id']})).first()
    if not row: raise HTTPException(404,'Trip unavailable')


def domain_error(exc):
    status=404 if exc.code=='NOT_FOUND' else 403 if exc.code=='FORBIDDEN' else 503 if exc.code in ('PERSISTENCE_DEGRADED','ROOM_BACKPRESSURE') else 409 if exc.code in ('COMMAND_ID_REUSE','STALE_STATE_VERSION','LEADER_DISCONNECTED') else 422
    return HTTPException(status,{'code':exc.code,**(exc.details or {})})


@router.post('/{trip_id}/constraints')
async def constraints(trip_id:UUID,command:ConstraintsUpdate,request:Request,actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn: await require_member(conn,trip_id,actor)
    try:
        return await update_constraints(request.app.state.rooms.get(trip_id),actor,command)
    except RoomError as exc: raise domain_error(exc) from None


@router.post('/{trip_id}/ai/ask')
async def ask_question(trip_id:UUID,body:Ask,request:Request,
                       key:UUID=Header(alias='Idempotency-Key'),actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn: await require_member(conn,trip_id,actor)
    try:
        return await ask(request.app.state.rooms.get(trip_id),actor,body,key,request.app.state.model_client)
    except RoomError as exc:
        request.app.state.rooms.get(trip_id).audit('trip.ai.rejected',key)
        raise domain_error(exc) from None


@router.get('/{trip_id}/ai/sources/{citation}')
async def source(trip_id:UUID,citation:str,request:Request,actor=Depends(authenticated)):
    match=re.fullmatch(r'venue:([A-Za-z0-9_-]{1,80})@([1-9][0-9]{0,8})',citation)
    if not match: raise HTTPException(422,'Invalid source identifier')
    async with request.app.state.engine.connect() as conn:
        await require_member(conn,trip_id,actor)
        row=(await conn.execute(text('''SELECT v.name,v.category,v.price_per_person_minor,v.currency,v.description,v.hours,v.latitude,v.longitude,
            COALESCE(array_agg(tags.tag) FILTER (WHERE tags.tag IS NOT NULL),ARRAY[]::varchar[]) AS diets
            FROM trips t JOIN datasets d ON d.id=t.dataset_id JOIN venue_metadata v ON v.dataset_id=d.id
            LEFT JOIN venue_dietary_tags tags ON tags.venue_id=v.id AND tags.dataset_id=v.dataset_id
            WHERE t.id=:trip AND d.version=:version AND v.source_id=:source GROUP BY v.id,v.dataset_id'''),
            {'trip':trip_id,'version':int(match[2]),'source':match[1]})).mappings().first()
    if not row: raise HTTPException(404,'Source unavailable for this trip version')
    return {'sourceId':citation,'name':row['name'],'category':row['category'],'currency':row['currency'],
            'pricePerPersonMinor':row['price_per_person_minor'],'dietaryTags':sorted(row['diets']),
            'hours':row['hours'],'coordinates':{'lat':float(row['latitude']),'lng':float(row['longitude'])},
            'description':row['description'],'synthetic':True}
