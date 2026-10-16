import React,{lazy,Suspense,useEffect,useMemo,useState} from 'react';
import {createPortal} from 'react-dom';
import {api,query} from './api';
import {REGION_AGES,CLUSTER_COLORS,contextPeriods,consumptionPeriods,periodLabel,consumptionRows,surveyRows} from './regionInsights.mjs';
import './region-analysis.css';
const ClusterMap=lazy(()=>import('./ClusterMap'));
const fmt=(v,n=1)=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:n,minimumFractionDigits:n}):'자료 없음';

function ConsumptionChart({rows,label}){
 const values=rows.filter(r=>r.available&&Number.isFinite(r.change)).map(r=>r.change);
 const min=Math.min(-25,...values),max=Math.max(25,...values),range=max-min;
 const left=235,right=1050,x=v=>left+(v-min)/range*(right-left),zero=x(0);
 const ticks=[min,0,max/2,max].filter((v,i,a)=>a.indexOf(v)===i);
 return <svg className="ri-consumption-chart" viewBox="0 0 1200 290" role="img" aria-label={`${label} 소비영역별 일평균 결제건수 변화율`}>
  {ticks.map(v=><g key={v}><line x1={x(v)} x2={x(v)} y1="15" y2="251" stroke={v===0?'#8ca0bd':'#e4edf8'} strokeDasharray={v===0?'4 4':undefined}/><text x={x(v)} y="278" textAnchor="middle" className="ri-axis">{fmt(v)}%</text></g>)}
  {rows.map((r,i)=>{const y=39+i*46,valid=r.available&&Number.isFinite(r.change),px=valid?x(r.change):zero,color=r.change>0?'#2cad94':'#4d85ea';return <g key={r.domain}><text x="8" y={y-2} className="ri-domain-label">{r.label}</text>{valid&&<text x="8" y={y+16} className="ri-domain-detail">{fmt(r.baselineDaily,2)} → {fmt(r.currentDaily,2)}건/일</text>}{valid?<><rect x={Math.min(zero,px)} y={y-12} width={Math.max(2,Math.abs(px-zero))} height="23" rx="4" fill={color}/><text x={r.change>0?px+12:px-12} y={y+5} textAnchor={r.change>0?'start':'end'} fill={color} className="ri-change-value">{r.change>0?'+':''}{fmt(r.change)}%</text><title>{r.label}: {fmt(r.change)}%, 과거 {fmt(r.baselineDaily,2)}건/일 → 현재 {fmt(r.currentDaily,2)}건/일</title></>:<text x={zero+15} y={y+5} className="ri-axis">비교 자료 부족</text>}</g>;})}
 </svg>;
}
export default function RegionAnalysis({city,district,onSelect,age,onAgeChange,onServices}){
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
   <section className="ri-topic" aria-labelledby="ri-map-title"><header className="ri-topic-header"><div><h2 id="ri-map-title">우리 동은 어떤 지역일까?</h2></div><span>{city} {regions.length}개 동 · {periodLabel(period)}</span></header>
    <div className="ri-cluster-legend">{groups.map(g=><article key={g.id}><i style={{background:CLUSTER_COLORS[g.id]}}/><div><strong>{g.items[0].type}</strong></div></article>)}</div>
    <div className="ri-geography"><article className="ri-map-card"><header><strong>지역을 선택해 보세요</strong><label>행정동<select aria-label="지역 유형 지도에서 행정동 선택" value={selected?.name||''} onChange={e=>onSelect(e.target.value)}>{regions.map(r=><option key={r.code}>{r.name}</option>)}</select></label></header><Suspense fallback={<p role="status">지도를 준비하고 있습니다…</p>}><ClusterMap regions={regions} selected={selected?.name} onSelect={onSelect}/></Suspense><p className="ri-note">지역 유형은 사회적 고립 위험의 순위가 아닙니다.</p></article>
    <article className="ri-selected" aria-label="선택한 지역 유형"><h3>선택한 지역</h3><h2>{selected?.name}</h2><span>{periodLabel(period)}</span><strong className="ri-type-badge" style={{background:CLUSTER_COLORS[selected?.cluster]+'25'}}><i style={{background:CLUSTER_COLORS[selected?.cluster]}}/>{selected?.type}</strong><p>활동 규모와 가구·인구 구성이 비슷한 동을 함께 묶었습니다.</p><h3>같은 유형의 지역</h3><div className="ri-peers">{regions.filter(r=>r.cluster===selected?.cluster&&r.code!==selected?.code).map(r=><button key={r.code} onClick={()=>onSelect(r.name)}>{r.name}</button>)}</div><p className="ri-note">동 전체의 특성을 요약한 결과입니다.</p></article></div>
   </section>
   <section className="ri-topic" aria-labelledby="ri-consumption-title"><header className="ri-topic-header"><div><h2 id="ri-consumption-title">소비는 어떻게 달라졌을까?</h2><p><b>{selected?.name} · {consumerAge} 고객</b>　일평균 결제건수 · 과거 같은 분기 평균 대비</p></div><div className="ri-consumption-filters"><span className="ri-selection-chip">지도에서 선택한 동 · {selected?.name}</span><div className="ri-age-tabs ri-consumer-ages" role="group" aria-label="소비 고객 연령 선택">{REGION_AGES.map(a=><button key={a} aria-pressed={consumerAge===a} onClick={()=>onAgeChange(a)}>{a}</button>)}</div><label><select aria-label="소비 기준분기" value={quarter} onChange={e=>setQuarter(e.target.value)}>{quarters.map(p=><option key={p} value={p}>{periodLabel(p)}</option>)}</select></label></div></header><div className="ri-consumption-key"><span>● 감소</span><span>● 증가</span><small>기준: {baseline.length?`${baseline[0].slice(0,4)}~${baseline.at(-1).slice(0,4)}년 ${baseline[0].slice(-1)}분기 평균`:'비교 자료 부족'} · 공통 관측 업종</small></div><ConsumptionChart rows={consumption} label={`${selected?.name} ${consumerAge} ${quarter}`}/><p className="ri-note">서울 상권분석 · 동별 5개 소비영역 · 가맹점 위치 기준으로, 해당 동 주민만의 소비를 뜻하지 않습니다.</p></section>
   <section className="ri-topic" aria-labelledby="ri-survey-title"><header className="ri-topic-header"><div><h2 id="ri-survey-title">강남구 주민들의 사회적 연결 마음</h2><p>{city} {surveyAge}의 관계망과 외로움</p></div><div className="ri-survey-controls"><span>{surveyYear}년 서울서베이</span><div className="ri-age-tabs" aria-label="서울서베이 연령대 선택">{REGION_AGES.map(a=><button key={a} aria-pressed={surveyAge===a} onClick={()=>setSurveyAge(a)}>{a}</button>)}</div></div></header>
    <div className="ri-survey-grid">{survey.map(r=><article key={r.metric}><h3>{r.label}</h3><strong>{Number.isFinite(r.gangnam)?`${fmt(r.gangnam*100)}%`:'자료 없음'}</strong>{[['gangnam',city],['seoul','서울 전체']].map(([key,name])=><div className={`ri-survey-bar ${key}`} key={key}><span>{name}</span><div><i style={{width:Number.isFinite(r[key])?`${r[key]*100/surveyMax*100}%`:'0%'}}/></div><b>{Number.isFinite(r[key])?`${fmt(r[key]*100)}%`:'자료 없음'}</b></div>)}</article>)}</div><p className="ri-note"><span className="ri-blue">● {city} {surveyAge}</span>　● 서울 전체 {surveyAge}　 · 비율(%) · 세 그래프 동일 눈금 0–{surveyMax}%</p><p className="ri-note">구·연령별 연간 조사값으로, 선택한 동의 조사 결과나 고립률을 뜻하지 않습니다.</p>
   </section>
   <section className="ri-topic ri-next-step"><div><h2>이 지역에 어떤 지원사업을 검토할까요?</h2><p>{city} {selected?.name} · {consumerAge}의 분석을 바탕으로 사업 후보를 확인합니다.</p></div><button className="primary" onClick={onServices}>사업 매칭 검토로 →</button></section>
  </>}
 </div>;
}
