import React,{useEffect,useMemo,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {api,query} from './api';
import {Icon} from './components';
import {MissionMap} from './MissionMap';
import {DOMAINS,TRACKING_AGES,pathState,eventsFor,trackingMonthOptions,eventsInMonth,preferredMonthlyEvent,trackingSeries,latestObservation,stateLabel} from './activityTracking.mjs';
import './regional-followup.css';
import {DETECTION_METHODS,detectionMapRegions} from './detectionMap.mjs';

const fmt=(v,d=2)=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:d}):'자료 없음';
const monthName=m=>`${Number(m.slice(5))}월`;

function FlowChart({series,domain,signalMonth,referenceMonth}) {
 const values=series.flatMap(p=>domain.metrics.map(([k])=>p.values[k])).filter(Number.isFinite);
 if(!values.length)return <div className="rf-chart-empty">활동량 비교 자료가 없습니다.</div>;
 const low=Math.min(100,...values),high=Math.max(100,...values),span=Math.max(10,high-low);
 const step=[2,5,10,20,25,50,100].find(n=>n>=span/4)||Math.ceil(span/400)*100;
 const min=Math.floor((low-step*.1)/step)*step,max=Math.ceil((high+step*.1)/step)*step;
 const ticks=Array.from({length:Math.round((max-min)/step)+1},(_,i)=>min+i*step);
 const x=i=>i*90/Math.max(1,series.length-1),y=v=>8+(max-v)/(max-min)*84;
 const at=series.findIndex(p=>p.month===signalMonth);
 const ends=domain.metrics.map(([k])=>{const v=series.at(-1)?.values[k];return Number.isFinite(v)?y(v):null;});
 if(ends.every(v=>v!==null)&&Math.abs(ends[0]-ends[1])<15){const mid=(ends[0]+ends[1])/2;const sign=ends[0]<=ends[1]?1:-1;ends[0]=mid-sign*7.5;ends[1]=mid+sign*7.5;}
 return <div className="rf-chart" role="img" aria-label={`${domain.label} 지표 흐름, ${referenceMonth} 활동량 100 기준`}><div className="rf-chart-plot">
  {at>=0&&<div className="rf-detection-band" style={{left:`${x(at)}%`}}><span>탐지월</span></div>}
  {ticks.map(v=><React.Fragment key={v}><span className="rf-y-tick" style={{top:`${y(v)}%`}}>{v}</span><i className={`rf-gridline ${v===100?'reference':''}`} style={{top:`${y(v)}%`}}/></React.Fragment>)}
  <span className="rf-reference-label" style={{top:`${y(100)}%`}}>탐지 전 수준 100</span>
  <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">{domain.metrics.flatMap(([key,,color],j)=>{
   const segments=[];let line=[];series.forEach((p,i)=>{const v=p.values[key];if(Number.isFinite(v))line.push([x(i),y(v)]);else if(line.length){segments.push(line);line=[];}});if(line.length)segments.push(line);
   return segments.map((s,i)=><polyline key={key+i} points={s.map(p=>p.join(',')).join(' ')} fill="none" stroke={color} strokeWidth="2.5" strokeDasharray={j?'7 5':undefined} vectorEffect="non-scaling-stroke"/>);
  })}</svg>
  {domain.metrics.map(([key,label,color],j)=><React.Fragment key={key}>{series.map((p,i)=>Number.isFinite(p.values[key])&&<i key={p.month} className={`rf-dot ${j?'square':''}`} style={{left:`${x(i)}%`,top:`${y(p.values[key])}%`,background:color}} title={`${p.month} ${label}: ${fmt(p.values[key])}`}/>)}{Number.isFinite(series.at(-1)?.values[key])&&<b className="rf-end-label" style={{left:'90%',top:`${ends[j]}%`,color}}>{label} {fmt(series.at(-1).values[key])}</b>}</React.Fragment>)}
  {series.map((p,i)=><span className="rf-x-tick" key={p.month} style={{left:`${x(i)}%`}}>{monthName(p.month)}</span>)}
 </div></div>;
}

function DomainCard({domain,event,endMonth}) {
 const series=trackingSeries(event,endMonth),latest=latestObservation(event,endMonth);
 const signal=event.signals[domain.key],state=pathState(signal),ds=latest?.domains?.[domain.key];
 return <section className="rf-domain-card" data-domain={domain.key}>
  <header className="rf-domain-header"><div><h3>{domain.label} 지표 흐름 추적하기</h3><span className={`rf-detection-badge ${state}`} title={state==='absolute'?'자체 과거 비교에서 탐지':state==='local'?'공통 변화 제거 후 탐지':state==='both'?'두 비교 모두에서 탐지':'탐지월에 해당 영역의 신호 미성립'}>탐지월: {domain.label} {state==='none'?'미탐지':'탐지'}</span></div><div className="rf-metric-legend">{domain.metrics.map(([key,label,color],j)=><span key={key}><i className={j?'square':''} style={{'--series-color':color}}/>{label}</span>)}</div></header>
  <p className="rf-reference-note">탐지 직전 기준월({event.referenceMonth}) = 100</p>
  <FlowChart series={series} domain={domain} signalMonth={event.signalMonth} referenceMonth={event.referenceMonth}/>
  <div className="rf-status-grid">{[['raw','실제 활동량'],['seasonal','계절성 고려'],['local','강남구 흐름 고려']].map(([key,label])=><article key={key}><Icon name={key==='raw'?'chart':key==='seasonal'?'calendar':'neighborhood'} size={18}/><div><h4>{label}</h4><span className={ds?.[key+'_state']==='recovered_to_reference'?'rf-reached':''}>{stateLabel(ds?.[key+'_state'])}</span></div></article>)}</div>
 </section>;
}

export default function RegionalFollowup({city,month,geometry,assessment=[],selected,onSelect,summarize,age,onAgeChange,onMonthChange}) {
 const [data,setData]=useState(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 const [selectedAge,setSelectedAge]=useState(TRACKING_AGES.includes(age)?age:'40대'),[signalMonth,setSignalMonth]=useState('');
 const initialized=useRef(''),selectionInitialized=useRef('');
 useEffect(()=>{let live=true;setData(null);setError('');api('/region-insights?'+query({city})).then(d=>{if(live)setData(d);}).catch(e=>live&&setError(e.message));return()=>{live=false;};},[city,retry]);
 const tracking=data?.activityTracking,months=tracking?.months||[],endMonth=month||months.at(-1)||'';
 const monthOptions=trackingMonthOptions(tracking,endMonth);
 const priorEvent=eventsFor(tracking,selected,selectedAge,endMonth).at(-1);
 const mapMonth=monthOptions.some(m=>m.month===signalMonth)?signalMonth:priorEvent?.signalMonth||monthOptions.filter(m=>m.count).at(-1)?.month||monthOptions.at(-1)?.month||endMonth;
 const monthlyEvents=eventsInMonth(tracking,mapMonth);
 const event=monthlyEvents.find(e=>e.district===selected&&e.age===selectedAge);
 useEffect(()=>{if(age!==selectedAge)onAgeChange?.(selectedAge);},[age,selectedAge,onAgeChange]);
 useEffect(()=>{if(!data||initialized.current===city)return;initialized.current=city;const latest=months.at(-1);if(latest&&latest!==month)onMonthChange?.(latest);},[data,city]);
 useEffect(()=>{
  if(!tracking||selectionInitialized.current===city)return;selectionInitialized.current=city;
  const available=tracking.events.filter(e=>e.signalMonth<=endMonth);
  const first=selected?preferredMonthlyEvent(available,selected,selectedAge):available.find(e=>e.district==='개포3동')||available[0];
  if(first){setSignalMonth(first.signalMonth);if(!selected)onSelect(first.district);}
 },[tracking,selected,onSelect,city,endMonth]);
 useEffect(()=>{
  const available=monthlyEvents.filter(e=>e.district===selected);
  if(available.length&&!available.some(e=>e.age===selectedAge)){const preferred=available.find(e=>e.age===age)||available[0];setSelectedAge(preferred.age);onAgeChange?.(preferred.age);}
 },[tracking,selected,mapMonth,endMonth]);
 const selectSignalMonth=value=>{
  setSignalMonth(value);
  const first=preferredMonthlyEvent(eventsInMonth(tracking,value),selected,selectedAge);
  if(first){onSelect(first.district);setSelectedAge(first.age);onAgeChange?.(first.age);}
 };
 const mapRegions=useMemo(()=>detectionMapRegions(summarize(assessment,geometry,city,mapMonth,months),tracking,mapMonth),[assessment,geometry,city,mapMonth,tracking]);
 const slot=document.getElementById('followup-period-slot');
 return <div className="rf-root">
  {slot&&createPortal(<label>관찰 종료월<select aria-label="추적 관찰 종료월" value={endMonth} onChange={e=>onMonthChange?.(e.target.value)} disabled={!months.length}>{[...months].reverse().map(m=><option key={m}>{m}</option>)}</select></label>,slot)}
  <section className="card rf-map-card directory-map"><header><h2>어느 지역을 살펴볼까요?</h2><span className="pill">탐지월 {mapMonth}</span></header><div className="rf-map-legend" aria-label="지도 탐지 방식">{Object.entries(DETECTION_METHODS).map(([key,method])=><span key={key}><i style={{background:method.color}}/>{method.label}</span>)}</div><div className="directory-map-body"><MissionMap geometry={geometry} regions={mapRegions} selected={selected} onSelect={onSelect}/></div></section>
  <section className="rf-tracking"><header className="rf-tracking-header"><h2>탐지 이후 어떻게 달라졌을까?</h2><div className="rf-case-heading"><h3>{selected||'행정동을 선택해 주세요'} · {selectedAge}</h3>{event&&DOMAINS.filter(d=>pathState(event.signals[d.key])!=='none').map(d=><span key={d.key} className={`rf-case-chip ${pathState(event.signals[d.key])}`}><Icon name={d.key==='communication'?'chat':'chart'} size={16}/>{d.key==='communication'?'전화·문자 연락':'평일·휴일 이동'} 감소 탐지</span>)}</div><div className="rf-controls"><div className="rf-age-buttons" role="group" aria-label="추적 관찰 연령대">{TRACKING_AGES.map(a=><button key={a} aria-pressed={a===selectedAge} onClick={()=>{setSelectedAge(a);onAgeChange?.(a);}}>{a}</button>)}</div><label>탐지월<select aria-label="추적할 탐지월 선택" value={monthOptions.length?mapMonth:''} onChange={e=>selectSignalMonth(e.target.value)} disabled={!monthOptions.length}>{!monthOptions.length&&<option value="">제공 자료 없음</option>}{[...monthOptions].reverse().map(m=><option key={m.month} value={m.month}>{m.month} · 탐지 {m.count}건</option>)}</select></label></div></header>
   {error?<div className="rf-empty" role="alert">{error}<button onClick={()=>setRetry(v=>v+1)}>다시 연결</button></div>:!data?<div className="rf-empty" role="status">DB1 추적 자료를 읽고 있습니다…</div>:!tracking?.available?<div className="rf-empty">{city}의 추적 관찰 자료가 연결되지 않았습니다.</div>:!event?<div className="rf-empty">{monthlyEvents.length?`${mapMonth} ${selected||'선택한 지역'} · ${selectedAge}에는 탐지 이력이 없습니다.`:`${mapMonth}에는 탐지된 사례가 없습니다.`}<p>{monthlyEvents.length?'지도에서 다른 지역이나 연령대를 선택해 주세요.':'다른 탐지월을 선택해 주세요.'}</p></div>:<div className="rf-domains">{DOMAINS.map(d=><DomainCard key={d.key} domain={d} event={event} endMonth={endMonth}/>)}</div>}
  </section>
 </div>;
}
