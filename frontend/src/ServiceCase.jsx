import React from 'react';
import {Icon} from './components';
import {SignalBadges,signalExplanation} from './DetectionEvidence';
import {serviceDomains} from './serviceCase.mjs';
import './service-case.css';
import DetectionCaseSelector from './DetectionCaseSelector';

const METHODS={absolute:'자체 과거 비교',local:'공통 변화 제거 후 비교',both:'두 비교 모두',none:'탐지 방식 확인 필요'};
const LABELS={call_contacts:'전화 연락',text_contacts:'문자 연락',weekday_move_count:'평일 이동',weekend_move_count:'휴일 이동'};
const fmt=v=>Math.abs(v).toLocaleString('ko-KR',{maximumFractionDigits:2});

export default function ServiceCase({context,detection,assessment,workflow,busy,onConfirm,cases,onCaseChange}) {
  const domains=serviceDomains(detection), reviewed=workflow.done?.includes(1);
  const stale=workflow.analysis_changed;
  return <section className="card service-case" aria-label="연결된 탐지 사례">
    <header className="service-case-heading"><h2>{context.district || '행정동 선택 필요'}{context.age && ` · ${context.age}`}</h2>
      <span className="service-case-month">{context.month || '탐지월 선택 필요'}</span>
      {domains.map(d=><span key={d.key} className={`service-case-chip ${d.state}`}><Icon name={d.key==='communication'?'chat':'chart'} size={18}/>{d.key==='communication'?'전화·문자 연락':'평일·휴일 이동'} 감소 탐지</span>)}
      <DetectionCaseSelector items={cases || []} selected={context} onSelect={onCaseChange} disabled={busy}/>
    </header>
    {domains.map(d=><div key={d.key} className={`service-case-domain ${d.state}`}>
      <div className="service-case-explanation">{d.state!=='none'&&<SignalBadges absolute={d.absolute} local={d.local}/>}<p>{signalExplanation(d.absolute,d.local,context.city)}</p></div>
      <div className="service-case-values">{d.metrics.map(metric=>{
        const row=assessment.find(r=>r.case_id===detection.case_id && r.metric===metric);
        const value=row?.change_pct;
        return <article key={metric}><Icon name={metric==='call_contacts'?'phone':metric==='text_contacts'?'chat':'chart'} size={26}/><div><h3>{LABELS[metric]}</h3><strong>{Number.isFinite(value)?`${fmt(value)}% ${value<0?'감소':value>0?'증가':'변화 없음'}`:'변화율 자료 없음'}</strong></div></article>;
      })}<aside>{domains.length===1&&<span className="service-case-neutral">{d.key==='communication'?'이동':'통신'} 미탐지</span>}<p>탐지 방식: {METHODS[d.state]}</p></aside></div>
    </div>)}
    {!domains.length&&<p className="service-case-empty">{detection?'선택한 동·연령대·월에는 탐지된 신호가 없습니다.':'탐지 현황에서 검토할 행정동·연령대·탐지월을 선택해 주세요.'}</p>}
    <footer className="service-case-actions"><p><Icon name="clipboard" size={22}/>{stale?'저장된 분석과 현재 분석이 다릅니다. 기존 업무 기록을 확인해 주세요.':reviewed?'탐지 근거 검토를 완료했습니다. 아래에서 관련 사업을 조회하세요.':'탐지 근거를 확인한 뒤 검토 완료를 눌러주세요.'}</p>
      <button className="primary" disabled={busy||reviewed||stale||!detection?.any_signal} onClick={onConfirm}>{busy?'저장 중…':reviewed?'✓ 근거 검토 완료됨':'✓ 근거 검토 완료'}</button></footer>
  </section>;
}
