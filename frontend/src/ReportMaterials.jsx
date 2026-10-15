import React from 'react';
import { EvidenceTable } from './components';
import { reviewGroups } from './reviewPresentation.mjs';

export function reportSelection(workflow, selected) {
  const metrics = (workflow.analysis_evidence || []).filter(row => row.is_risk_signal).map(row => row.metric_label);
  const services = reviewGroups(workflow.reviews).map(group => group.key);
  return {
    metrics: (selected?.metrics || metrics.slice(0, 3)).filter(key => metrics.includes(key)),
    services: (selected?.services || services.slice(0, 4)).filter(key => services.includes(key)),
    include_note: selected?.include_note === true,
    include_followup: selected?.include_followup === true,
  };
}

export default function ReportMaterials({ workflow, selection, onChange, recordQuery, disabled }) {
  const groups = reviewGroups(workflow.reviews);
  const record = recordQuery.data;
  const toggle = (field, value, checked) => onChange({ ...selection, [field]: checked ? [...selection[field], value] : selection[field].filter(key => key !== value) });
  return <details className="secondary-details report-materials" open><summary>초안에 포함할 저장 근거 선택</summary>
    <fieldset disabled={disabled}><legend>후보 지표 · 저장 당시 분석</legend>
      {(workflow.analysis_evidence || []).filter(row => row.is_risk_signal).map(row => <label className="confirmation" key={row.metric_label}><input type="checkbox" checked={selection.metrics.includes(row.metric_label)} onChange={e => toggle('metrics', row.metric_label, e.target.checked)} />{row.metric_label}</label>)}
      {!workflow.analysis_evidence?.some(row => row.is_risk_signal) && <p className="hint">저장된 분석에 후보 지표가 없습니다.</p>}
    </fieldset>
    <fieldset disabled={disabled}><legend>사업 검토 · 사업별 최신 판단</legend>{groups.map(group => <label className="confirmation" key={group.key}><input type="checkbox" checked={selection.services.includes(group.key)} onChange={e => toggle('services', group.key, e.target.checked)} />{group.latest.name} · {group.latest.decision}</label>)}</fieldset>
    <fieldset disabled={disabled || recordQuery.loading || !!recordQuery.error}><legend>업무 기록에서 가져오기</legend>
      <label className="confirmation"><input type="checkbox" checked={selection.include_note} onChange={e => onChange({ ...selection, include_note: e.target.checked })} />검토 의견·인계 내용</label>
      <label className="confirmation"><input type="checkbox" checked={selection.include_followup} onChange={e => onChange({ ...selection, include_followup: e.target.checked })} />담당자·확인 기한·후속 조치</label>
    </fieldset>
    {recordQuery.loading ? <p className="hint" role="status">저장한 업무 기록을 불러오고 있습니다…</p> : recordQuery.error ? <p className="error" role="alert">업무 기록 조회 실패 · {recordQuery.error}</p> : <div className="hint"><p>검토 의견: {record?.note || '저장된 의견 없음'}</p><p>담당자 {record?.assignee || '미지정'} · 확인 기한 {record?.due || '미지정'}</p><p>후속 조치: {record?.followup || '저장된 조치 없음'}</p></div>}
    <button className="text-button" disabled={disabled || recordQuery.loading} onClick={recordQuery.reload}>업무 기록 다시 불러오기</button>
    <p className="hint">저장된 내용만 가져옵니다. 긴 근거는 문장 단위로 요약·생략되며 초안에서 확인할 수 있습니다.</p>
  </details>;
}

export function ReportEvidence({ workflow, content }) {
  const groups = reviewGroups(workflow.reviews).filter(group => !content.selection || content.selection.services?.includes(group.key));
  const rows = (workflow.analysis_evidence || []).filter(row => !content.selection || content.selection.metrics?.includes(row.metric_label));
  return <details className="secondary-details"><summary>작성 중인 문장과 저장 근거 대조</summary>
    <p className="hint">분석 출처: {workflow.analysis_source || '저장된 분석'} · 업무 시작 당시 근거</p>
    {rows.length > 0 && <EvidenceTable rows={rows} />}
    {groups.map(group => <p key={group.key}><b>{group.latest.name} · {group.latest.decision}</b><br/>{group.latest.note}</p>)}
    {content.experience_version != null && <p className="hint">업무 기록 {content.experience_version}차 저장본을 초안에 반영했습니다. 이후 기록이 바뀌면 최신 기록으로 초안을 갱신하세요.</p>}
  </details>;
}
