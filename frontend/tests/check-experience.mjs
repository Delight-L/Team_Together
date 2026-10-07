import assert from 'node:assert/strict';
import { reportChecks } from '../src/experienceLogic.mjs';

const workflow = { analysis_source: 'CSV', analysis_evidence: [{ change_pct: -6.123, risk_robust_z: -2.33 }], reviews: [{ source_url: 'https://example.org/service' }] };
assert.deepEqual(reportChecks({ summary: '전월 대비 -6.1%' }, workflow).unmatched, []);
assert.deepEqual(reportChecks({ summary: '전월 대비 99%' }, workflow).unmatched, [99]);
assert.equal(reportChecks({ summary: '개인의 고립으로 확정' }, workflow).strong, true);
assert.equal(reportChecks({ summary: '지역 변화 후보를 확인' }, workflow).strong, false);
assert.equal(reportChecks({}, { reviews: [{}] }).missingServiceSource, true);
assert.equal(reportChecks({}, {}).missingSource, true);
console.log('보고서 보조 점검 검사 통과');
