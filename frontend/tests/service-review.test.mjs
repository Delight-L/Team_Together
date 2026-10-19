import test from 'node:test';
import assert from 'node:assert/strict';
import {serviceReviewCases, selectedReviewCase, serviceReviewContext, reviewCaseKey, reviewMonthGroups} from '../src/serviceReview.mjs';

const context={city:'강남구',month:'2025-12',district:'역삼2동',age:'30대'};
const detection=(district,age,month,communication=true,mobility=false)=>({district,age,month,code:district,any_signal:true,
  communication_signal:communication,mobility_signal:mobility,payload:{communication_absolute_signal:communication,mobility_local_signal:mobility}});
const event=(row,points)=>({district:row.district,code:row.code,age:row.age,signalMonth:row.month,points});
const point=(month,communication,mobility)=>({month,domains:{communication:{raw_state:communication},mobility:{raw_state:mobility}}});
const recovered='recovered_to_reference',below='both_below_reference';

test('review month includes new and unrecovered earlier events, never future detections',()=>{
  const rows=[detection('역삼2동','30대','2025-11'),detection('삼성2동','50대','2025-10'),detection('삼성2동','30대','2025-10'),detection('삼성10동','30대','2025-10'),detection('개포3동','40대','2026-01')];
  const items=serviceReviewCases({ageDetections:rows},{events:[]},context);
  assert.deepEqual(items.map(x=>`${x.signalMonth}/${x.district}/${x.age}`),['2025-11/역삼2동/30대','2025-10/삼성2동/30대','2025-10/삼성2동/50대','2025-10/삼성10동/30대']);
  assert.ok(items.every(item=>item.month==='2025-12'&&item.lifecycle==='tracking'));
  const nov=serviceReviewCases({ageDetections:rows},{events:[]},{...context,month:'2025-11'});
  assert.equal(nov[0].lifecycle,'new');
  assert.deepEqual(reviewMonthGroups(nov).map(x=>[x.month,x.lifecycle,x.count]),[['2025-11','new',1],['2025-10','tracking',3]]);
});

test('recovery considers only the originally triggered domains at the review month',()=>{
  const comm=detection('개포3동','40대','2025-10');
  const both=detection('삼성2동','40대','2025-10',true,true);
  const movement=detection('신사동','40대','2025-10',false,true);
  const tracking={events:[event(comm,[point('2025-11',below,below),point('2025-12',recovered,below)]),event(both,[point('2025-12',recovered,below)]),event(movement,[point('2025-12',below,recovered)])]};
  assert.deepEqual(serviceReviewCases({ageDetections:[comm,both,movement]},tracking,context).map(x=>x.district),['삼성2동']);
  assert.equal(serviceReviewCases({ageDetections:[comm]},tracking,{...context,month:'2025-11'}).length,1);
  assert.equal(serviceReviewCases({ageDetections:[comm]},tracking,{...context,month:'2025-10'}).length,1);
});

test('missing, mixed or unavailable observations remain for review; later data cannot establish recovery',()=>{
  const rows=['개포3동','삼성2동','역삼1동'].map(name=>detection(name,'40대','2025-10'));
  const events=[event(rows[0],[point('2026-01',recovered,recovered)]),event(rows[1],[point('2025-12','mixed_recovery',recovered)]),event(rows[2],[point('2025-12','unavailable',recovered)])];
  assert.equal(serviceReviewCases({ageDetections:rows},{events},context).length,3);
});

test('repeated events in the same group stay distinct and saved work always uses the original month',()=>{
  const rows=[detection('역삼2동','30대','2025-10'),detection('역삼2동','30대','2025-11')];
  const items=serviceReviewCases({ageDetections:[...rows,rows[0]]},{events:[]},context);
  assert.equal(items.length,2);
  assert.equal(new Set(items.map(reviewCaseKey)).size,2);
  const older=selectedReviewCase(items,context,'2025-10');
  assert.deepEqual(serviceReviewContext(context,older),{...context,month:'2025-10'});
  assert.equal(context.month,'2025-12');
  assert.equal(selectedReviewCase(items,context,'missing').signalMonth,'2025-11');
});

test('no earlier event or another city yields no selectable group',()=>{
  const analysis={ageDetections:[detection('개포3동','40대','2025-10')]};
  for(const month of ['2025-07','2025-08','2025-09']) assert.deepEqual(serviceReviewCases(analysis,{events:[]},{...context,month}),[]);
  assert.deepEqual(serviceReviewCases(analysis,{events:[]},{...context,city:'춘천시'}),[]);
  assert.equal(selectedReviewCase([],context,''),null);
  assert.deepEqual(serviceReviewContext(context,null),{city:'강남구',district:'',month:'2025-12'});
});
