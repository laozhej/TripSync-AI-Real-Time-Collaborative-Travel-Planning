import asyncio
import hashlib
import json
from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import text
from app.recommendations.engine import train,rank

async def catalog(conn,dataset):
    return [dict(r)|{'key':r['source_id']} for r in (await conn.execute(text('''SELECT v.*,d.destination,
        ARRAY(SELECT tag FROM venue_dietary_tags t WHERE t.venue_id=v.id AND t.dataset_id=v.dataset_id ORDER BY tag) AS tags
        FROM venue_metadata v JOIN datasets d ON d.id=v.dataset_id WHERE v.dataset_id=:dataset ORDER BY v.source_id'''),{'dataset':dataset})).mappings()]

async def training(engine,dataset):
    async with engine.connect() as conn:
        venues=await catalog(conn,dataset)
        rows=[dict(r) for r in (await conn.execute(text('''SELECT i.user_id::text AS "user",v.source_id AS key,i.kind,i.created_at FROM interactions i
            JOIN venue_metadata v ON v.id=i.venue_id AND v.dataset_id=i.dataset_id WHERE i.dataset_id=:dataset'''),{'dataset':dataset})).mappings()]
        watermark=max((r['created_at'] for r in rows),default=datetime(1970,1,1,tzinfo=timezone.utc))
    artifact=await asyncio.to_thread(train,venues,rows)
    raw=json.dumps(artifact,sort_keys=True);checksum=hashlib.sha256(raw.encode()).hexdigest();version=uuid4()
    # Validate fully before retiring the prior artifact. One transaction promotes.
    if not artifact['features'] or any(k not in artifact['features'] for k in artifact['neighbors']):raise ValueError('invalid artifact')
    async with engine.begin() as conn:
        await conn.execute(text('UPDATE model_artifacts SET active=false WHERE dataset_id=:dataset AND active'),{'dataset':dataset})
        await conn.execute(text('''INSERT INTO model_artifacts(id,dataset_id,artifact,checksum,trained_through,active)
            VALUES(:id,:dataset,CAST(:artifact AS jsonb),:checksum,:watermark,true)'''),{'id':version,'dataset':dataset,'artifact':raw,'checksum':checksum,'watermark':watermark})
    return {'modelVersion':str(version),'checksum':checksum,'interactions':len(rows),'trainedThrough':watermark.isoformat()}

async def recommend(conn,trip,user_id):
    venues=await catalog(conn,trip['dataset_id'])
    artifact=(await conn.execute(text('SELECT id,artifact,checksum,trained_through FROM model_artifacts WHERE dataset_id=:dataset AND active'),{'dataset':trip['dataset_id']})).mappings().first()
    model=artifact['artifact'] if artifact else train(venues,[])
    if artifact and hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()!=artifact['checksum']:raise ValueError('artifact checksum mismatch')
    users=(await conn.execute(text("SELECT user_id FROM memberships WHERE trip_id=:trip AND status='active'"),{'trip':trip['id']})).scalars().all()
    history=[dict(r) for r in (await conn.execute(text('''SELECT i.user_id::text AS "user",v.source_id AS key,i.kind,i.created_at FROM interactions i
        JOIN venue_metadata v ON v.id=i.venue_id AND v.dataset_id=i.dataset_id
        WHERE i.dataset_id=:dataset AND i.user_id=ANY(:users) AND EXISTS
        (SELECT 1 FROM memberships m WHERE m.trip_id=i.trip_id AND m.user_id=i.user_id AND m.status='active')'''),{'dataset':trip['dataset_id'],'users':list(users)})).mappings()]
    excluded=set((await conn.execute(text('''SELECT v.source_id FROM itinerary_items i JOIN venue_metadata v ON v.id=i.venue_id AND v.dataset_id=i.dataset_id
        WHERE i.trip_id=:trip AND (i.lifecycle_stage='locked' OR i.removed_at IS NOT NULL)'''),{'trip':trip['id']})).scalars())
    scores={}
    for uid in users:
        for row in rank(model,[r for r in history if r['user']==str(uid)],excluded):
            aggregate=scores.setdefault(row['key'],row|{'score':0.0})
            aggregate['score']+=row['score']/len(users)
    by_key={v['key']:v for v in venues}
    ranked=sorted(scores.values(),key=lambda r:(-r['score'],r['key']))[:5]
    return {'modelVersion':str(artifact['id']) if artifact else None,'hybridReady':bool(artifact),
        'generatedAt':datetime.now(timezone.utc).isoformat(),'interactionWatermark':max((r['created_at'] for r in history),default=None),
        'exploratory':True,'items':[r|{'venueId':str(by_key[r['key']]['id']),'name':by_key[r['key']]['name'],'category':by_key[r['key']]['category']} for r in ranked]}
