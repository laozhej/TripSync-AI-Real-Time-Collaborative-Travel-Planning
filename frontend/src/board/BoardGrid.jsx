import React, {useState} from 'react';
import {planningRange as utcDateRange,displayTime,timeLabel} from './time.js';

export default function BoardGrid({board,room,connection,onSelectedMove,onDropMove,onRemove,onLock,onUnlock}){
  const [offset,O]=useState(0);
  const range=utcDateRange(room);
  const first=Date.parse(range.startDate+'T00:00:00Z'),count=range.count;
  const start=Math.min(offset,Math.max(0,count-1));
  const days=Array.from({length:Math.min(7,count-start)},(_,i)=>({index:start+i,date:new Date(first+(start+i)*86400000).toISOString().slice(0,10)}));
  const canEdit=connection==='connected'&&!board.trip?.roomLocked&&(room.role==='leader'||(room.role==='planner'&&room.canPin));
  const canLead=connection==='connected'&&!board.trip?.roomLocked&&room.role==='leader'&&board.leaderConnected;
  function drop(event,day,hour){
    event.preventDefault();if(!canEdit)return;
    let drag,current;
    try{
      const text=event.dataTransfer.getData('application/tripsync-item');if(text.length>2048)return;
      drag=JSON.parse(text);
      current=board.items.find(item=>item.itemId===drag.itemId);
      if(!current||!Number.isSafeInteger(drag.positionVersion)||drag.positionVersion<1)return;
    }catch{return;}
    onDropMove({...current,positionVersion:drag.positionVersion},day.date,hour);
  }
  return <div className="dayGrid">
    <div className="gridNav"><button className="link" disabled={start===0} onClick={()=>O(Math.max(0,start-7))}>Previous days</button><span>Days {start+1}–{start+days.length} of {count}</span><button className="link" disabled={start+days.length>=count} onClick={()=>O(start+7)}>Next days</button></div>
    <p id="board-instructions">Times are {timeLabel(room)}. Drag a drafting card to a day/time cell, or choose the day and time below and use its move button.</p>
    <div className="gridScroll" tabIndex={0} aria-label="Scrollable itinerary grid">
      <table aria-describedby="board-instructions"><caption>Shared day-by-day itinerary</caption><thead><tr><th scope="col">{timeLabel(room)}</th>{days.map(day=><th key={day.index} scope="col">{day.date}</th>)}</tr></thead>
        <tbody>{Array.from({length:24},(_,hour)=><tr key={hour}><th scope="row">{String(hour).padStart(2,'0')}:00</th>{days.map(day=><td key={day.index} aria-label={`${day.date} ${hour}:00 ${timeLabel(room)}`} onDragOver={event=>{if(canEdit)event.preventDefault()}} onDrop={event=>drop(event,day,hour)}>
          {board.items.filter(item=>displayTime(item.startTime,room).slice(0,10)===day.date&&Number(displayTime(item.startTime,room).slice(11,13))===hour).sort((a,b)=>a.startTime.localeCompare(b.startTime)||a.itemId.localeCompare(b.itemId)).map(item=><article className="place gridCard" key={item.itemId} draggable={canEdit&&item.lifecycleStage==='drafting'}
            onDragStart={event=>{event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('application/tripsync-item',JSON.stringify({itemId:item.itemId,positionVersion:item.positionVersion}))}}>
            <div><small>{displayTime(item.startTime,room)} {timeLabel(room)}</small><h3>{item.name}</h3><span>{item.lifecycleStage}</span></div><div>
              {item.lifecycleStage==='drafting'&&<><button className="link" disabled={!canEdit} onClick={()=>onSelectedMove(item)}>Move to selected time</button><button className="link" disabled={!canEdit} onClick={()=>onRemove(item)}>Remove</button></>}
              {room.role==='leader'&&item.lifecycleStage==='drafting'&&<button className="link" disabled={!canLead} onClick={()=>onLock(item)}>Lock</button>}
              {room.role==='leader'&&item.lifecycleStage==='locked'&&<button className="link" disabled={!canLead} onClick={()=>onUnlock(item)}>Unlock</button>}
            </div></article>)}
        </td>)}</tr>)}</tbody>
      </table>
    </div>
  </div>;
}
