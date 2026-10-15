import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {consumptionRows,surveyRows,boundaryCenter,CLUSTER_COLORS} from '../src/regionInsights.mjs';
const data=JSON.parse(readFileSync(new URL('../../data/processed/region_insights.json',import.meta.url)));
const boundaries=JSON.parse(readFileSync(new URL('../src/data/administrative-regions.json',import.meta.url))).features.filter(f=>f.properties.city==='강남구');
test('all 22 authoritative dong boundaries, including Gaepo3, match typologies',()=>{
 assert.equal(boundaries.length,22);
 assert.deepEqual(new Set(boundaries.map(f=>f.properties.name)),new Set(data.typologies.map(r=>r.name)));
 assert.deepEqual([0,1,2].map(id=>data.typologies.filter(r=>r.cluster===id).length),[7,3,12]);
 assert.equal(data.typologies.find(r=>r.name==='개포3동').cluster,1);
 for(const f of boundaries){assert.ok(boundaryCenter(f).every(Number.isFinite));assert.ok(CLUSTER_COLORS[data.typologies.find(r=>r.name===f.properties.name).cluster]);}
});
test('consumption changes with selected dong, customer age and exact quarter',()=>{
 const a=consumptionRows(data,'1123072','40대','2025Q4');
 assert.equal(a.length,5);assert.ok(Math.abs(a[0].change-(-22.587473843))<1e-6);assert.equal(a[1].change,200);
 assert.notDeepEqual(a,consumptionRows(data,'1123059','40대','2025Q4'));
 assert.notDeepEqual(a,consumptionRows(data,'1123072','30대','2025Q4'));
 assert.notDeepEqual(a,consumptionRows(data,'1123072','40대','2025Q3'));
 assert.ok(consumptionRows(data,'1123072','60대 이상','2025Q4').every(r=>r.age));
 assert.ok(consumptionRows(data,'missing','40대','2025Q4').every(r=>r.change===undefined));
});
test('survey compares same year and age at district scope; no dong allocation',()=>{
 const r=surveyRows(data,'40대',2025);
 assert.ok(Math.abs(r[0].gangnam*100-6.0513395)<1e-5);
 assert.ok(Math.abs(r[0].seoul*100-14.2343847)<1e-5);
 assert.notDeepEqual(r,surveyRows(data,'50대',2025));
 assert.ok(surveyRows(data,'40대',2030).every(r=>r.gangnam===null&&r.seoul===null));
});
