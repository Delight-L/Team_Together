import React,{useMemo,useState,useEffect} from 'react';
import {Icon} from './components';
import {qualityGroups,qualityPageFor,qualityMonthText,COVERAGE_MINIMUM} from './dataQuality.mjs';
import './data-quality.css';
import {ChartMotion,useChartProgress} from './ChartMotion';
const fmt=(value,digits=0)=>Number.isFinite(value)?value.toLocaleString('ko-KR',{maximumFractionDigits:digits}):'자료 없음';

function CoverageFill({coverage}) {
 const progress=useChartProgress();
 return <i style={{width:`${Math.max(0,Math.min(100,coverage*100))*progress}%`}}/>;
}
export default function DataQuality({analysis,city,active=true}) {
  const months=useMemo(()=>[...(analysis?.months || [])].sort(),[analysis?.months]);
  const groups=useMemo(()=>city==='강남구'?qualityGroups(analysis?.ageDetections || [],months):[],[analysis,city,months]);
  const [page,setPage]=useState(0),[selected,setSelected]=useState('');
  const pages=Math.max(1,Math.ceil(groups.length/2)),current=Math.min(page,pages-1);
  useEffect(()=>{setPage(0);setSelected('');},[city,months.join('/')]);
  const jump=id=>{setSelected(id);setPage(qualityPageFor(groups,id));};
  const changePage=p=>{setPage(p);setSelected(groups[p*2]?.id || '');};
  const first=groups[current*2];
  const chosen=groups.slice(current*2,current*2+2).some(g=>g.id===selected)?selected:first?.id || '';
  const pagerNumbers=Array.from({length:pages},(_,i)=>i).filter(i=>pages<=7||i===0||i===pages-1||Math.abs(i-current)<=1);
  const knownValues=groups.length>0&&groups.every(g=>g.hasValues);
  return <ChartMotion active={active&&Boolean(analysis)} replayKey={`${city}:${current}:${chosen}:${groups.map(g=>g.firstIssue.coverage).join("/")}`}><div className="dq-panel">
    <header className="dq-heading"><h2>자료 확인</h2><small>기준: {months.length?`${months[0].replace('-','.')}–${months.at(-1).slice(5)}`:'자료 확인 중'}</small></header>
    <div className="dq-notice"><p><span className="dq-info" aria-hidden="true">i</span>자료는 있지만, 유효 비율이 기준에 못 미친 사례입니다.</p>
      <label>집단 바로가기<select aria-label="자료 확인 집단 선택" value={chosen} disabled={!groups.length} onChange={e=>jump(e.target.value)}>
        {!groups.length&&<option value="">확인 대상 없음</option>}{groups.map(g=><option key={g.id} value={g.id}>{g.district} · {g.age}</option>)}
      </select></label></div>
    <div className="dq-summary"><article><span className="dq-summary-icon"><Icon name="services" size={30}/></span><div><span>확인 대상</span><strong>{groups.length}개 집단</strong></div></article><article><span className="dq-summary-icon"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6M17 2v6M3 10h18M7 14h2m4 0h2m-8 4h2m4 0h2"/></svg></span><div><span>영향 기준월</span><strong>{qualityMonthText(groups.flatMap(g=>g.affectedMonths))}</strong></div></article></div>
    {!analysis?<p role="status">자료를 확인하고 있습니다…</p>:!groups.length?<div className="dq-empty">{city}의 제공 기간에는 유효 비율 기준 미달 사례가 없습니다.</div>:<div className="dq-cards">{groups.slice(current*2,current*2+2).map(g=>{
      const issue=g.firstIssue;
      return <article className={`dq-card ${chosen===g.id?'chosen':''}`} key={g.id}>
        <h3><Icon name="report" size={24}/>{g.district} · {g.age}</h3>
        <div className="dq-value"><div><span>{Number(issue.month.slice(5))}월 {issue.label} 유효 비율</span><strong>{fmt(issue.coverage*100,2)}%</strong></div><small>판정 기준 {COVERAGE_MINIMUM*100}%</small></div>
        <div className="dq-bar" role="img" aria-label={`${g.district} ${g.age} ${issue.month} 유효 비율 ${fmt(issue.coverage*100,2)}%, 기준 ${COVERAGE_MINIMUM*100}%`}><CoverageFill coverage={issue.coverage}/><b style={{left:`${COVERAGE_MINIMUM*100}%`}}/></div>
        <p className="dq-population">총 추정 인구 {fmt(issue.total)} · 미추정 인구 {fmt(issue.unestimated)}</p>
        <ol className="dq-timeline">{g.timeline.map(t=><li className={t.kind} key={t.month}><b>{Number(t.month.slice(5))}월</b><span>{t.label}</span></li>)}</ol>
        {g.issues.length>1&&<details className="dq-more"><summary>기준 미달 자료 {g.issues.length}건 전체 보기</summary>{g.issues.map(i=><p key={i.month+i.metric}>{i.month} · {i.label} · {fmt(i.coverage*100,2)}%</p>)}</details>}
      </article>;
    })}</div>}
    <footer className="dq-pagination"><nav aria-label="자료 확인 페이지"><button disabled={current===0} onClick={()=>changePage(current-1)}>← 이전</button>{pagerNumbers.map((n,i)=><React.Fragment key={n}>{i>0&&n>pagerNumbers[i-1]+1&&<span>…</span>}<button aria-current={n===current?'page':undefined} className={n===current?'active':''} onClick={()=>changePage(n)}>{n+1}</button></React.Fragment>)}<button disabled={current===pages-1} onClick={()=>changePage(current+1)}>다음 →</button></nav><span>{current+1} / {pages} 페이지</span></footer>
    <aside className="dq-explanation"><h3><Icon name="report" size={22}/>확인된 내용</h3><div><p>{knownValues?'기준 미달 사례의 집계된 이동·연락 값은 존재합니다.':'유효 비율과 지표의 산출 가능 여부를 함께 확인합니다.'}</p><p>유효 비율 = 해당 지표의 유효 추정 인구 ÷ 총 추정 인구입니다.</p><p>미추정 인구가 늘어난 원인은 제공기관 확인이 필요합니다.</p></div></aside>
  </div></ChartMotion>;
}
