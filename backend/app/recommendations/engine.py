"""Small content-cosine + item-neighbor collaborative model, trained off-loop."""
import math
from collections import defaultdict

STRENGTH={'view':1,'pin':2,'like':3,'lock':4}

def cosine(a,b):
    denominator=math.sqrt(sum(v*v for v in a.values())*sum(v*v for v in b.values()))
    return sum(v*b.get(k,0) for k,v in a.items())/denominator if denominator else 0.0

def features(venue):
    return {'category:'+venue['category']:1.0,'destination:'+venue['destination']:0.25,
            'price':min(venue['price_per_person_minor']/100000,1.0),
            **{'diet:'+tag:0.5 for tag in venue.get('tags',[])}}

def train(venues,interactions):
    vectors={v['key']:features(v) for v in venues}; users=defaultdict(dict); popularity=defaultdict(int)
    for row in interactions:
        key=row['key'];uid=row['user'];strength=STRENGTH[row['kind']]
        if key in vectors:users[uid][key]=max(users[uid].get(key,0),strength)
    columns={k:{u:profile[k] for u,profile in users.items() if k in profile} for k in vectors}
    for profile in users.values():
        for key,value in profile.items():popularity[key]+=value
    return {'schemaVersion':1,'features':vectors,'neighbors':{k:{j:cosine(column,other) for j,other in columns.items() if j!=k} for k,column in columns.items()},'popularity':dict(popularity)}

def rank(artifact,history,excluded=(),declared=()):
    profile=defaultdict(float); positives={}
    for row in history:positives[row['key']]=max(positives.get(row['key'],0),STRENGTH[row['kind']])
    for key,w in positives.items():
        for feature,value in artifact['features'].get(key,{}).items():profile[feature]+=value*w
    for category in declared:profile['category:'+category]+=1
    output=[];max_pop=max(artifact['popularity'].values(),default=1) or 1
    for key,vector in artifact['features'].items():
        if key in excluded:continue
        content=cosine(profile,vector) if profile else artifact['popularity'].get(key,0)/max_pop
        neighbors=artifact['neighbors'].get(key,{})
        cf=sum(neighbors.get(j,0)*w for j,w in positives.items())/sum(positives.values()) if positives else 0
        available=any(neighbors.get(j,0)>0 for j in positives)
        output.append({'key':key,'score':0.5*content+0.5*cf if available else content,'contentScore':content,'cfScore':cf,
                       'reason':'content+collaborative' if available else 'content/popularity cold start'})
    return sorted(output,key=lambda r:(-r['score'],r['key']))
