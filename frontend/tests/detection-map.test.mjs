import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {detectionMapRegions} from '../src/detectionMap.mjs';
const event=(age,communication,mobility={})=>({district:'삼성2동',age,signalMonth:'2025-10',signals:{communication,mobility}});
const classify=events=>detectionMapRegions([{name:'삼성2동'}],{available:true,events},'2025-10')[0];
test('different ages or domains stay mixed, never become a both-method case',()=>{
 assert.deepEqual(classify([event('30대',{absolute:true}),event('50대',{local:true})]).detectionMethods,['absolute','local']);
 assert.deepEqual(classify([event('30대',{absolute:true},{local:true})]).detectionMethods,['absolute','local']);
 const both=classify([event('30대',{absolute:true,local:true})]);
 assert.deepEqual(both.detectionMethods,['both']);assert.equal(both.count,1);
 assert.deepEqual(classify([event('30대',{absolute:true,local:true}),event('50대',{local:true})]).detectionMethods,['local','both']);
});
test('actual October nine cases occupy eight yellow districts; November has one teal district',()=>{
 const tracking=JSON.parse(readFileSync(new URL('../../data/processed/region_insights.json',import.meta.url),'utf8')).activityTracking;
 const regions=[...new Set(tracking.events.map(e=>e.district))].map(name=>({name}));
 const oct=detectionMapRegions(regions,tracking,'2025-10').filter(r=>r.count);
 assert.equal(oct.length,8);assert.equal(oct.reduce((n,r)=>n+r.count,0),9);assert(oct.every(r=>r.detectionMethods.join()==='absolute'));
 const nov=detectionMapRegions(regions,tracking,'2025-11').filter(r=>r.count);
 assert.equal(nov.length,1);assert.equal(nov[0].name,'역삼2동');assert.deepEqual(nov[0].detectionMethods,['local']);
 assert(detectionMapRegions(regions,tracking,'2025-12').every(r=>r.count===0));
});
