import React,{useEffect,useState} from 'react';
export default function Dashboard({api,onOpen}){
 const [data,setData]=useState(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;api('/api/v1/me/dashboard').then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError(e.message)});return()=>{active=false}},[]);
 const money=(minor,currency)=>new Intl.NumberFormat('en-IN',{style:'currency',currency}).format(minor/100);
 return <section className="panel"><h2>Your trips & preferences</h2>{error&&<p role="alert">{error}</p>}{!data&&!error&&<p>Loading your trips…</p>}{data&&<><p>{data.derivedPreferences.length?data.derivedPreferences.map(p=>`${p.category}: ${p.interactions} interactions`).join(' · '):'Like places to build your travel preferences.'}</p><p>Declared diets: {data.dietaryTags.join(', ')||'None yet'}</p>{data.budgetRanges.map(r=><p key={r.currency}>Price range from your history: {money(r.minimumMinor,r.currency)} to {money(r.maximumMinor,r.currency)} per person</p>)}{data.trips.length===0&&<p>Your trip history will appear here.</p>}{data.trips.map(t=><article className="place" key={t.tripId}><div><h3>{t.destination}</h3><p>{t.startDate} to {t.endDate} · {t.role} · {t.status}</p></div><button className="secondary" onClick={()=>onOpen(t.tripId)}>{t.canRejoin?'Rejoin room':'View history'}</button></article>)}</>}</section>
}
