import assert from 'node:assert/strict';
import test from 'node:test';
import { briefingStats, rankedCases, casePage, caseMetrics, metricSeries, sixMonths, caseNarrative, caseQuestionDraft } from '../src/briefingData.js';

const metric = (label, change, signal, z) => ({ metric_label: label, change_pct: change,
  is_risk_signal: signal, risk_robust_z: z, has_enough_history: true, relative_change_pp: -1 });
const candidate = { name: '삼성1동', count: 2, status: '신규 후보', pending: false, minZ: -2.67,
  rows: [metric('전화 연락', 0.1, false, -0.74), metric('문자 연락', -3.7, false, -0.03),
    metric('평일 이동', -6.1, true, -2.67), metric('휴일 이동', 3.6, true, -2.42)] };

test('실제 후보를 참고 지역의 단일 낮은 Z보다 먼저 표시한다', () => {
  const reference = { name: '참고동', count: 0, status: '기준 미해당', pending: false, minZ: -9, rows: [metric('전화 연락', 0, false, -9)] };
  const ranked = rankedCases([reference, candidate, { name: '자료없음', rows: [], count: 0 }]);
  assert.equal(ranked[0].name, '삼성1동');
  assert.equal(ranked[1].status, '기준 미해당');
  assert.equal(ranked.length, 2);
});

test('신규 6곳과 연속 1곳은 첫 페이지에서 모두 확인할 수 있다', () => {
  const candidates = Array.from({ length: 7 }, (_, i) => ({ ...candidate, name: `후보${i}`, status: i === 6 ? '연속 후보' : '신규 후보' }));
  const references = Array.from({ length: 14 }, (_, i) => ({ ...candidate, name: `참고${i}`, count: 0, status: '기준 미해당' }));
  const ordered = rankedCases([...references, ...candidates]);
  const first = casePage(ordered);
  assert.equal(first.items.filter((r) => r.status === '신규 후보').length, 6);
  assert.equal(first.items.filter((r) => r.status === '연속 후보').length, 1);
  const all = Array.from({ length: first.totalPages }, (_, page) => casePage(ordered, page).items).flat();
  assert.deepEqual(all, ordered);
  assert.equal(new Set(all.map((r) => r.name)).size, 21);
  assert.equal(casePage(ordered.slice(0, 8), 2).page, 1);
  assert.equal(casePage([candidate]).items.length, 1);
});

test('카드에는 판정된 지표를 먼저 보여주며 증가한 원자료도 후보일 수 있다', () => {
  const selected = caseMetrics(candidate);
  assert.deepEqual(selected.map((row) => row.metric_label), ['평일 이동', '휴일 이동']);
  assert.equal(selected[1].change_pct, 3.6);
  const text = caseNarrative(candidate, selected);
  assert(text.includes('6.1% 감소'));
  assert(text.includes('3.6% 증가'));
  assert(text.includes('공통 변화를 보정'));
});

test('비교 이력이 없는 신규/연속 건수를 0으로 확정하지 않는다', () => {
  const stats = briefingStats([candidate], [], '강남구', '2025-12', ['2025-12']);
  assert.equal(stats[0].value, null);
  assert.equal(stats[1].value, null);
  const withPrevious = briefingStats([candidate], [{ 기준연월: '2025-11', has_enough_history: true }], '강남구', '2025-12', ['2025-11', '2025-12']);
  assert.equal(withPrevious[0].value, 1);
  assert.equal(withPrevious[1].value, 0);
});

test('6개월은 기준월에서 끝나고 연도 경계를 올바르게 처리한다', () => {
  assert.deepEqual(sixMonths('2025-02'), ['2024-09', '2024-10', '2024-11', '2024-12', '2025-01', '2025-02']);
});

test('원자료 그래프는 선택 지역·지표·기준월을 지키며 누락을 보간하지 않는다', () => {
  const row = { 행정동명: '삼성1동', metric_label: '평일 이동', metric_unit: '회' };
  const result = metricSeries([
    { ...row, 기준연월: '2025-10', metric_value: 33.4 },
    { ...row, 기준연월: '2025-12', metric_value: 21.2 },
    { ...row, 기준연월: '2026-01', metric_value: 999 },
    { ...row, 행정동명: '다른동', 기준연월: '2025-11', metric_value: 999 },
    { ...row, metric_label: '휴일 이동', 기준연월: '2025-11', metric_value: 999 },
  ], '삼성1동', '평일 이동', '2025-12');
  assert(result.raw);
  assert.equal(result.unit, '회');
  assert.equal(result.points.at(-2).value, null);
  assert.equal(result.points.at(-1).value, 21.2);
  assert(!result.points.some((point) => point.value === 999));
});

test('원자료 열이 없는 업로드는 변화율과 올바른 단위로 표시한다', () => {
  const result = metricSeries([{ 행정동명: '삼성1동', metric_label: '평일 이동', 기준연월: '2025-12', change_pct: -6.1, metric_value: null }], '삼성1동', '평일 이동', '2025-12');
  assert.equal(result.raw, false);
  assert.equal(result.unit, '%');
  assert.equal(result.points.at(-1).value, -6.1);
});

test('참고 지역과 판단 보류를 변화 후보로 설명하지 않는다', () => {
  assert(caseNarrative({ ...candidate, count: 0, pending: false }, []).includes('변화 후보는 없습니다'));
  assert(caseNarrative({ ...candidate, count: 0, pending: true }, []).includes('판단을 보류'));
});

test('챗봇 질문 초안은 선택한 실제 지표와 기준월을 포함한다', () => {
  const question = caseQuestionDraft(candidate, '강남구', '2025-12', caseMetrics(candidate));
  assert(question.includes('삼성1동, 2025-12'));
  assert(question.includes('전월 변화율 -6.1%'));
  assert(question.includes('Robust Z -2.42'));
  assert(question.includes('원인을 단정하지 말고'));
  assert(question.length < 2000);
});
