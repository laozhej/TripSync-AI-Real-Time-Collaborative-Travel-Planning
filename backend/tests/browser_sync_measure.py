"""Two-context rendered board latency, including same-version races."""
import json
import os
from pathlib import Path
import secrets
import time
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright
from phase4_measure_stats import distribution

OUT = Path(os.getenv('MEASUREMENT_OUTPUT', 'evidence/performance/sync-browser'))
OUT.mkdir(parents=True, exist_ok=True)
INIT = """
window.__sync = {items:{}, sent:{}, samples:{}, conflicts:[], longTasks:[]};
new PerformanceObserver(list => {
  for (const entry of list.getEntries()) window.__sync.longTasks.push({start:entry.startTime,duration:entry.duration});
}).observe({type:'longtask',buffered:true});
const Native = window.WebSocket;
window.WebSocket = class extends Native {
  constructor(...args) {
    super(...args);
    window.__sync.socket=this;
    this.addEventListener('message', e => {
      const {event,payload:p}=JSON.parse(e.data), state=window.__sync;
      if(event==='trip.snapshot') state.items=Object.fromEntries(p.items.map(i=>[i.itemId,i]));
      if(event==='trip.board.edit.conflict') state.conflicts.push(p);
      if(event!=='trip.board.update') return;
      if(p.operation==='remove') delete state.items[p.itemId]; else state.items[p.itemId]=p.item;
      const sample={received:performance.timeOrigin+performance.now()};
      state.samples[p.commandId]=sample;
      const expected=new Date(Date.parse(p.item.startTime)+19800000).toISOString().slice(11,16)+' IST';
      const matching=()=>[...document.querySelectorAll('.gridCard')].some(c=>c.querySelector('h3')?.textContent===p.item.name && c.querySelector('small')?.textContent.includes(expected));
      const done=()=>{
        if(!matching()) return false;
        sample.dom=performance.timeOrigin+performance.now();
        requestAnimationFrame(()=>requestAnimationFrame(()=>sample.frame=performance.timeOrigin+performance.now()));
        return true;
      };
      if(!done()){
        const observer=new MutationObserver(()=>{if(done())observer.disconnect()});
        observer.observe(document.getElementById('itinerary'),{subtree:true,childList:true,characterData:true});
        setTimeout(()=>observer.disconnect(),5000);
      }
    });
  }
  send(raw) {
    const command=JSON.parse(raw);
    if(command.event==='trip.board.move') window.__sync.sent[command.payload.commandId]=performance.timeOrigin+performance.now();
    return super.send(raw);
  }
};
"""
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    contexts=[browser.new_context(reduced_motion='reduce') for _ in range(2)]
    for context in contexts:context.add_init_script(INIT)
    pages=[context.new_page() for context in contexts]
    errors=[]
    for index,page in enumerate(pages):
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(os.environ['BROWSER_BASE_URL'],wait_until='networkidle')
        page.get_by_role('button',name='Create account',exact=True).click()
        page.get_by_label('Display name').fill(['Leader','Planner'][index])
        page.get_by_label('Email',exact=True).fill(f'sync-{secrets.token_hex(8)}@example.invalid')
        page.get_by_label('Password',exact=True).fill('synthetic browser measurement password')
        page.locator('form').get_by_role('button',name='Create account',exact=True).click()
        page.get_by_role('heading',name='Start a trip').wait_for()
    leader,planner=pages
    leader.get_by_role('button',name='Create room',exact=True).click()
    leader.locator('[data-snapshot-ready=true]').wait_for()
    leader.get_by_role('button',name='Itinerary canvas',exact=True).click()
    planner.get_by_label('Invitation code').fill(leader.locator('.invite code').inner_text())
    planner.get_by_role('button',name='Join room',exact=True).click()
    planner.locator('[data-snapshot-ready=true]').wait_for()
    planner.get_by_role('button',name='Itinerary canvas',exact=True).click()
    leader.get_by_role('button',name='Add to itinerary',exact=True).first.click()
    for page in pages:expect(page.locator('.gridCard')).to_have_count(1)
    samples=[]
    for n in range(220):
        sender=pages[n%2]
        key=str(uuid4())
        minute='30' if n%2 else '35'
        sender.evaluate("""({key,minute})=>{
          const item=Object.values(window.__sync.items)[0];
          window.__sync.socket.send(JSON.stringify({event:'trip.board.move',payload:{
            commandId:key,correlationId:key,itemId:item.itemId,expectedPositionVersion:item.positionVersion,
            dayIndex:0,startTime:'2026-11-10T06:'+minute+':00Z',endTime:'2026-11-10T07:'+minute+':00Z'
          }}))
        }""",{'key':key,'minute':minute})
        for page in pages:page.wait_for_function('key=>window.__sync.samples[key]?.frame',arg=key)
        sent=sender.evaluate('key=>window.__sync.sent[key]',key)
        received=[page.evaluate('key=>window.__sync.samples[key]',key) for page in pages]
        if n>=20:samples.append({'commandId':key,'allReceivedMs':max(s['received'] for s in received)-sent,
            'allDomMs':max(s['dom'] for s in received)-sent,'allFrameMs':max(s['frame'] for s in received)-sent})
        time.sleep(.025)
    race_frames = []
    for n in range(20):
        item=leader.evaluate('Object.values(window.__sync.items)[0]')
        keys=[str(uuid4()),str(uuid4())]
        target=time.time()*1000+100
        for page,key in zip(pages,keys):
            page.evaluate("""({item,key,target,minute})=>setTimeout(()=>{
              window.__sync.socket.send(JSON.stringify({event:'trip.board.move',payload:{
                commandId:key,correlationId:key,itemId:item.itemId,expectedPositionVersion:item.positionVersion,
                dayIndex:0,startTime:'2026-11-10T06:'+minute+':00Z',endTime:'2026-11-10T07:'+minute+':00Z'}}))
            },Math.max(0,target-Date.now()))""",{'item':item,'key':key,'target':target,'minute':'35' if n%2==0 else '30'})
        for page in pages:page.wait_for_function('version=>Object.values(window.__sync.items)[0].positionVersion===version',arg=item['positionVersion']+1)
        deadline=time.monotonic()+5
        while sum(page.evaluate('window.__sync.conflicts.length') for page in pages)<n+1:
            assert time.monotonic()<deadline
            time.sleep(.01)
        assert leader.evaluate('window.__sync.items')==planner.evaluate('window.__sync.items')
        winner = leader.evaluate('keys=>keys.find(key=>window.__sync.samples[key])',keys)
        assert winner
        for page in pages:
            page.wait_for_function('key=>window.__sync.samples[key]?.frame',arg=winner)
        sent = pages[keys.index(winner)].evaluate('key=>window.__sync.sent[key]',winner)
        race_frames.append(max(page.evaluate('key=>window.__sync.samples[key].frame',winner) for page in pages)-sent)
    long_tasks=[page.evaluate('window.__sync.longTasks') for page in pages]
    assert not errors,errors
    summary={'chrome':browser.version,'contexts':2,'warmupMoves':20,'moves':len(samples),'concurrentRaces':20,
        'method':'same-host performance.timeOrigin+performance.now from socket send to both DOM updates and two animation frames; 25ms inter-move pacing',
        'received':distribution([s['allReceivedMs'] for s in samples]),'dom':distribution([s['allDomMs'] for s in samples]),
        'frames':distribution([s['allFrameMs'] for s in samples]),'raceFrames':distribution(race_frames),'racesOver100Ms':sum(ms>=100 for ms in race_frames),'over100Ms':sum(s['allFrameMs']>=100 for s in samples)}
    (OUT/'browser-samples.json').write_text(json.dumps({'moves':samples,'raceFramesMs':race_frames,'longTasks':long_tasks},indent=2))
    (OUT/'browser-summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))
    browser.close()
