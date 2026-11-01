"""Frozen chronological synthetic evaluation, independent of model scores.

Authored category cohorts choose liked venues uniformly with a fixed seed.
Training never sees held-out labels. This evaluates synthetic preferences only.
"""
import argparse
import hashlib
import json
import random
from pathlib import Path
from app.recommendations.engine import train,rank

SEED=7312026

def evaluate():
    rng=random.Random(SEED)
    # A separate authored evaluation catalog provides enough unseen positives;
    # these are fictional feature fixtures, never claimed as bookable venues.
    venues=[{'key':f'{category}-{i:02}','category':category,'destination':'Bengaluru fictional evaluation',
             'price_per_person_minor':10000+1000*i,'tags':[]} for category in ('food','activity','lodging','transit') for i in range(10)]
    train_rows=[];validation={};test={};user_history={}
    for user in range(40):
        category=('food','activity','lodging','transit')[user%4]
        choices=[v['key'] for v in venues if v['category']==category];rng.shuffle(choices)
        uid=str(user);user_history[uid]=[{'user':uid,'key':key,'kind':'like'} for key in choices[:3]]
        train_rows.extend(user_history[uid]);validation[uid]=choices[3:5];test[uid]=choices[5:]
    artifact=train(venues,train_rows);results=[]
    # Fixed equal blend from ADR-019; validation labels are never used to tune it.
    for uid,history in user_history.items():
        ranked=rank(artifact,history,excluded={r['key'] for r in history}|set(validation[uid]))
        relevant=set(test[uid]);keys=[r['key'] for r in ranked[:5]]
        variants={
            'hybrid':keys,
            'content':[r['key'] for r in sorted(ranked,key=lambda r:(-r['contentScore'],r['key']))[:5]],
            'cf':[r['key'] for r in sorted(ranked,key=lambda r:(-r['cfScore'],r['key']))[:5]],
            'popularity':sorted([v['key'] for v in venues if v['key'] not in {r['key'] for r in history}|set(validation[uid])],key=lambda k:(-artifact['popularity'].get(k,0),k))[:5]}
        results.append({'user':uid,**{name:len(set(keys)&relevant)/5 for name,keys in variants.items()}})
    metrics={name:sum(row[name] for row in results)/len(results) for name in ('hybrid','content','cf','popularity')}
    fixture={'venues':venues,'train':train_rows,'validation':validation,'test':test}
    return {'seed':SEED,'fixtureSha256':hashlib.sha256(json.dumps(fixture,sort_keys=True).encode()).hexdigest(),
            'trainCount':len(train_rows),'validationCount':80,'testCount':200,'catalogSize':len(venues),'testUsers':len(results),
            'split':'per-user chronological 3 train / 2 validation / 5 test; validation positives excluded as already seen',
            'precisionAt5':metrics,'target':0.6,'targetMet':metrics['hybrid']>=0.6,'perUser':results,
            'limitations':'Synthetic single-category cohorts; no claim about real travelers. All eligible unseen catalog candidates ranked.'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=evaluate();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='perUser'}))

if __name__=='__main__':main()
