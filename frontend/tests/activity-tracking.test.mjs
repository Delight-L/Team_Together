import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {eventsFor,trackingSeries,latestObservation,pathState,DOMAINS,stateLabel} from '../src/activityTracking.mjs';
const data=JSON.parse(readFileSync(new URL('../../data/processed/region_insights.json',import.meta.url))).activityTracking;
test('the ten reviewed episodes and 29 follow-up records keep their exact dong, age and month',()=>{
 assert.equal(data.events.length,10);assert.equal(data.events.reduce((n,e)=>n+e.points.length,0),29);
 const event=eventsFor(data,'개포3동','40대','2025-12')[0];
 assert.equal(event.code,'1123074');assert.equal(event.referenceMonth,'2025-09');assert.equal(event.signalMonth,'2025-10');
 assert.equal(eventsFor(data,'개포3동','20대','2025-12').length,0);
 assert.equal(eventsFor(data,'개포3동','40대','2025-09').length,0);
 assert.equal(pathState(event.signals.communication),'absolute');assert.equal(pathState(event.signals.mobility),'none');
});
test('end month prevents future records and compares to the fixed pre-signal month, not the previous plotted month',()=>{
 const event=eventsFor(data,'개포3동','40대','2025-12')[0];
 const series=trackingSeries(event,'2025-11');
 assert.deepEqual(series.map(p=>p.month),['2025-09','2025-10','2025-11']);
 assert.equal(series[0].values.call_contacts,100);
 assert.ok(Math.abs(series[1].values.call_contacts-95.1317494294766)<1e-8);
 assert.equal(latestObservation(event,'2025-11').month,'2025-11');
 assert.equal(trackingSeries(event,'2025-09').length,0);
});
test('all four real metric series and existing scope states are preserved without treating later mobility falls as new detection',()=>{
 const event=eventsFor(data,'개포3동','40대','2025-12')[0];
 const raw=trackingSeries(event,'2025-12').at(-1).values;
 const seasonal=trackingSeries(event,'2025-12','seasonal').at(-1).values;
 for(const d of DOMAINS)for(const [metric] of d.metrics)assert.ok(Number.isFinite(raw[metric]));
 assert.ok(Math.abs(raw.call_contacts-94.82405657089485)<1e-8);
 assert.ok(Math.abs(raw.weekday_move_count-57.95486024412179)<1e-8);
 assert.ok(Math.abs(seasonal.text_contacts-88.00331975916905)<1e-8);
 const latest=latestObservation(event,'2025-12');
 assert.equal(latest.domains.mobility.raw_state,'both_below_reference');
 assert.equal(pathState(event.signals.mobility),'none');
 assert.equal(stateLabel('unavailable'),'비교 자료 부족');
});
test('missing metrics remain missing and mixed detection methods have independent badges',()=>{
 const event={signalMonth:'2025-10',referenceMonth:'2025-09',points:[{month:'2025-10',raw:{call_contacts:null,text_contacts:-4}}]};
 const series=trackingSeries(event,'2025-12');
 assert.equal(series[0].values.call_contacts,null);assert.equal(series[1].values.call_contacts,null);
 assert.equal(series[1].values.text_contacts,96);
 assert.equal(pathState({absolute:true,local:false}),'absolute');assert.equal(pathState({absolute:false,local:true}),'local');
 assert.equal(pathState({absolute:true,local:true}),'both');assert.equal(pathState({}),'none');
});
