import React from 'react';
import { number } from './api';
import { ReviewWorkspace } from './Experience';

export function AnalysisSummary({ rows }) {
  const signals = rows.filter(row => row.is_risk_signal).map(row => row.metric_label);
  const pending = rows.filter(row => !row.has_enough_history).length;
  return <div className="analysis-summary">
    <strong>이번 달 먼저 확인할 변화</strong>
    <p>{signals.length ? `${signals.join('·')} 지표가 후보 기준에 해당합니다.` : pending ? '과거 이력이 부족한 지표가 있어 추가 자료 확인이 필요합니다.' : '현재 후보 기준에 해당하는 지표가 없습니다.'}</p>
    <p className="hint">{signals.length > 0 && pending > 0 ? `별도로 이력 부족 ${pending}개 지표가 있습니다. ` : ''}지역 집계 신호이며 개인의 고립이나 변화 원인을 확정하지 않습니다.</p>
  </div>;
}

export function EvidenceExplanation({ rows, workflow }) {
  const saved = workflow.analysis_evidence || [];
  const labels = [...new Set([...saved, ...rows].map(row => row.metric_label))];
  return <>
    <details className="secondary-details"><summary>변화율·공통 변화·점수는 무엇이 다른가요?</summary>
      <p><b>전월 변화율(%)</b>은 지난달과 비교해 늘거나 줄어든 정도입니다.</p>
      <p><b>공통 변화를 뺀 전월 변화(%p)</b>는 시·군·구 전체 흐름과 해당 지역 변화의 차이입니다.</p>
      <p><b>평소 대비 점수</b>는 공통 변화를 제거한 뒤 과거 변동 폭과 비교한 단위 없는 값입니다. 백분율이 아니며, 전월 변화율만으로 후보를 판정하지 않습니다.</p>
    </details>
    {saved.length > 0 && <details className="secondary-details"><summary>업무 저장 당시 근거와 현재 분석 비교{workflow.analysis_changed ? ' · 분석 버전 변경됨' : ''}</summary>
      <p className="hint">표 위의 분석은 현재 자료입니다. 사업 검토·보고서는 업무 시작 당시 저장한 근거를 사용합니다. 근거를 바꾸려면 ‘새 분석으로 다시 시작’을 사용하세요.</p>
      <div className="table-scroll"><table><thead><tr><th>지표</th><th>저장 당시 전월 변화</th><th>현재 전월 변화</th><th>저장 당시 / 현재 판정</th></tr></thead><tbody>{labels.map(label => {
        const old = saved.find(row => row.metric_label === label), current = rows.find(row => row.metric_label === label);
        const value = row => row ? `${number(row.change_pct)}${Number.isFinite(row.change_pct) ? '%' : ''}` : '자료 없음';
        const status = row => !row ? '자료 없음' : !row.has_enough_history ? '이력 부족' : row.is_risk_signal ? '확인 후보' : '기준 미해당';
        return <tr key={label}><td>{label}</td><td>{value(old)}</td><td>{value(current)}</td><td>{status(old)} / {status(current)}</td></tr>;
      })}</tbody></table></div>
    </details>}
  </>;
}

export function AnalysisReview({ context, user, onView }) {
  return <details className="card info-card analysis-inline-review"><summary>근거를 보며 검토 의견 작성 · 업무 기록과 공유</summary>
    <ReviewWorkspace compact key={user.id + JSON.stringify(context)} context={context} user={user} onView={onView} />
  </details>;
}
