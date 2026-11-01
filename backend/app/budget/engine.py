"""Exact minor-unit allocations; no transport, storage or model arithmetic."""
def allocate(total, weights):
    if type(total) is not int or not 0 <= total <= 10**12 or not weights:
        raise ValueError('invalid total or attendees')
    if any(type(w) is not int or not 0 <= w <= 2**31-1 for w in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError('invalid weights')
    denominator=sum(weights.values())
    result={uid:total*w//denominator for uid,w in weights.items()}
    order=sorted(weights,key=lambda uid:(-(total*weights[uid]%denominator),uid))
    for uid in order[:total-sum(result.values())]: result[uid]+=1
    return dict(sorted(result.items()))

def item_allocations(item):
    ids=item['attendeeIds']
    weights=item.get('weights',{}) if item.get('splitMode')=='weighted' else {uid:1 for uid in ids}
    if set(weights)!=set(ids): raise ValueError('weights must cover attendees')
    return allocate(item['pricePerPersonMinor']*len(ids),weights)

def summarize(items,currency,votes=()):
    items={i['itemId']:i for i in items}
    allocations={key:item_allocations(i) for key,i in items.items()}
    grouped=set(); reservations=[]; people={}; proposed=locked=0
    def add(values,committed=False):
        nonlocal proposed,locked
        proposed+=sum(values.values())
        if committed: locked+=sum(values.values())
        for uid,amount in values.items():
            p=people.setdefault(uid,{'userId':uid,'proposedMinor':0,'lockedMinor':0})
            p['proposedMinor']+=amount
            if committed:p['lockedMinor']+=amount
    for vote in votes:
        if vote['status']!='open':continue
        options=[key for key in vote['optionIds'] if key in items]
        grouped.update(options)
        users={uid for key in options for uid in allocations[key]}
        values={uid:max(allocations[key].get(uid,0) for key in options) for uid in users}
        add(values);reservations.append({'optionIds':options,'allocations':values})
    for key,item in items.items():
        if key not in grouped:add(allocations[key],item['lifecycleStage']=='locked')
    return {'currency':currency,'proposedMinor':proposed,'lockedMinor':locked,
            'perPerson':[people[uid] for uid in sorted(people)],'itemAllocations':allocations,
            'reservationMethod':'per-person maximum','reservations':reservations}
