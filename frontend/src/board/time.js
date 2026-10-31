const DAY=86400000;
const formatters=new Map();
export function destinationDate(instant,timezone='UTC'){
  if(!formatters.has(timezone))formatters.set(timezone,new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}));
  const values=Object.fromEntries(formatters.get(timezone).formatToParts(new Date(instant)).map(part=>[part.type,part.value]));
  return values.year.padStart(4,'0')+'-'+values.month+'-'+values.day;
}
function isoDate(millis){return new Date(millis).toISOString().slice(0,10)}
export function utcDateRange(room){
  let first=Date.parse(room.startDate+'T00:00:00Z'),last=Date.parse(room.endDate+'T00:00:00Z');
  if(destinationDate(first-1,room.timezone)===room.startDate)first-=DAY;
  if(destinationDate(last+DAY,room.timezone)===room.endDate)last+=DAY;
  return {startDate:isoDate(first),endDate:isoDate(last),count:Math.round((last-first)/DAY)+1};
}
export function slot(date,time,room,duration=3600000){
  const start=new Date(date+'T'+time+':00Z');
  if(!Number.isFinite(start.getTime())||start.toISOString().slice(0,16)!==date+'T'+time||!Number.isSafeInteger(duration)||duration<=0){
    throw Error('Choose a valid date, UTC time and duration.');
  }
  const end=new Date(start.getTime()+duration);
  if(!Number.isFinite(end.getTime()))throw Error('Choose a valid end time.');
  const local=destinationDate(start,room.timezone),last=destinationDate(end.getTime()-1,room.timezone);
  if(local<room.startDate||last>room.endDate)throw Error('Choose a slot within the destination-local trip dates.');
  return {dayIndex:Math.round((Date.parse(local+'T00:00:00Z')-Date.parse(room.startDate+'T00:00:00Z'))/DAY),
          startTime:start.toISOString(),endTime:end.toISOString()};
}
