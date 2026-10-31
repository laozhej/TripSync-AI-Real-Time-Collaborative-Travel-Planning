import React, {useEffect, useState} from 'react';
const tags=['vegetarian','vegan','halal','gluten-free'];
function cents(value){
  if(!/^\d{1,11}(\.\d{1,2})?$/.test(value))throw Error('Enter a positive EUR amount with at most two decimal places.');
  const [whole,fraction='']=value.split('.');const total=BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0'));
  if(total<=0n||total>1000000000000n)throw Error('The ceiling is outside the supported range.');
  return Number(total);
}
function amount(value){if(value==null)return '';const text=String(value).padStart(3,'0');return text.slice(0,-2)+'.'+text.slice(-2)}

export default function ConciergePanel({api,tripId,userId,isLeader,board,day,time,onResync}){
  const [category,C]=useState('food'),[question,Q]=useState('Suggest a venue that fits our group.'),[anchor,A]=useState('');
  const [groupBudget,G]=useState(''),[personalBudget,P]=useState(''),[diets,D]=useState([]),[result,R]=useState(null);
  const [busy,B]=useState(false),[error,E]=useState(''),[source,S]=useState(null);
  useEffect(()=>{G(amount(board.trip?.categoryCeilingsMinor?.[category]))},[category,board.trip?.categoryCeilingsMinor]);
  useEffect(()=>{P(amount(board.preferences?.categoryCeilingsMinor?.[category]));D(board.preferences?.dietaryTags||[])},[category,board.preferences]);
  useEffect(()=>{if(board.lastSuggestion)R(board.lastSuggestion)},[board.lastSuggestion]);
  async function perform(work){B(true);E('');try{await work()}catch(error){E(error.message);onResync()}finally{B(false)}}
  async function save(group){await perform(async()=>{
    const command={commandId:crypto.randomUUID(),correlationId:crypto.randomUUID(),expectedStateVersion:board.stateVersion};
    if(group){command.categoryCeilingsMinor={...board.trip?.categoryCeilingsMinor,[category]:cents(groupBudget)}}
    else{const ceilings={...board.preferences?.categoryCeilingsMinor};if(personalBudget.trim())ceilings[category]=cents(personalBudget);else delete ceilings[category];command.targetUserId=userId;command.constraints={dietaryTags:diets,categoryCeilingsMinor:ceilings}}
    await api(`/api/v1/trips/${tripId}/constraints`,{method:'POST',body:JSON.stringify(command)});
  })}
  async function ask(event){event.preventDefault();await perform(async()=>{
    const start=new Date(day+'T'+time+':00Z');if(!Number.isFinite(start.getTime()))throw Error('Choose a valid trip day and time.');
    const body={question,category,startTime:start.toISOString(),endTime:new Date(start.getTime()+3600000).toISOString(),attendeeIds:[]};
    if(anchor)body.anchorItemId=anchor;
    S(null);R(await api(`/api/v1/trips/${tripId}/ai/ask`,{method:'POST',headers:{'Idempotency-Key':crypto.randomUUID()},body:JSON.stringify(body)}));
  })}
  const earlier=result&&(result.roomEpoch!==board.roomEpoch||board.roomSeq>result.roomSeq);
  return <section className="panel concierge" aria-label="AI Concierge">
    <h2>AI Concierge</h2><p>Suggestions use the authored dataset and every attending traveler's constraints. Sample places are fictional.</p>
    {error&&<p role="alert">{error}</p>}
    <label>Spend category<select value={category} onChange={e=>C(e.target.value)}>{['food','activity','lodging','transit'].map(value=><option key={value}>{value}</option>)}</select></label>
    <details><summary>Budget and dietary preferences</summary>
      {isLeader&&<div><label>Group category ceiling (EUR/person)<input inputMode="decimal" value={groupBudget} onChange={e=>G(e.target.value)}/></label><button disabled={busy||!board.leaderConnected} onClick={()=>save(true)}>Save group ceiling</button></div>}
      <label>My category ceiling (EUR/person, optional)<input inputMode="decimal" value={personalBudget} onChange={e=>P(e.target.value)}/></label>
      <fieldset><legend>My dietary requirements</legend>{tags.map(tag=><label key={tag}><input type="checkbox" checked={diets.includes(tag)} onChange={e=>D(old=>e.target.checked?[...old,tag]:old.filter(value=>value!==tag))}/>{tag}</label>)}</fieldset>
      <button disabled={busy} onClick={()=>save(false)}>Save my preferences</button>
    </details>
    <form onSubmit={ask}>
      <label>Question<textarea required maxLength={4000} value={question} onChange={e=>Q(e.target.value)}/></label>
      <label>Near a planned item<select value={anchor} onChange={e=>A(e.target.value)}><option value="">No anchor</option>{board.items.map(item=><option key={item.itemId} value={item.itemId}>{item.name}</option>)}</select></label>
      <p>For all active travelers, starting {day} at {time} UTC, for one hour. The opening-hours check includes a 30-minute buffer before the start.</p>
      <button className="secondary" disabled={busy}>{busy?'Checking…':'Ask Concierge'}</button>
    </form>
    {result&&<div role="status"><p><strong>{earlier?'Earlier result':result.status.replaceAll('_',' ')}</strong></p>{earlier&&<p>The room changed after this answer. Review your constraints and ask again for a current suggestion.</p>}<p>{result.answer}</p>{result.sourceEvents.map(id=><button className="link" key={id} onClick={()=>perform(async()=>S(await api(`/api/v1/trips/${tripId}/ai/sources/${encodeURIComponent(id)}`)))}>{id}</button>)}</div>}
    {source&&<div><h3>{source.name}</h3><p>EUR {amount(source.pricePerPersonMinor)} per person · {source.category}</p><p>{source.description}</p><p>Dietary tags: {source.dietaryTags.join(', ')||'none declared'}</p><small>{source.sourceId} · Synthetic authored source</small></div>}
  </section>;
}
