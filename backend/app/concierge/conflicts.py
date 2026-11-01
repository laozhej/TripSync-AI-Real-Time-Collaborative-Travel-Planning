"""Deterministic conflict fingerprints; persistence owns open/resolved history."""
from datetime import datetime
from itertools import combinations
import hashlib
import json

def detect(items,budget,total_ceiling,personal_ceilings):
    result={}
    def add(kind,ids,details):
        identity=[kind,sorted(ids),details.get('userId')]
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        result[key]={'fingerprint':key,'type':kind,'itemIds':sorted(ids),'details':details}
    for a,b in combinations(sorted(items,key=lambda i:i['itemId']),2):
        if (set(a['attendeeIds']) & set(b['attendeeIds']) and
            datetime.fromisoformat(a['startTime'])<datetime.fromisoformat(b['endTime']) and
            datetime.fromisoformat(b['startTime'])<datetime.fromisoformat(a['endTime'])):
            add('overlap',[a['itemId'],b['itemId']],{})
    if budget['proposedMinor']>total_ceiling:
        add('budgetBreach',[],{'proposedMinor':budget['proposedMinor'],'ceilingMinor':total_ceiling})
    for p in budget['perPerson']:
        ceiling=personal_ceilings.get(p['userId'])
        if ceiling is not None and p['proposedMinor']>ceiling:
            add('budgetBreach',[],{'userId':p['userId'],'proposedMinor':p['proposedMinor'],'ceilingMinor':ceiling})
    return result
