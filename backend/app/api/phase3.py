"""Phase 3 HTTP adapters. Domain services are also used by the native gateway."""
import asyncio
import hashlib
import json
from uuid import UUID,uuid4
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,ValidationError
from sqlalchemy import text
from app.api.auth import authenticated
from app.realtime.rooms import RoomError,envelope
from app.voting.service import OpenVote,CastVote,open_vote,cast_vote,member
from app.recommendations.service import recommend,training
from app.datasets.schema import Dataset
from app.budget.service import SplitUpdate,update_split
from app.analytics.service import Finalize,finalize
from app.datasets.importer import insert_bundle,MAX_BYTES,_unique_pairs

router=APIRouter(prefix='/api/v1')
_ingest_lock=asyncio.Lock()
_training_lock=asyncio.Lock()

async def accessible(request,trip_id,actor):
    async with request.app.state.engine.connect() as conn:
        row=(await conn.execute(text('''SELECT t.* FROM trips t JOIN memberships m ON m.trip_id=t.id
            WHERE t.id=:trip AND m.user_id=:uid AND m.status='active' '''),{'trip':trip_id,'uid':actor['user_id']})).mappings().first()
    if not row:raise HTTPException(404,'Trip unavailable')
    return row

async def call_vote(request,trip_id,actor,command,service):
    await accessible(request,trip_id,actor)
    try:return await service(request.app.state.rooms.get(trip_id),actor,command)
    except RoomError as exc:
        raise HTTPException(404 if exc.code=='NOT_FOUND' else 403 if exc.code in ('FORBIDDEN','LEADER_DISCONNECTED') else 503 if exc.code=='PERSISTENCE_DEGRADED' else 409,{'code':exc.code,**(exc.details or {})}) from None

@router.post('/trips/{trip_id}/votes')
async def http_open(trip_id:UUID,command:OpenVote,request:Request,actor=Depends(authenticated)):
    return await call_vote(request,trip_id,actor,command,open_vote)

@router.post('/trips/{trip_id}/votes/cast')
async def http_cast(trip_id:UUID,command:CastVote,request:Request,actor=Depends(authenticated)):
    return await call_vote(request,trip_id,actor,command,cast_vote)

@router.post('/trips/{trip_id}/items/split')
async def split_item(trip_id:UUID,command:SplitUpdate,request:Request,actor=Depends(authenticated)):
    return await call_vote(request,trip_id,actor,command,update_split)

@router.get('/trips/{trip_id}/planning')
async def planning(trip_id:UUID,request:Request,actor=Depends(authenticated)):
    await accessible(request,trip_id,actor);room=request.app.state.rooms.get(trip_id);await room.load()
    async with room.lock:return await room.snapshot_locked(actor)

@router.get('/me/dashboard')
async def dashboard(request:Request,actor=Depends(authenticated)):
    async with request.app.state.engine.connect() as conn:
        rows=(await conn.execute(text('''SELECT t.id,t.destination,t.start_date,t.end_date,t.status,t.currency,m.role,m.constraints
            FROM trips t JOIN memberships m ON m.trip_id=t.id WHERE m.user_id=:uid AND m.status='active' ORDER BY t.created_at DESC'''),{'uid':actor['user_id']})).mappings().all()
        profile=(await conn.execute(text('''SELECT v.category,count(*) AS interactions FROM interactions i
            JOIN venue_metadata v ON v.id=i.venue_id AND v.dataset_id=i.dataset_id WHERE i.user_id=:uid
            AND EXISTS(SELECT 1 FROM memberships m WHERE m.trip_id=i.trip_id AND m.user_id=i.user_id AND m.status='active')
            GROUP BY v.category ORDER BY interactions DESC,v.category'''),{'uid':actor['user_id']})).mappings().all()
        ranges=(await conn.execute(text('''SELECT v.currency,min(v.price_per_person_minor) AS minimum_minor,
            max(v.price_per_person_minor) AS maximum_minor FROM interactions i
            JOIN venue_metadata v ON v.id=i.venue_id AND v.dataset_id=i.dataset_id
            JOIN memberships m ON m.trip_id=i.trip_id AND m.user_id=i.user_id AND m.status='active'
            WHERE i.user_id=:uid GROUP BY v.currency ORDER BY v.currency'''),{'uid':actor['user_id']})).mappings().all()
    return {'trips':[{'tripId':str(r['id']),'destination':r['destination'],'startDate':r['start_date'],'endDate':r['end_date'],
        'status':r['status'],'currency':r['currency'],'role':r['role'],'preferences':r['constraints'],'canRejoin':r['status']!='finalized'} for r in rows],
        'derivedPreferences':[dict(r) for r in profile],
        'dietaryTags':sorted({tag for r in rows for tag in r['constraints'].get('dietaryTags',[])}),
        'budgetRanges':[{'currency':r['currency'],'minimumMinor':r['minimum_minor'],'maximumMinor':r['maximum_minor']} for r in ranges]}

@router.get('/trips/{trip_id}/budgets')
async def budgets(trip_id:UUID,request:Request,actor=Depends(authenticated)):
    state=await planning(trip_id,request,actor)
    return state['budgets']|{'roomSeq':state['roomSeq'],'committedSeq':state['committedSeq']}

@router.get('/trips/{trip_id}/conflicts')
async def conflicts(trip_id:UUID,request:Request,actor=Depends(authenticated)):
    return {'items':(await planning(trip_id,request,actor))['conflicts']}

@router.get('/trips/{trip_id}/votes/{vote_id}')
async def vote_detail(trip_id:UUID,vote_id:UUID,request:Request,actor=Depends(authenticated)):
    state=await planning(trip_id,request,actor)
    vote=next((v for v in state['votes'] if v['voteId']==str(vote_id)),None)
    if not vote:raise HTTPException(404,'Vote unavailable')
    return vote

@router.get('/trips/{trip_id}/recommendations')
async def recommendations(trip_id:UUID,request:Request,actor=Depends(authenticated)):
    trip=await accessible(request,trip_id,actor)
    async with request.app.state.engine.connect() as conn:return await recommend(conn,trip,actor['user_id'])

class Interaction(BaseModel):
    model_config=ConfigDict(extra='forbid')
    venueId:UUID
    kind:Literal['view','like']
    eventId:UUID

@router.post('/trips/{trip_id}/interactions',status_code=201)
async def interaction(trip_id:UUID,body:Interaction,request:Request,actor=Depends(authenticated)):
    trip=await accessible(request,trip_id,actor)
    async with request.app.state.engine.begin() as conn:
        prior=(await conn.execute(text('SELECT user_id,trip_id,venue_id,kind FROM interactions WHERE event_id=:event'),{'event':body.eventId})).mappings().first()
        if prior:
            if (prior['user_id'],prior['trip_id'],prior['venue_id'],prior['kind'])!=(actor['user_id'],trip_id,body.venueId,body.kind):raise HTTPException(409,'Event ID reused')
            return {'status':'duplicate'}
        exists=(await conn.execute(text('SELECT 1 FROM venue_metadata WHERE id=:id AND dataset_id=:dataset'),{'id':body.venueId,'dataset':trip['dataset_id']})).first()
        if not exists:raise HTTPException(422,'Venue unavailable in pinned dataset')
        await conn.execute(text('''INSERT INTO interactions(id,user_id,trip_id,venue_id,dataset_id,kind,event_id)
            VALUES(:id,:uid,:trip,:venue,:dataset,:kind,:event)'''),{'id':uuid4(),'uid':actor['user_id'],'trip':trip_id,'venue':body.venueId,'dataset':trip['dataset_id'],'kind':body.kind,'event':body.eventId})
    request.app.state.rooms.get(trip_id).publish(envelope('trip.recommendations.updated',trip_id,{}))
    return {'status':'recorded'}

@router.post('/trips/{trip_id}/recommendations/train')
async def train_model(trip_id:UUID,request:Request,actor=Depends(authenticated)):
    trip=await accessible(request,trip_id,actor)
    if not actor['is_admin']:raise HTTPException(403,'Admin required')
    async with _training_lock:result=await training(request.app.state.engine,trip['dataset_id'])
    request.app.state.rooms.get(trip_id).publish(envelope('trip.recommendations.updated',trip_id,result))
    return result

@router.post('/trips/{trip_id}/finalize')
async def finalize_trip(trip_id:UUID,command:Finalize,request:Request,actor=Depends(authenticated)):
    return await call_vote(request,trip_id,actor,command,finalize)

@router.get('/trips/{trip_id}/analytics')
async def analytics(trip_id:UUID,request:Request,actor=Depends(authenticated)):
    await accessible(request,trip_id,actor);room=request.app.state.rooms.get(trip_id);await room.load()
    async with room.lock:
        await room.flush_locked()
        if room.frozen:raise HTTPException(503,'Room persistence unavailable')
        async with request.app.state.engine.connect() as conn:
            events=(await conn.execute(text('SELECT type,payload,occurred_at FROM room_events WHERE trip_id=:trip ORDER BY room_seq'),{'trip':trip_id})).mappings().all()
            changes=(await conn.execute(text('SELECT status,count(*) AS count FROM conflict_changes WHERE trip_id=:trip GROUP BY status'),{'trip':trip_id})).mappings().all()
            presence=(await conn.execute(text('SELECT connected_planners,occurred_at FROM presence_ledger WHERE session_id=:session ORDER BY occurred_at'),{'session':UUID(room.session_id)})).mappings().all()
        counts={r['status']:r['count'] for r in changes}
        peak=max((e['connected_planners'] for e in presence),default=0)
        async with request.app.state.engine.connect() as conn:
            boundary=(await conn.execute(text('SELECT started_at,ended_at,now() AS as_of FROM session_boundaries WHERE trip_id=:trip'),{'trip':trip_id})).mappings().first()
        duration=(boundary['ended_at'] or boundary['as_of'])-boundary['started_at'] if boundary else None
        return {'sessionId':room.session_id,'throughSeq':room.committed,'sessionDurationSeconds':max(0,duration.total_seconds()) if duration else 0,'sessionStartedAt':boundary['started_at'] if boundary else None,'sessionEndedAt':boundary['ended_at'] if boundary else None,'durationKnown':bool(boundary),
            'peakPlanners':peak,'aiCount':sum(e['type']=='trip.ai.suggestion' for e in events),
            'conflictsFlagged':counts.get('open',0),'conflictsResolved':counts.get('resolved',0),
            'finalBudgets':room.budget_summary(room.currency),'ledgerEventCount':len(events)}

@router.post('/admin/datasets',status_code=201)
async def upload(request:Request,actor=Depends(authenticated)):
    if not actor['is_admin']:raise HTTPException(403,'Admin required')
    raw=bytearray()
    async for part in request.stream():
        raw.extend(part)
        if len(raw)>MAX_BYTES:raise HTTPException(413,'Dataset exceeds 2 MiB')
    try:
        data=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        dataset=Dataset.model_validate(data)
    except ValidationError as exc:
        fields=['.'.join(str(part) for part in e['loc'])+' ('+e['type']+')' for e in exc.errors(include_input=False)[:20]]
        raise HTTPException(422,'Invalid dataset fields: '+'; '.join(fields)) from None
    except (ValueError,UnicodeError):raise HTTPException(422,'Invalid dataset: check JSON encoding, duplicate keys and finite numbers') from None
    checksum=hashlib.sha256(raw).hexdigest()
    async with _ingest_lock:
        async with request.app.state.engine.begin() as conn:
            duplicate=(await conn.execute(text('SELECT id FROM datasets WHERE destination=:destination AND checksum=:checksum'),{'destination':dataset.destination,'checksum':checksum})).scalar_one_or_none()
            if duplicate:return {'datasetId':str(duplicate),'status':'duplicate'}
            version=(await conn.execute(text('SELECT COALESCE(max(version),0)+1 FROM datasets WHERE destination=:destination'),{'destination':dataset.destination})).scalar_one()
            dataset_id=uuid4();await insert_bundle(conn,dataset,checksum,dataset_id,version,'staging')
    return {'datasetId':str(dataset_id),'version':version,'status':'staging'}

@router.get('/admin/datasets')
async def datasets(request:Request,actor=Depends(authenticated)):
    if not actor['is_admin']:raise HTTPException(403,'Admin required')
    async with request.app.state.engine.connect() as conn:
        rows=(await conn.execute(text('SELECT id,destination,version,status,checksum FROM datasets ORDER BY destination,version'))).mappings().all()
    return {'items':[dict(r)|{'datasetId':str(r['id'])} for r in rows]}

@router.post('/admin/datasets/{dataset_id}/activate')
async def activate(dataset_id:UUID,request:Request,actor=Depends(authenticated)):
    if not actor['is_admin']:raise HTTPException(403,'Admin required')
    async with _ingest_lock:
        async with request.app.state.engine.begin() as conn:
            row=(await conn.execute(text('SELECT destination,status FROM datasets WHERE id=:id'),{'id':dataset_id})).mappings().first()
            if not row:raise HTTPException(404,'Dataset unavailable')
            if row['status']=='retired':raise HTTPException(409,'Retired versions cannot be reactivated')
            await conn.execute(text("UPDATE datasets SET status='retired' WHERE destination=:destination AND status='active' AND id<>:id"),{'destination':row['destination'],'id':dataset_id})
            await conn.execute(text("UPDATE datasets SET status='active' WHERE id=:id"),{'id':dataset_id})
    return {'datasetId':str(dataset_id),'status':'active'}
