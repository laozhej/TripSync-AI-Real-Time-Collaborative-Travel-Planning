"""Elections share the room lock, conditional versions and durable transaction."""
import hashlib
import json
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid4
from typing import Annotated
from pydantic import BaseModel,ConfigDict,Field,StrictInt
from sqlalchemy import text
from app.board.lifecycle import begin_voting,resolve_voting,BoardConflict,BoardInvalid,BoardForbidden
from app.realtime.rooms import RoomError,envelope
from app.budget.engine import summarize
from app.concierge.conflicts import detect
from app.voting.rules import choose_winner

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid')
    commandId:UUID
    correlationId:UUID

class OpenVote(Command):
    expectedVersions:dict[UUID,Annotated[StrictInt,Field(ge=1)]]=Field(min_length=2,max_length=50)
    durationSeconds:StrictInt=Field(default=60,ge=10,le=300)

class CastVote(Command):
    voteId:UUID
    choiceVenueId:UUID
    expectedBallotVersion:StrictInt=Field(ge=0)

def slot_key(items):
    first=items[0]
    return hashlib.sha256(json.dumps([first['dayIndex'],first['startTime'],first['endTime'],sorted(first['attendeeIds'])]).encode()).hexdigest()

async def member(conn,room,actor):
    row=(await conn.execute(text('''SELECT m.role,m.can_pin,t.status,t.room_locked FROM memberships m
        JOIN trips t ON t.id=m.trip_id JOIN auth_sessions s ON s.user_id=m.user_id
        WHERE m.trip_id=:trip AND m.user_id=:uid AND m.status='active'
        AND s.id=:sid AND s.revoked_at IS NULL AND s.expires_at>now()'''),
        {'trip':room.trip_id,'uid':actor['user_id'],'sid':actor['session_id']})).mappings().first()
    if not row:raise RoomError('NOT_FOUND')
    return row

async def load_votes(conn,trip_id):
    rows=(await conn.execute(text('SELECT id,status,closes_at,data FROM votes WHERE trip_id=:trip ORDER BY created_at,id'),{'trip':trip_id})).mappings().all()
    result=[]
    for row in rows:
        ballots=(await conn.execute(text('''SELECT b.user_id,b.choice_item_id,b.version FROM ballots b
            JOIN memberships m ON m.user_id=b.user_id AND m.trip_id=:trip
            WHERE b.vote_id=:vote AND (m.status='active' OR :closed) ORDER BY b.user_id'''),{'trip':trip_id,'vote':row['id'],'closed':row['status']!='open'})).mappings().all()
        result.append(row['data']|{'voteId':str(row['id']),'status':row['status'],'closesAt':row['closes_at'].isoformat(),
            'ballots':[{'userId':str(b['user_id']),'choiceItemId':str(b['choice_item_id']),'version':b['version']} for b in ballots]})
    return result

async def sync_conflicts(conn,room,items=None,votes=None,seq=None):
    items=room.items if items is None else items
    votes=room.votes if votes is None else votes
    seq=room.seq if seq is None else seq
    trip=(await conn.execute(text('SELECT total_budget_minor,currency FROM trips WHERE id=:trip'),{'trip':room.trip_id})).mappings().one()
    members=(await conn.execute(text('SELECT user_id,constraints FROM memberships WHERE trip_id=:trip'),{'trip':room.trip_id})).mappings().all()
    ceilings={str(m['user_id']):m['constraints'].get('totalCeilingMinor') for m in members}
    current=detect(list(items.values()),summarize(items.values(),trip['currency'],votes),trip['total_budget_minor'],ceilings)
    old=(await conn.execute(text('SELECT fingerprint,status FROM conflicts WHERE trip_id=:trip'),{'trip':room.trip_id})).mappings().all()
    states={r['fingerprint']:r['status'] for r in old}
    for key in set(states)|set(current):
        status='open' if key in current else 'resolved'
        if states.get(key)==status:
            if key in current:await conn.execute(text('UPDATE conflicts SET data=CAST(:data AS jsonb) WHERE trip_id=:trip AND fingerprint=:key'),{'data':json.dumps(current[key]),'trip':room.trip_id,'key':key})
            continue
        if status=='open':
            await conn.execute(text('''INSERT INTO conflicts(trip_id,fingerprint,status,data,opened_seq)
                VALUES(:trip,:key,'open',CAST(:data AS jsonb),:seq) ON CONFLICT(trip_id,fingerprint)
                DO UPDATE SET status='open',data=EXCLUDED.data,opened_seq=EXCLUDED.opened_seq,resolved_seq=NULL'''),
                {'trip':room.trip_id,'key':key,'seq':seq,'data':json.dumps(current[key])})
        else:await conn.execute(text("UPDATE conflicts SET status='resolved',resolved_seq=:seq WHERE trip_id=:trip AND fingerprint=:key"),{'trip':room.trip_id,'key':key,'seq':seq})
        await conn.execute(text('INSERT INTO conflict_changes VALUES(:trip,:seq,:key,:status) ON CONFLICT DO NOTHING'),{'trip':room.trip_id,'seq':seq,'key':key,'status':status})
        details=current.get(key)
        if details is None:
            details=(await conn.execute(text('SELECT data FROM conflicts WHERE trip_id=:trip AND fingerprint=:key'),{'trip':room.trip_id,'key':key})).scalar_one()
        conn.info.setdefault('conflict_notifications',[]).append({'fingerprint':key,'conflictType':details['type'],
            'itemIds':details['itemIds'],'details':details['details'],'status':status,'roomSeq':seq,'roomEpoch':room.epoch,'durable':True})

async def write_event(conn,room,event,payload,command=None,actor=None,fingerprint=None):
    seq=room.seq+1
    result=await conn.execute(text('UPDATE trips SET room_seq=:seq,committed_seq=:seq WHERE id=:trip AND committed_seq=:base RETURNING id'),{'seq':seq,'trip':room.trip_id,'base':room.seq})
    if not result.first():raise RuntimeError('durable sequence mismatch')
    payload=payload|{'roomSeq':seq,'roomEpoch':room.epoch,'durable':True,'commandId':str(command.commandId) if command else None,'eventId':str(uuid4())}
    await conn.execute(text('''INSERT INTO room_events(trip_id,room_seq,event_id,command_id,session_id,actor_id,type,payload)
        VALUES(:trip,:seq,:event,:command,:session,:actor,:type,CAST(:payload AS jsonb))'''),
        {'trip':room.trip_id,'seq':seq,'event':UUID(payload['eventId']),'command':command.commandId if command else None,
         'session':UUID(room.session_id),'actor':actor['user_id'] if actor else None,'type':event,'payload':json.dumps(payload|{'commandHash':fingerprint})})
    return payload

async def prior(conn,room,actor,command,fingerprint):
    found=(await conn.execute(text('SELECT actor_id,payload FROM room_events WHERE trip_id=:trip AND command_id=:cmd'),{'trip':room.trip_id,'cmd':command.commandId})).mappings().first()
    if found:
        if found['actor_id']!=actor['user_id'] or found['payload'].get('commandHash')!=fingerprint:raise RoomError('COMMAND_ID_REUSE')
        return found['payload']|{'status':'duplicate','committedSeq':room.committed}

async def save_items(conn,room,old,new,archived=()):
    for i in list(new)+list(archived):
        result=await conn.execute(text('''UPDATE itinerary_items SET lifecycle_stage=:stage,position_version=:version,
            removed_at=CASE WHEN :removed THEN now() ELSE NULL END WHERE trip_id=:trip AND id=:id AND position_version=:base RETURNING id'''),
            {'stage':i['lifecycleStage'],'version':i['positionVersion'],'removed':i in archived,'trip':room.trip_id,'id':UUID(i['itemId']),'base':old[i['itemId']]['positionVersion']})
        if not result.first():raise RuntimeError('durable item mismatch')

async def open_locked(room,command=None,actor=None,options=None):
    versions={str(k):v for k,v in command.expectedVersions.items()} if command else {i['itemId']:i['positionVersion'] for i in options}
    items=[room.items[k] for k in versions if k in room.items]
    if len(items)!=len(versions):raise RoomError('NOT_FOUND')
    try:changed=begin_voting(items,versions)
    except BoardConflict as exc:raise RoomError('STALE_POSITION_VERSION',{'commandId':str(command.commandId) if command else None,'itemId':exc.current_item['itemId'],'currentPositionVersion':exc.current_item['positionVersion'],'expectedPositionVersion':versions[exc.current_item['itemId']],'currentItem':exc.current_item,'roomSeq':room.seq}) from None
    except (BoardInvalid,BoardForbidden):raise RoomError('INVALID_VOTE') from None
    key=slot_key(items); vote_id=uuid4(); fingerprint=hashlib.sha256(command.model_dump_json().encode()).hexdigest() if command else None
    async with room.transaction_locked() as conn:
        if actor:
            m=await member(conn,room,actor)
            duplicate=await prior(conn,room,actor,command,fingerprint)
            if duplicate:return duplicate
            if m['role']!='leader' or m['room_locked'] or m['status']=='finalized':raise RoomError('FORBIDDEN')
            if not any(a['user_id']==actor['user_id'] for a in room.connections.values()):raise RoomError('LEADER_DISCONNECTED')
        if (await conn.execute(text("SELECT 1 FROM votes WHERE trip_id=:trip AND slot_key=:key AND status='open'"),{'trip':room.trip_id,'key':key})).first():raise RoomError('VOTE_ALREADY_OPENED')
        eligible=(await conn.execute(text("SELECT user_id FROM memberships WHERE trip_id=:trip AND status='active' AND role IN ('leader','planner') ORDER BY user_id"),{'trip':room.trip_id})).scalars().all()
        closes=datetime.now(timezone.utc)+timedelta(seconds=command.durationSeconds if command else 60)
        vote={'voteId':str(vote_id),'optionIds':list(versions),'options':[{'itemId':i['itemId'],'venueId':i['venueId'],'name':i['name']} for i in items],
              'eligibleUserIds':[str(u) for u in eligible],'status':'open','closesAt':closes.isoformat(),'ballots':[],'openedBy':'leader' if actor else 'system'}
        await conn.execute(text("INSERT INTO votes(id,trip_id,slot_key,status,closes_at,data) VALUES(:id,:trip,:key,'open',:closes,CAST(:data AS jsonb))"),{'id':vote_id,'trip':room.trip_id,'key':key,'closes':closes,'data':json.dumps(vote)})
        await save_items(conn,room,room.items,changed)
        next_items=room.items|{i['itemId']:i for i in changed}; next_votes=room.votes+[vote]
        await sync_conflicts(conn,room,next_items,next_votes,room.seq+1)
        payload=await write_event(conn,room,'trip.vote.open',{'itemId':items[0]['itemId'],'candidateVenueIds':[i['venueId'] for i in items],'closesAt':vote['closesAt'],'voteId':vote['voteId'],'vote':vote,'affectedItems':changed,'budgetSummary':summarize(next_items.values(),room.currency,next_votes)},command,actor,fingerprint)
    room.items=next_items;room.votes=next_votes;room.seq=room.committed=payload['roomSeq']
    room.publish(envelope('trip.vote.open',room.trip_id,payload));return payload

async def open_vote(room,actor,command):
    await room.load()
    async with room.lock:
        # Replay must be checked before lifecycle validation, including after resolution.
        async with room.manager.engine.connect() as conn:
            await member(conn,room,actor)
            duplicate=await prior(conn,room,actor,command,hashlib.sha256(command.model_dump_json().encode()).hexdigest())
            if duplicate:return duplicate
        return await open_locked(room,command,actor)

async def cast_vote(room,actor,command):
    await room.load()
    fingerprint=hashlib.sha256(command.model_dump_json().encode()).hexdigest()
    async with room.lock:
        received=datetime.now(timezone.utc)
        async with room.transaction_locked() as conn:
            m=await member(conn,room,actor)
            duplicate=await prior(conn,room,actor,command,fingerprint)
            if duplicate:return duplicate
            if m['role'] not in ('leader','planner') or m['room_locked'] or m['status']=='finalized':raise RoomError('FORBIDDEN')
            votes=await load_votes(conn,room.trip_id);vote=next((v for v in votes if v['voteId']==str(command.voteId)),None)
            if vote is None:raise RoomError('NOT_FOUND')
            if vote['status']!='open' or received>=datetime.fromisoformat(vote['closesAt']):raise RoomError('VOTE_CLOSED')
            if str(actor['user_id']) not in vote['eligibleUserIds']:raise RoomError('FORBIDDEN')
            option=next((i for i in vote['options'] if i['venueId']==str(command.choiceVenueId)),None)
            if option is None:raise RoomError('INVALID_VOTE')
            previous=next((b for b in vote['ballots'] if b['userId']==str(actor['user_id'])),None)
            if (previous['version'] if previous else 0)!=command.expectedBallotVersion:raise RoomError('STALE_BALLOT_VERSION')
            await conn.execute(text('''INSERT INTO ballots(vote_id,user_id,choice_item_id,version) VALUES(:vote,:uid,:choice,1)
                ON CONFLICT(vote_id,user_id) DO UPDATE SET choice_item_id=EXCLUDED.choice_item_id,version=ballots.version+1,cast_at=now()'''),{'vote':command.voteId,'uid':actor['user_id'],'choice':UUID(option['itemId'])})
            next_votes=await load_votes(conn,room.trip_id);updated=next(v for v in next_votes if v['voteId']==str(command.voteId))
            payload=await write_event(conn,room,'trip.vote.cast',{'itemId':option['itemId'],'userId':str(actor['user_id']),'choiceVenueId':str(command.choiceVenueId),'voteId':updated['voteId'],'ballotVersion':command.expectedBallotVersion+1,'vote':updated},command,actor,fingerprint)
        room.votes=next_votes;room.seq=room.committed=payload['roomSeq'];room.publish(envelope('trip.vote.cast',room.trip_id,payload));return payload

async def resolve_locked(room,vote):
    async with room.transaction_locked() as conn:
        fresh=next(v for v in await load_votes(conn,room.trip_id) if v['voteId']==vote['voteId'])
        if fresh['status']!='open':return
        winner,counts=choose_winner(fresh['options'],fresh['ballots'])
        items=[room.items[i] for i in fresh['optionIds']]
        changed=resolve_voting(items,{i['itemId']:i['positionVersion'] for i in items},winner)
        await save_items(conn,room,room.items,changed['activeItems'],changed['archivedItems'])
        result=fresh|{'status':'resolved' if winner else 'cancelled','winningItemId':winner,'tally':counts,'reason':'deadline' if winner else 'no-turnout'}
        updated=await conn.execute(text("UPDATE votes SET status=:status,data=CAST(:data AS jsonb) WHERE id=:id AND status='open' RETURNING id"),{'status':result['status'],'data':json.dumps(result),'id':UUID(vote['voteId'])})
        if not updated.first():raise RuntimeError('duplicate vote resolution')
        next_items={k:v for k,v in room.items.items() if k not in fresh['optionIds']}|{i['itemId']:i for i in changed['activeItems']}
        next_votes=[result if v['voteId']==result['voteId'] else v for v in room.votes]
        if winner:
            await conn.execute(text("INSERT INTO interactions(id,user_id,trip_id,venue_id,dataset_id,kind,event_id) SELECT :id,pinned_by_user_id,trip_id,venue_id,dataset_id,'lock',:event FROM itinerary_items WHERE trip_id=:trip AND id=:item"),
                {'id':uuid4(),'event':uuid4(),'trip':room.trip_id,'item':UUID(winner)})
        await sync_conflicts(conn,room,next_items,next_votes,room.seq+1)
        payload=await write_event(conn,room,'trip.vote.resolved',{'itemId':items[0]['itemId'],'winningVenueId':next((i['venueId'] for i in items if i['itemId']==winner),None),'voteId':result['voteId'],'affectedItems':changed['activeItems']+changed['archivedItems'],'vote':result,**changed,'budgetSummary':summarize(next_items.values(),room.currency,next_votes)})
    room.items=next_items;room.votes=next_votes;room.seq=room.committed=payload['roomSeq'];room.publish(envelope('trip.vote.resolved',room.trip_id,payload))

async def tick(room):
    await room.load()
    async with room.lock:
        if room.frozen:return
        for vote in list(room.votes):
            if vote['status']=='open' and datetime.fromisoformat(vote['closesAt'])<=datetime.now(timezone.utc):await resolve_locked(room,vote)
        async with room.manager.engine.connect() as conn:
            trip=(await conn.execute(text('SELECT room_locked,status FROM trips WHERE id=:trip'),{'trip':room.trip_id})).mappings().one()
        if trip['room_locked'] or trip['status']=='finalized':return
        groups={}
        for i in room.items.values():
            if i['lifecycleStage']=='drafting' and i['venueId'] is not None:groups.setdefault(slot_key([i]),[]).append(i)
        async with room.manager.engine.connect() as conn:
            opened=set((await conn.execute(text('SELECT slot_key FROM votes WHERE trip_id=:trip'),{'trip':room.trip_id})).scalars())
        for key,options in groups.items():
            if key not in opened and len(options)>1 and len({i['venueId'] for i in options})==len(options):await open_locked(room,options=options)
