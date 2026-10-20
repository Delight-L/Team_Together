import test from 'node:test';
import assert from 'node:assert/strict';
import {dashboardCaseFocus,selectedServiceContext,serviceDetection,serviceDomains,confirmServiceEvidence} from '../src/serviceCase.mjs';

const context={city:'강남구',district:'삼성2동',age:'50대',month:'2025-12'};
const group={city:'강남구',district:'개포3동',age:'40대',month:'2025-10',sex:'통합'};
test('handoff keeps review month and carries the chosen group without sex',()=>{
  assert.deepEqual(selectedServiceContext('dashboard',context,group,null),{city:'강남구',district:'개포3동',age:'40대',month:'2025-12'});
  assert.deepEqual(selectedServiceContext('map',context,null,group),{city:'강남구',district:'개포3동',age:'40대',month:'2025-12'});
  assert.deepEqual(selectedServiceContext('chart',context,null,null),context);
  assert.equal(selectedServiceContext('dashboard',context,null,null).district,context.district);
});
test('exact dong, age and month required; no fallback to another detected case',()=>{
  const hit={...group,case_id:'chosen'};
  const analysis={ageDetections:[{...hit,age:'30대'},{...hit,month:'2025-11'},hit]};
  assert.equal(serviceDetection(analysis,group),hit);
  assert.equal(serviceDetection(analysis,{...group,age:undefined}),null);
  assert.equal(serviceDetection(analysis,{...group,city:'춘천시'}),null);
  assert.equal(serviceDetection(analysis,{...group,month:'2025-12'}),null);
});
test('communication and mobility preserve independent methods and paired metrics',()=>{
  const domains=serviceDomains({communication_signal:true,mobility_signal:true,payload:{communication_absolute_signal:true,communication_local_signal:false,mobility_absolute_signal:false,mobility_local_signal:true}});
  assert.deepEqual(domains.map(d=>d.state),['absolute','local']);
  assert.deepEqual(domains[0].metrics,['call_contacts','text_contacts']);
  assert.equal(serviceDomains({communication_signal:true,payload:{communication_absolute_signal:true,communication_local_signal:true}})[0].state,'both');
});
test('explicit confirmation registers evidence before confirming; successful return unlocks lookup',async()=>{
  const calls=[];
  const result=await confirmServiceEvidence({},async path=>{calls.push(path);return {done:path.endsWith('start')?[0]:[0,1]};});
  assert.deepEqual(calls,['/workflow/start','/workflow/confirm']);
  assert.deepEqual(result.done,[0,1]);
});
test('registration failure never confirms or unlocks; retry skips an already registered snapshot',async()=>{
  const calls=[];
  assert.equal(await confirmServiceEvidence({},async path=>{calls.push(path);return null;}),null);
  assert.deepEqual(calls,['/workflow/start']);
  calls.length=0;
  await confirmServiceEvidence({done:[0]},async path=>{calls.push(path);return null;});
  assert.deepEqual(calls,['/workflow/confirm']);
});
test('revisiting a reviewed case does not register or confirm again',async()=>{
  const current={done:[0,1,2]};
  assert.equal(await confirmServiceEvidence(current,()=>{throw Error('Unexpected save');}),current);
});

test('overview handoff preserves original case identity and empty-month focus',()=>{
 const analysis={ageDetections:[{...group,code:'1123074',any_signal:true}]};
 const focus=dashboardCaseFocus(analysis,group,42);
 assert.equal(focus.code,'1123074');assert.equal(focus.sex,'통합');assert.equal(focus.requestId,42);
 assert.deepEqual(selectedServiceContext('dashboard',context,focus,null),{city:group.city,district:group.district,age:group.age,month:context.month});
 const empty={city:'강남구',month:'2025-09',district:''};
 assert.equal(dashboardCaseFocus(analysis,empty,43).month,'2025-09');
 assert.equal(dashboardCaseFocus(analysis,empty,43).code,undefined);
});
