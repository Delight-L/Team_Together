import React from 'react';
import {Icon} from './components';
import {SignalBadges,signalExplanation} from './DetectionEvidence';
import {serviceDomains} from './serviceCase.mjs';
import './service-case.css';
import ServiceReviewSelector from './ServiceReviewSelector';

const METHODS={absolute:'자체 과거 비교',local:'공통 변화 제거 후 비교',both:'두 비교 모두',none:'탐지 방식 확인 필요'};
const LABELS={call_contacts:'전화 연락',text_contacts:'문자 연락',weekday_move_count:'평일 이동',weekend_move_count:'휴일 이동'};
const fmt=v=>Math.abs(v).toLocaleString('ko-KR',{maximumFractionDigits:2});

export default function ServiceCase({context,detection,assessment,workflow,busy,onConfirm,cases,onCaseChange,reviewMonth,reviewSelection,casesLoading,casesError,caseFilter,onCaseFilter,fromChatContext=false}) {
  const domains=serviceDomains(detection), reviewed=workflow.done?.includes(1);
  const stale=workflow.analysis_changed;
  const hasCase=Boolean(detection?.any_signal);
  const following=reviewSelection?.lifecycle==='tracking';
  return <section className="card service-case" aria-label="연결된 탐지 사례">
    <ServiceReviewSelector items={cases || []} selected={reviewSelection} filter={caseFilter} onFilter={onCaseFilter} onSelect={onCaseChange} busy={busy} loading={casesLoading}/>
    <header className="service-case-heading"><h2>{(hasCase || (fromChatContext && context.district)) ? `${context.district}${context.age ? ` · ${context.age}` : ''}` : casesLoading ? '검토 사례를 확인하고 있습니다' : casesError ? '검토 사례 확인 필요' : '검토할 탐지 사례가 없습니다'}</h2>
      {hasCase&&<span className={`service-review-lifecycle ${following?'tracking':'new'}`}>{following?'이전 탐지 · 추적 중':'이달 신규 탐지'}</span>}
      {domains.map(d=><span key={d.key} className={`service-case-chip ${d.state}`}><Icon name={d.key==='communication'?'chat':'chart'} size={18}/>{d.key==='communication'?'전화·문자 연락':'평일·휴일 이동'} 감소 탐지</span>)}
    </header>
    {hasCase&&<p className="service-review-dates"><span>최초 탐지월 <b>{context.month}</b></span><span>검토 기준월 <b>{reviewMonth}</b></span></p>}
    {hasCase&&<p className="service-original-values">최초 탐지 당시 변화</p>}
    {domains.map(d=><div key={d.key} className={`service-case-domain ${d.state}`}>
      <div className="service-case-explanation">{d.state!=='none'&&<SignalBadges absolute={d.absolute} local={d.local}/>}<p>{signalExplanation(d.absolute,d.local,context.city)}</p></div>
      <div className="service-case-values">{d.metrics.map(metric=>{
        const row=assessment.find(r=>r.case_id===detection.case_id && r.metric===metric);
        const value=row?.change_pct;
        return <article key={metric}><Icon name={metric==='call_contacts'?'phone':metric==='text_contacts'?'chat':'chart'} size={26}/><div><h3>{LABELS[metric]}</h3><strong>{Number.isFinite(value)?`${fmt(value)}% ${value<0?'감소':value>0?'증가':'변화 없음'}`:'변화율 자료 없음'}</strong></div></article>;
      })}<aside>{domains.length===1&&<span className="service-case-neutral">{d.key==='communication'?'이동':'통신'} 미탐지</span>}<p>탐지 방식: {METHODS[d.state]}</p></aside></div>
    </div>)}
    {!hasCase&&!fromChatContext&&!casesLoading&&!casesError&&<p className="service-case-empty">선택한 기준월에는 신규 탐지 또는 추적 중인 사례가 없습니다.</p>}
    {hasCase&&<footer className="service-case-actions"><p><Icon name="clipboard" size={22}/>{stale?'저장된 분석과 현재 분석이 다릅니다. 기존 업무 기록을 확인해 주세요.':reviewed?'탐지 근거 검토를 완료했습니다. 아래에서 관련 사업을 조회하세요.':'탐지 근거를 확인한 뒤 검토 완료를 눌러주세요.'}</p>
      <button className="primary" disabled={busy||reviewed||stale||!detection?.any_signal} onClick={onConfirm}>{busy?'저장 중…':reviewed?'✓ 근거 검토 완료됨':'✓ 근거 검토 완료'}</button></footer>}
  </section>;
}
