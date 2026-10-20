import React, { useEffect, useRef } from 'react';
import { reportChecks } from './experienceLogic.mjs';

// 데이터 기준 창: 지역 분석·데이터 관리의 «데이터 기준 보기»에서 엽니다.
export function DataDialog({ onClose, data, context, rows, user }) {
  const dialog = useRef(null);
  useEffect(() => { const el = dialog.current; el.showModal(); return () => el.close(); }, []);
  return <dialog ref={dialog} className="support-dialog" aria-labelledby="data-dialog-title" onClose={() => { if (!dialog.current?.open) onClose(); }}>
    <header className="experience-toolbar"><h2 id="data-dialog-title">데이터 기준</h2><button className="secondary" onClick={onClose} aria-label="데이터 기준 닫기">닫기</button></header>
    <DataSummary data={data} context={context} rows={rows} user={user} expanded />
  </dialog>;
}

// 일반 사용자에게는 쉬운 설명만, 관리자에게는 분석 버전 같은 기술 정보까지 보여 줍니다.
export function DataSummary({ data, context, rows, user, expanded = false }) {
  const previous = data.months.filter(m => m < context.month).at(-1);
  return <details open={expanded || undefined} className="card data-summary"><summary>데이터 기준 · {context.month}</summary>
    <dl><dt>분석 자료</dt><dd>읍·면·동별 통화·문자·평일 이동·휴일 이동 분석{user?.admin ? ` (${data.source})` : ''}</dd>
      <dt>제공 기간</dt><dd>{data.months[0] || '자료 없음'} ~ {data.months.at(-1) || '자료 없음'}</dd>
      <dt>선택 지역 자료</dt><dd>{context.district ? `${context.district} · ${rows.length}개 지표` : '읍·면·동을 선택하면 제공 범위를 확인할 수 있습니다.'}</dd>
      <dt>누락·이력 부족</dt><dd>과거 이력 부족 {rows.filter(r => !r.has_enough_history).length}개 · 전월 변화값 누락 {rows.filter(r => !Number.isFinite(r.change_pct)).length}개</dd></dl>
    <h3>확인 후보는 어떻게 정하나요?</h3>
    <p>시·군·구 전체의 공통 변화를 뺀 뒤, 과거 흐름과 얼마나 다른지(평소 대비 차이)를 살펴봅니다. 전화·문자 또는 평일·휴일 이동의 값이 모두 -2 이하일 때 후보로 표시하며, 최소 12회 과거 이력이 필요합니다.</p>
    <p className="hint">지역 집계 결과이며 개인의 고립 여부를 판정하지 않습니다. 춘천시의 실제 분석 결과는 아직 연결되지 않았습니다.</p>
    {user?.admin && <details className="secondary-details"><summary>분석 버전·갱신 정보 (관리자)</summary><dl>
      <dt>분석 규칙</dt><dd>analysis2-v11 · 공통 변화 제거 후 Robust Z</dd>
      <dt>이전 분석월</dt><dd>{previous || '이전 분석월 없음'} · 신규/연속 후보 비교 기준입니다. 전월 변화율은 원자료에 계산된 값을 사용합니다.</dd>
      <dt>전체 근거 행</dt><dd>{data.assessment.length.toLocaleString()}개</dd>
      <dt>결과 버전</dt><dd>{data.runId}</dd>
      <dt>분석 파일 변경</dt><dd>{data.analysisFileModifiedAt || '미확인'} · 원천자료 갱신일은 별도 확인이 필요합니다.</dd>
      <dt>연결 확인</dt><dd>{data.dataCheckedAt || '미확인'}</dd>
    </dl></details>}
  </details>;
}


export function ReportQuality({ content, workflow }) {
  if (!content) return null;
  const { strong, unmatched, missingServiceSource, pending } = reportChecks(content, workflow);
  const attention = strong || unmatched.length > 0 || missingServiceSource || pending > 0;
  return <details className="report-quality" open={attention || undefined}><summary>보고서 검토 도움말{attention ? ' · 확인할 항목 있음' : ''}</summary><ul>{pending > 0 && <li>‘담당자 검토 전’ 표시가 {pending}곳 남아 있습니다. 확인을 마친 사업은 검토 결과로 고쳐 주세요. 그대로 두면 보고서에 검토 전으로 남습니다.</li>}<li>{workflow.analysis_source ? `분석 출처: ${workflow.analysis_source}` : '분석 출처가 기록되어 있는지 확인하세요.'}</li><li>{unmatched.length ? `저장된 분석값과 바로 대조되지 않는 수치: ${unmatched.map(n => n + '%').join(', ')}. 사업 지원 비율 등 별도 출처가 있는 값인지 확인하세요.` : '입력된 백분율에서 저장된 분석값과 다른 수치가 발견되지 않았습니다. 지표·기간의 연결은 직접 확인하세요.'}</li>{workflow.reviews?.length > 0 && <li>{missingServiceSource ? '원문 출처가 누락된 사업 기록이 있습니다. 운영기관에 확인하세요.' : '저장된 사업 원문 링크를 참고해 자격·접수 여부를 확인하세요.'}</li>}<li>{strong ? '고립 판정 또는 효과 단정으로 읽힐 수 있는 표현이 있습니다. 지역 변화 근거에 맞게 수정하세요.' : '지역 집계 신호이며 개인의 고립 판정으로 표현하지 않았는지 확인하세요.'}</li></ul><p className="hint">자동 점검은 보조 안내입니다. 전체 수치의 정확성이나 문장 의미를 보증하지 않습니다.</p></details>;
}
