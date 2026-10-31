import test from 'node:test';
import assert from 'node:assert/strict';
import {destinationDate,utcDateRange,slot} from '../src/board/time.js';
const trip=(timezone,startDate='2026-07-10',endDate=startDate)=>({timezone,startDate,endDate});

test('Lisbon summer UTC drop uses the destination-local day index',()=>{
  const room=trip('Europe/Lisbon','2026-07-10','2026-07-12');
  assert.equal(slot('2026-07-10','23:00',room).dayIndex,1);
  assert.equal(destinationDate('2026-07-10T23:00:00Z',room.timezone),'2026-07-11');
});
test('positive offset includes the previous UTC display date',()=>{
  assert.deepEqual(utcDateRange(trip('Europe/Lisbon')),{startDate:'2026-07-09',endDate:'2026-07-10',count:2});
  assert.equal(slot('2026-07-09','23:00',trip('Europe/Lisbon')).dayIndex,0);
});
test('winter Lisbon has no extra display day',()=>{
  assert.deepEqual(utcDateRange(trip('Europe/Lisbon','2026-11-10')),{startDate:'2026-11-10',endDate:'2026-11-10',count:1});
});
test('negative offset includes the next UTC date',()=>{
  assert.deepEqual(utcDateRange(trip('America/New_York')),{startDate:'2026-07-10',endDate:'2026-07-11',count:2});
  assert.equal(slot('2026-07-11','02:00',trip('America/New_York')).dayIndex,0);
});
test('quarter-hour offset does not require a guessed numeric offset',()=>{
  assert.equal(slot('2026-07-09','18:15',trip('Asia/Kathmandu')).dayIndex,0);
});
test('invalid or out-of-trip slots reject before any command is sent',()=>{
  for(const [day,time] of [['2026-07-09','22:00'],['2026-07-10','23:00'],['2026-02-31','12:00'],['2026-07-10','25:00']]){
    assert.throws(()=>slot(day,time,trip('Europe/Lisbon')));
  }
});
test('drop preserves duration and half-open end may equal trip midnight',()=>{
  const value=slot('2026-07-10','21:00',trip('Europe/Lisbon'),2*3600000);
  assert.equal(value.endTime,'2026-07-10T23:00:00.000Z');
  assert.equal(value.dayIndex,0);
});
