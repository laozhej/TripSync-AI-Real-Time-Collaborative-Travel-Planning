"""Authorized trip-context resolution and idempotent grounded Concierge requests."""
import asyncio
import anyio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.datasets.schema import Venue
from app.concierge.constraints import Constraints, rank_candidates
from app.concierge.preferences import Category, Preferences
from app.concierge.rag import answer_from_model, render
from app.realtime.rooms import RoomError, envelope


class Ask(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    question: str=Field(min_length=1,max_length=4000)
    category: Category | None=None
    startTime: datetime | None=None
    endTime: datetime | None=None
    attendeeIds: list[UUID]=Field(default_factory=list,max_length=50)
    anchorItemId: UUID | None=None
    ceilingMinor: StrictInt | None=Field(default=None,gt=0,le=10**12)
    radiusKm: float=Field(default=2,gt=0,le=20)
    bufferMinutes: StrictInt=Field(default=30,ge=0,le=1440)

    @field_validator('question')
    @classmethod
    def safe_question(cls,value):
        if not value.strip() or '\x00' in value: raise ValueError('invalid question')
        try: value.encode('utf-8')
        except UnicodeEncodeError: raise ValueError('invalid question') from None
        return value

    @model_validator(mode='after')
    def valid_times(self):
        if len(self.attendeeIds)!=len(set(self.attendeeIds)): raise ValueError('duplicate attendees')
        for time in (self.startTime,self.endTime):
            if time is not None and time.utcoffset() is None: raise ValueError('offset-bearing times required')
        if self.startTime is not None and self.endTime is not None and self.endTime<=self.startTime:
            raise ValueError('ordered times required')
        return self


@asynccontextmanager
async def question_lock(room,key):
    async with room.lock:
        state=room.ai_locks.setdefault(key,{'lock':asyncio.Lock(),'users':0})
        state['users']+=1
    try:
        async with state['lock']: yield
    finally:
        with anyio.CancelScope(shield=True):
            async with room.lock:
                state['users']-=1
                if state['users']==0: room.ai_locks.pop(key,None)


async def member_trip(conn,room,actor):
    row=(await conn.execute(text('''SELECT t.dataset_id,t.currency,t.timezone,t.start_date,t.end_date,t.status,t.planning_session_id,
        t.category_ceilings,m.constraints,d.version FROM trips t JOIN memberships m ON m.trip_id=t.id
        JOIN auth_sessions s ON s.user_id=m.user_id JOIN datasets d ON d.id=t.dataset_id
        WHERE t.id=:trip AND m.user_id=:uid AND m.status='active' AND s.id=:session
        AND s.revoked_at IS NULL AND s.expires_at>now()'''),
        {'trip':room.trip_id,'uid':actor['user_id'],'session':actor['session_id']})).mappings().first()
    if not row: raise RoomError('NOT_FOUND')
    if row['status']=='finalized': raise RoomError('FORBIDDEN')
    return row


async def capture(room,actor,request,key,fingerprint):
    async with room.lock:
        if room.frozen: raise RoomError('PERSISTENCE_DEGRADED')
        async with room.manager.engine.connect() as conn:
            trip=await member_trip(conn,room,actor)
            prior=(await conn.execute(text('SELECT command_hash,response FROM ai_questions WHERE trip_id=:trip AND user_id=:uid AND request_key=:key'),
                {'trip':room.trip_id,'uid':actor['user_id'],'key':key})).mappings().first()
            if prior:
                if prior['command_hash']!=fingerprint: raise RoomError('COMMAND_ID_REUSE')
                return {'cached':prior['response']}
            result={'seq':room.seq,'version':trip['version'],'choices':[]}
            missing=[field for field,value in [('category',request.category),('startTime',request.startTime),('endTime',request.endTime)] if value is None]
            prefs=Preferences.model_validate(trip['constraints'])
            ceiling=prefs.categoryCeilingsMinor.get(request.category,trip['category_ceilings'].get(request.category))
            if ceiling is None: missing.append('configuredCategoryCeiling')
            if missing:
                result['early']={'status':'needs_clarification','requiredFields':missing,
                    'answer':'Provide the requested slot and configure a per-person category ceiling.','suggestedVenueId':None,'sourceEvents':[]}
                return result
            if request.ceilingMinor is not None: ceiling=min(ceiling,request.ceilingMinor)
            zone=ZoneInfo(trip['timezone'])
            if request.startTime.astimezone(zone).date()<trip['start_date'] or (request.endTime-timedelta(microseconds=1)).astimezone(zone).date()>trip['end_date']:
                raise RoomError('INVALID_TIME')
            attendees=(await conn.execute(text("SELECT user_id,constraints FROM memberships WHERE trip_id=:trip AND status='active'"),{'trip':room.trip_id})).mappings().all()
            members={row['user_id']:row for row in attendees}
            ids=request.attendeeIds or list(members)
            if any(uid not in members for uid in ids): raise RoomError('INVALID_ATTENDEES')
            diets=set()
            for uid in ids: diets.update(Preferences.model_validate(members[uid]['constraints']).dietaryTags)
            rows=(await conn.execute(text('''SELECT v.*,COALESCE(array_agg(t.tag) FILTER (WHERE t.tag IS NOT NULL),ARRAY[]::varchar[]) AS tags
                FROM venue_metadata v LEFT JOIN venue_dietary_tags t ON t.venue_id=v.id AND t.dataset_id=v.dataset_id
                WHERE v.dataset_id=:dataset GROUP BY v.id,v.dataset_id'''),{'dataset':trip['dataset_id']})).mappings().all()
            venues={}
            for row in rows:
                try:
                    venue=Venue.model_validate({'sourceId':row['source_id'],'name':row['name'],'category':row['category'],
                        'pricePerPerson':str(Decimal(row['price_per_person_minor'])/100),'dietaryTags':row['tags'],
                        'coordinates':{'lat':float(row['latitude']),'lng':float(row['longitude'])},'rating':row['rating'],
                        'description':row['description'],'hours':row['hours']})
                except (ValidationError,ValueError,TypeError):
                    continue
                venues[venue.sourceId]=(venue,str(row['id']))
            anchor=None
            if request.anchorItemId is not None:
                item=room.items.get(str(request.anchorItemId))
                if item is None: raise RoomError('INVALID_ANCHOR')
                anchored=next((venue for venue,vid in venues.values() if vid==item['venueId']),None)
                if anchored is None: raise RoomError('INVALID_ANCHOR')
                anchor=anchored.coordinates
            try:
                rules=Constraints(category=request.category,ceilingMinor=ceiling,requiredDiets=diets,start=request.startTime,
                    end=request.endTime,timezone=trip['timezone'],anchor=anchor,radiusKm=request.radiusKm,bufferMinutes=request.bufferMinutes)
            except ValidationError:
                raise RoomError('INVALID_CONSTRAINTS') from None
            ranked=rank_candidates([v for v,_ in venues.values()],rules)
            if ranked:
                valid_ids=[candidate['sourceId'] for candidate in ranked]
                hits=(await conn.execute(text('''SELECT source_id FROM venue_metadata WHERE dataset_id=:dataset AND source_id=ANY(:ids)
                    AND search_vector @@ plainto_tsquery('english',:question)'''),
                    {'dataset':trip['dataset_id'],'ids':valid_ids,'question':request.question})).scalars().all()
                if hits: ranked=[candidate for candidate in ranked if candidate['sourceId'] in hits]
            result['choices']=[{'venue':venues[c['sourceId']][0],'venueId':venues[c['sourceId']][1],'score':c['score'],'currency':trip['currency']} for c in ranked[:5]]
            return result


async def ask(room,actor,request,key,client):
    await room.load()
    room.audit('trip.ai.requested',key)
    fingerprint=hashlib.sha256(request.model_dump_json().encode()).hexdigest()
    async with question_lock(room,(actor['user_id'],key)):
        for attempt in range(2):
            try:
                context=await capture(room,actor,request,key,fingerprint)
            except (SQLAlchemyError,OSError):
                async with room.lock: room.fail_locked()
                raise RoomError('PERSISTENCE_DEGRADED') from None
            if 'cached' in context:
                room.audit('trip.ai.replayed',key)
                return context['cached']
            if 'early' in context:
                answer=context['early']
            elif not context['choices']:
                answer=await answer_from_model([],request.question,context['version'],client)
            elif room.manager.model_gate.locked() and context['choices']:
                answer=render(context['choices'][0],context['version'],'grounded_fallback')
            else:
                async with room.manager.model_gate:
                    answer=await answer_from_model(context['choices'],request.question,context['version'],client)
            async with room.lock:
                if room.seq!=context['seq']:
                    if attempt==0: continue
                    answer={'status':'stale_context','answer':'The trip changed during this request. Review the current plan and ask again.',
                            'suggestedVenueId':None,'sourceEvents':[]}
                seq=room.seq+1
                response=answer | {'questionId':str(uuid4()),'userId':str(actor['user_id']),
                    'datasetVersion':context['version'],'basedOnSeq':context['seq'],'roomSeq':seq,'roomEpoch':room.epoch,
                    'generatedAt':datetime.now(timezone.utc).isoformat(),'eventId':str(uuid4()),'correlationId':str(key),'durable':True}
                async with room.transaction_locked() as conn:
                    trip=await member_trip(conn,room,actor)
                    result=await conn.execute(text('UPDATE trips SET room_seq=:seq,committed_seq=:seq WHERE id=:trip AND committed_seq=:base RETURNING id'),
                        {'trip':room.trip_id,'seq':seq,'base':room.seq})
                    if not result.first(): raise RuntimeError('durable Concierge sequence mismatch')
                    await conn.execute(text('''INSERT INTO ai_questions (id,trip_id,user_id,request_key,command_hash,response)
                        VALUES (:id,:trip,:uid,:key,:hash,CAST(:response AS jsonb))'''),
                        {'id':UUID(response['questionId']),'trip':room.trip_id,'uid':actor['user_id'],'key':key,'hash':fingerprint,'response':json.dumps(response)})
                    await conn.execute(text('''INSERT INTO room_events (trip_id,room_seq,event_id,session_id,actor_id,type,payload)
                        VALUES (:trip,:seq,:event,:session,:actor,'trip.ai.suggestion',CAST(:payload AS jsonb))'''),
                        {'trip':room.trip_id,'seq':seq,'event':UUID(response['eventId']),'session':trip['planning_session_id'],
                         'actor':actor['user_id'],'payload':json.dumps(response)})
                room.seq=room.committed=seq
                room.publish(envelope('trip.ai.suggestion',room.trip_id,response))
                room.audit('trip.ai.'+response['status'],key)
                return response
