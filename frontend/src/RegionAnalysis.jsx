import React,{lazy,Suspense,useEffect,useMemo,useState} from 'react';
import {createPortal} from 'react-dom';
import {api,query} from './api';
import {REGION_AGES,CLUSTER_COLORS,contextPeriods,consumptionPeriods,periodLabel,consumptionRows,surveyRows} from './regionInsights.mjs';
import './region-analysis.css';
const ClusterMap=lazy(()=>import('./ClusterMap'));
const fmt=(v,n=1)=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:n,minimumFractionDigits:n}):'자료 없음';

function ConsumptionChart({rows,label}) {
 const values=rows.filter(r=>r.available&&Number.isFinite(r.change)).map(r=>r.change);
 const min=Math.floor(Math.min(0,...values)/10)*10, upper=Math.ceil(Math.max(0,...values)/10)*10;
 const max=upper===min?min+10:upper, range=max-min, y=v=>(max-v)/range*100;
 const ticks=Array.from({length:Math.round(range/10)+1},(_,i)=>min+i*10);
 return <div className="ri-consumption-chart" role="img" aria-label={`${label} 소비영역별 일평균 결제건수 변화율`}>
  <div className="ri-column-plot">{ticks.map(v=><div key={v} className={`ri-column-gridline ${v===0?'zero':''}`} style={{top:`${y(v)}%`}}><span>{v}%</span></div>)}
   <div className="ri-columns">{rows.map(r=>{const valid=r.available&&Number.isFinite(r.change),at=valid?y(r.change):y(0);return <div key={r.domain} className="ri-column" style={{'--column-color':r.change>0?'#F2BA78':'#8DAFDC','--column-ink':r.change>0?'#9A5A1D':'#355C91'}}>{valid?<><i style={{top:`${Math.min(y(0),at)}%`,height:`${Math.max(.4,Math.abs(at-y(0)))}%`}} title={`${r.label}: ${fmt(r.change)}%, 과거 ${fmt(r.baselineDaily,2)}건/일 → 현재 ${fmt(r.currentDaily,2)}건/일`}/><b className={r.change>0?'positive':'negative'} style={{top:`${at}%`}}>{r.change>0?'+':''}{fmt(r.change)}%</b></>:<span className="ri-column-missing">자료 없음</span>}</div>;})}</div>
  </div>
  <div className="ri-column-categories">{rows.map(r=><div key={r.domain}><strong>{r.label}</strong></div>)}</div>
 </div>;
}
export default function RegionAnalysis({city,district,onSelect,age,onAgeChange}){
 const [data,setData]=useState(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 const [period,setPeriod]=useState(''),[quarter,setQuarter]=useState('');
 const [surveyAge,setSurveyAge]=useState(REGION_AGES.includes(age)?age:'40대');
 const consumerAge=REGION_AGES.includes(age)?age:'40대';
 useEffect(()=>{let live=true;setData(null);setError('');api('/region-insights?'+query({city})).then(d=>{if(!live)return;setData(d);setPeriod(contextPeriods(d).at(-1)||'');setQuarter(consumptionPeriods(d).at(-1)||'');}).catch(e=>live&&setError(e.message));return()=>{live=false;};},[city,retry]);
 const periods=contextPeriods(data),quarters=consumptionPeriods(data);
 const regions=useMemo(()=>(data?.typologies||[]).filter(r=>r.period===period),[data,period]);
 const selected=regions.find(r=>r.name===district)||regions.find(r=>r.name==='일원본동')||regions[0];
 useEffect(()=>{if(selected&&selected.name!==district)onSelect(selected.name);},[selected?.name,district,onSelect]);
 const groups=[0,1,2].map(id=>({id,items:regions.filter(r=>r.cluster===id)})).filter(g=>g.items.length);
 const consumption=consumptionRows(data,selected?.code,consumerAge,quarter);
 const surveyYear=[...new Set((data?.surveys||[]).map(r=>r.year))].filter(y=>y<=Number(period.slice(0,4))).sort().at(-1);
 const survey=surveyRows(data,surveyAge,surveyYear);
 const surveyMax=Math.max(20,...survey.flatMap(r=>[r.gangnam,r.seoul]).filter(Number.isFinite).map(v=>Math.ceil(v*100/10)*10));
 const baseline=consumption.find(r=>r.available)?.baselinePeriods||[];
 const slot=document.getElementById('region-period-slot');
 return <div className="ri-root">
  {slot&&createPortal(<label>기준기간<select aria-label="지역 유형 기준기간" value={period} disabled={!periods.length} onChange={e=>setPeriod(e.target.value)}>{periods.map(p=><option key={p} value={p}>{periodLabel(p)}</option>)}</select></label>,slot)}
  {error?<div role="alert" className="error">{error}<button onClick={()=>setRetry(r=>r+1)}>다시 연결</button></div>:!data?<p role="status">지역 유형·소비·조사 자료를 읽고 있습니다…</p>:!regions.length?<section className="ri-topic"><h2>우리 동은 어떤 지역일까?</h2><p>{city}의 지역 유형·소비·조사 분석 자료가 아직 연결되지 않았습니다.</p></section>:<>
   <div className="ri-analysis-top">
   <section className="ri-topic ri-topic-map" aria-labelledby="ri-map-title"><header className="ri-topic-header"><h2 id="ri-map-title">우리 동은 어떤 지역일까?</h2><span>{city} {regions.length}개 동 · {periodLabel(period)}</span></header>
    <div className="ri-cluster-legend">{groups.map(g=><article key={g.id}><i style={{background:CLUSTER_COLORS[g.id]}}/><strong>{g.items[0].type}</strong></article>)}</div>
    <article className="ri-map-card"><header><strong>지역을 선택해 보세요</strong></header><Suspense fallback={<p role="status">지도를 준비하고 있습니다…</p>}><ClusterMap regions={regions} selected={selected?.name} onSelect={onSelect}/></Suspense></article>
   </section>
   <section className="ri-topic ri-topic-consumption" aria-labelledby="ri-consumption-title"><header className="ri-topic-header"><h2 id="ri-consumption-title">소비는 어떻게 달라졌을까?</h2><h3>{selected?.name} · {consumerAge}</h3><div className="ri-consumption-filters"><div className="ri-age-tabs ri-consumer-ages" role="group" aria-label="소비 고객 연령 선택">{REGION_AGES.map(a=><button key={a} aria-pressed={consumerAge===a} onClick={()=>onAgeChange(a)}>{a}</button>)}</div><select aria-label="소비 기준분기" value={quarter} onChange={e=>setQuarter(e.target.value)}>{quarters.map(p=><option key={p} value={p}>{periodLabel(p)}</option>)}</select></div></header><div className="ri-consumption-key"><span>● 감소</span><span>● 증가</span><small>기준: {baseline.length?`${baseline[0].slice(0,4)}~${baseline.at(-1).slice(0,4)}년 ${baseline[0].slice(-1)}분기 평균`:'비교 자료 부족'} · 공통 관측 업종</small></div><ConsumptionChart rows={consumption} label={`${selected?.name} ${consumerAge} ${quarter}`}/><p className="ri-consumption-description">일평균 결제건수 · 과거 같은 분기 평균 대비</p></section>
   </div>
   <section className="ri-topic ri-topic-survey" aria-labelledby="ri-survey-title"><header className="ri-topic-header"><h2 id="ri-survey-title">강남구 주민들의 사회적 연결 마음 지표</h2><div className="ri-age-tabs" role="group" aria-label="서울서베이 연령대 선택">{REGION_AGES.map(a=><button key={a} aria-pressed={surveyAge===a} onClick={()=>setSurveyAge(a)}>{a}</button>)}</div></header>
    <div className="ri-survey-grid">{survey.map(r=><article key={r.metric}><h3>{r.label}</h3>{[['gangnam',city],['seoul','서울 전체']].map(([key,name])=><div className={`ri-survey-bar ${key}`} key={key}><span>{name}</span><div><i style={{width:Number.isFinite(r[key])?`${r[key]*100/surveyMax*100}%`:'0%'}}/></div><b>{Number.isFinite(r[key])?`${fmt(r[key]*100)}%`:'자료 없음'}</b></div>)}<div className="ri-survey-scale">{[0,.25,.5,.75,1].map(f=><span key={f}>{fmt(surveyMax*f,0)}%</span>)}</div></article>)}</div><p className="ri-survey-source">기준: 2022-2025 서울서베이 구 · 연령별 연간 자료</p>
   </section>
  </>}
 </div>;
}
