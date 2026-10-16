import { test } from 'node:test';
import assert from 'node:assert/strict';
import { signalCount, ageStatus, normalizeAgeNames, relevantScores } from '../src/ageSignals.mjs';

test('count cases once across communication metrics, keep two ages separate', () => {
  const rows=[{case_id:'30',is_risk_signal:true},{case_id:'30',is_risk_signal:true},{case_id:'50',is_risk_signal:true},{case_id:'50',is_risk_signal:true}];
  assert.equal(signalCount(rows),2);
  assert.equal(signalCount([{is_risk_signal:true},{is_risk_signal:true}]),2);
});
test('candidate follows exact dong, month and age; sex is never a detection dimension', () => {
  const cases=[{code:'1123059',month:'2025-10',age_band:'30s',age:'30대',any_signal:true,signal_status:'New',assessment_status:'assessed'}];
  const g={code:'1123059',month:'2025-10',age:'30대',sex:'남성'};
  assert.equal(ageStatus(cases,g).count,1);
  assert.deepEqual(ageStatus(cases,g),ageStatus(cases,{...g,sex:'여성'}));
  assert.equal(ageStatus(cases,{...g,age:'20대'}),undefined);
  assert.equal(ageStatus(cases,{...g,month:'2025-12'}),undefined);
});
test('dong rename preserves its source name, code, age case and count without mutating input', () => {
  const source={analysisScope:'dong_age',assessment:[{'행정동코드':'1123074','행정동명':'일원2동',case_id:'x',is_risk_signal:true}],ageDetections:[{code:'1123074',district:'일원2동'}]};
  const normalized=normalizeAgeNames(source);
  assert.equal(normalized.assessment[0]['행정동명'],'개포3동');
  assert.equal(normalized.assessment[0].source_district,'일원2동');
  assert.equal(source.assessment[0]['행정동명'],'일원2동');
  assert.equal(signalCount(normalized.assessment),1);
  assert.deepEqual(normalizeAgeNames(normalized),normalized);
});
test('candidate summary uses its triggered metrics, not a different unflagged age', () => {
  assert.deepEqual(relevantScores([{is_risk_signal:true,risk_robust_z:-4.38},{is_risk_signal:false,risk_robust_z:-9}]),[-4.38]);
});

import { restoreWorkspace } from '../src/groupTabs.mjs';
test('analysis migration marker survives restoring the workspace', () => {
  assert.equal(restoreWorkspace({analysisVersion:'original-model',month:'2025-11'},'강남구').analysisVersion,'original-model');
});

import { detectionTabs } from '../src/ageSignals.mjs';
import { groupLabel, groupKey, availableWorkspace } from '../src/groupTabs.mjs';
test('all monthly detections open once without a sex label and survive restoration', () => {
  const cases = Array.from({length:9},(_,i) => ({code:'1123059',district:'삼성2동',age:String(20+i)+'대',month:'2025-10',any_signal:true}));
  cases[0].age='20대';
  cases.push({...cases[0]}, {...cases[0],month:'2025-11'}, {...cases[0],age:'60대 이상',any_signal:false});
  const tabs = detectionTabs(cases,'강남구','2025-10');
  assert.equal(tabs.length,9);
  assert.equal(detectionTabs(cases,'강남구','2025-11').length,1);
  assert.equal(detectionTabs(cases,'강남구','2025-12').length,0);
  assert.equal(groupLabel(tabs[0]),'삼성2동 · 20대');
  const state = restoreWorkspace({tabs:[tabs[0]],active:groupKey(tabs[0])},'강남구');
  assert.equal(state.tabs.length,1);
  assert.equal(availableWorkspace(state,{districts:[{code:'1123059',name:'삼성2동'}],months:['2025-10'],ages:['20대'],sexes:['남성','여성']},'2025-10').tabs.length,1);
});

import { observationWindow } from '../src/ageSignals.mjs';
test('observation window is three months BEFORE the label, including year boundaries', () => {
 assert.equal(observationWindow('2025-10'),'2025.07–09');
 assert.equal(observationWindow('2025-11'),'2025.08–10');
 assert.equal(observationWindow('2026-02'),'2025.11–2026.01');
 assert.equal(observationWindow('2026-01'),'2025.10–12');
 assert.equal(observationWindow('2025-13'),'');
});
