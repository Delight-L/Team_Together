import DataQuality from './DataQuality.jsx';
import {orderedCases} from './caseOrder.mjs';
import DetectionCaseSelector from './DetectionCaseSelector';
import DetectionEvidence, { SignalBadges, signalState, signalExplanation } from './DetectionEvidence';
import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, query } from './api';
import { Icon } from './components';
import { useDraft } from './useDraft';
import { draftKey } from './draftStore.mjs';
import { groupKey, groupLabel, openGroup, restoreWorkspace, availableWorkspace, pickInitialGroup, CANDIDATE_ORDER } from './groupTabs.mjs';
import { summarizeRegions } from './Briefing';
import './group-dashboard.css';
import RegionContextCards from './RegionContextCards';
import { comparisonRows, signedBar } from './regionalPresentation.mjs';
import { ageStatus, detectionTabs, observationWindow } from './ageSignals.mjs';

const fmt = (n, digits = 1) => Number.isFinite(n) ? n.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '—';
const pct = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${fmt(n, 2)}%` : '비교 불가';
const emptyTabs = { tabs: [], active: '' };
const PAGE_SIZE = 9;

function LineChart({ points, label }) {
  const fillId = useId(), chartRef = useRef(null);
  const [size, setSize] = useState({width: 360, height: 150});
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const {width, height} = entry.contentRect;
      if (width > 0 && height > 0) setSize({width, height});
    });
    if (chartRef.current) observer.observe(chartRef.current);
    return () => observer.disconnect();
  }, []);
  const values = points.filter(p => Number.isFinite(p.mean));
  const max = Math.max(...values.map(p => p.mean), 1);
  const bottom = Math.max(35, size.height - 24), top = 10;
  const x = i => 30 + i * Math.max(1, size.width - 44) / Math.max(points.length - 1, 1);
  const y = v => bottom - v / max * (bottom - top);
  // Missing observations leave a gap; resizing changes coordinates, never circle or text proportions.
  const segments = []; let segment = [];
  points.forEach((p, i) => {
    if (Number.isFinite(p.mean)) segment.push([x(i), y(p.mean)]);
    else if (segment.length) { segments.push(segment); segment = []; }
  });
  if (segment.length) segments.push(segment);
  return <div ref={chartRef} className="gd-flow-chart">{values.length ? <svg className="gd-line" viewBox={`0 0 ${size.width} ${size.height}`} role="img" aria-label={label}>
    <defs><linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#60a5fa" stopOpacity=".24"/><stop offset="1" stopColor="#60a5fa" stopOpacity=".02"/></linearGradient></defs>
    {segments.map((seg, i) => <polygon key={i} points={[...seg, [seg.at(-1)[0], bottom], [seg[0][0], bottom]].map(p => p.join(',')).join(' ')} fill={`url(#${fillId})`}/>)}
    {[0, max / 2, max].map(v => <g key={v}><line x1="30" x2={size.width - 14} y1={y(v)} y2={y(v)} stroke="#e2e8f0"/><text x="24" y={y(v)+4} textAnchor="end">{fmt(v,0)}</text></g>)}
    {segments.map((seg,i) => <polyline key={i} points={seg.map(p => p.join(',')).join(' ')} fill="none" stroke="#2563eb" strokeWidth="2"/>)}
    {points.map((p,i) => <g key={p.month}>{Number.isFinite(p.mean) && <circle cx={x(i)} cy={y(p.mean)} r="3" fill="#2563eb"><title>{p.month}: {fmt(p.mean,2)}</title></circle>}{(points.length < 9 || i % 6 === 0 || i === points.length-1) && <text x={x(i)} y={size.height-5} textAnchor="middle">{Number(p.month.slice(5))}월</text>}</g>)}
  </svg> : <p className="gd-empty">표시할 자료가 없습니다.</p>}</div>;
}

function DetectionSummary({detection, group}) {
  const metrics = comparisonRows(detection?.payload, [['call_contacts','전화 연락'],['text_contacts','문자 연락'],['weekday_move_count','평일 이동'],['weekend_move_count','휴일 이동']]);
  const extent = Math.max(1,...metrics.flatMap(r => [r.local,r.common]).filter(Number.isFinite).map(Math.abs));
  return <section className="gd-detection-summary gd-summary-with-graphs" aria-label="통신·이동 탐지 요약">
    <div className="gd-metrics-heading"><div className="gd-heading-with-note"><h3>통신·이동 변화</h3><small className="gd-period-note">직전 기준월 대비</small></div><div className="gd-summary-graph-legend"><span><i/>{group.district} {group.age}</span><span><i/>{group.city} {group.age} 공통 변화</span></div></div>
    <div className="gd-summary-graphs">{metrics.map((r,i) => <article key={r.label} className={`gd-summary-metric ${detection[i<2?'communication_signal':'mobility_signal'] === true ? `is-detected signal-${signalState(detection.payload?.[(i<2?'communication':'mobility')+'_absolute_signal'],detection.payload?.[(i<2?'communication':'mobility')+'_local_signal'])}` : ''}`}><header><h4><Icon name={i<2?'chat':'chart'} size={22}/>{r.label}</h4></header><div className="gd-metric-value"><strong>{pct(r.local)}</strong>{Number.isFinite(r.local) && <span>{r.local<0?'감소':r.local>0?'증가':'변화 없음'}</span>}</div><div className="gd-summary-bars" role="img" aria-label={`${r.label}: ${group.district} ${pct(r.local)}, ${group.city} 같은 연령 공통 변화 ${pct(r.common)}`}>
      {['local','common'].map(key => <div key={key} className={`gd-summary-bar ${key}`}><span>{key === 'local' ? group.district : group.city}</span><div className="gd-summary-track"><i style={signedBar(r[key],extent)}/></div><small>{pct(r[key])}</small></div>)}
    </div></article>)}</div>
  </section>;
}

function DetectionHeading({group, detection, onEvidence, caseOptions, onCaseChange}) {
  const p=detection?.payload || {};
  const domains=[['communication','전화·문자 연락','chat'],['mobility','평일·휴일 이동','chart']].filter(([key])=>detection?.[key+'_signal']);
  return <header className="gd-case-heading gd-unified-heading"><div className="gd-case-title"><h2>{groupLabel(group)}</h2>{domains.map(([key,label,icon])=><span key={key} className={`gd-domain-chip signal-${signalState(p[key+'_absolute_signal'],p[key+'_local_signal'])}`}><Icon name={icon} size={20}/>{label} 감소 탐지</span>)}<div className="gd-case-actions">{caseOptions && <DetectionCaseSelector items={caseOptions} selected={group} onSelect={onCaseChange}/>}<button className="text-button gd-heading-evidence" onClick={onEvidence}>탐지 근거 보기 →</button></div></div><div className="gd-path-explanation">{domains.map(([key])=><span className="gd-domain-explanation" key={key}>{domains.length>1&&<b>{key==='communication'?'통신':'이동'}</b>}<SignalBadges absolute={p[key+'_absolute_signal']} local={p[key+'_local_signal']}/></span>)}{domains.length===1&&<p>{signalExplanation(p[domains[0][0]+'_absolute_signal'], p[domains[0][0]+'_local_signal'], group.city)}</p>}</div></header>;
}

// 조사 파일 카드가 글자 겹침 없이 들어가는 최소 폭입니다. 높이는 실제 카드 내용과 여백으로 잽니다.
const CARD_MIN_WIDTH = 260, CARD_MIN_HEIGHT = 105;

function cardHeight(list) {
  const card = list.firstElementChild, content = card?.querySelector('span');
  if (!card || !content) return CARD_MIN_HEIGHT;
  const style = getComputedStyle(card);
  const height = content.offsetHeight + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
  return Math.max(CARD_MIN_HEIGHT, Math.ceil(height));
}

// 목록 영역의 실제 크기로 칸·줄 수를 정합니다. 화면 폭이 아니라 영역 크기를 보므로
// 챗봇 패널·메뉴 때문에 목록만 좁아져도 칸 수를 줄이고, 한 페이지 개수를 맞춰 스크롤 없이 보여 줍니다.
function useCardGrid(list) {
  const [grid, setGrid] = useState({ cols: 3, rows: 3 });
  useEffect(() => {
    if (!list || typeof ResizeObserver === 'undefined') return;
    const measure = () => {
      if (!list.clientWidth || !list.clientHeight) return; // 숨겨진 탭에서는 크기를 재지 않습니다.
      const style = getComputedStyle(list);
      const columnGap = parseFloat(style.columnGap) || 0, rowGap = parseFloat(style.rowGap) || 0;
      const cols = Math.max(1, Math.min(3, Math.floor((list.clientWidth + columnGap) / (CARD_MIN_WIDTH + columnGap))));
      const fits = Math.max(1, Math.floor((list.clientHeight + rowGap) / (cardHeight(list) + rowGap)));
      const rows = Math.min(fits, Math.ceil(PAGE_SIZE / cols));
      setGrid(old => old.cols === cols && old.rows === rows ? old : { cols, rows });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [list]);
  return grid;
}

function Directory({ catalog, loading, error, retry, city, month, onOpen, state, statusOf, detectionMode = false }) {
  const [page,setPage]=useState(0);
  const groups=orderedCases(catalog?.groups || []);
  useEffect(()=>setPage(0),[month,city]);
  const [listElement,setListElement]=useState(null);
  const {cols,rows}=useCardGrid(listElement);
  const pageSize=cols*rows,pages=Math.max(1,Math.ceil(groups.length/pageSize)),current=Math.min(page,pages-1);
  return <div className="gd-directory gd-clean-directory"><header><h2>조사 파일</h2><span>{month}</span></header>
    {loading?<p role="status">그룹 자료를 읽고 있습니다…</p>:error?<div role="alert" className="gd-error">{error}<button onClick={retry}>다시 연결</button></div>:<div ref={setListElement} className="gd-file-list" style={{'--gd-file-cols':cols,'--gd-file-rows':rows}}>{groups.slice(current*pageSize,current*pageSize+pageSize).map(g=>{
      const group={city,code:g.code,district:g.district,age:g.age,sex:g.sex,month:g.month},id=groupKey(group),opened=state.tabs.some(t=>groupKey(t)===id);
      return <button key={id} className={state.active===id?'selected':''} title={groupLabel(g)} onClick={()=>onOpen(group)}><Icon name="report" size={21}/><span><strong>{groupLabel(g)}</strong><small>{g.month}{!detectionMode&&` · 구성비 ${fmt(g.share)}%`}</small></span>{CANDIDATE_ORDER.includes(statusOf(g)?.status)&&<i className="gd-candidate">{statusOf(g).status}</i>}{opened?<em>{state.active===id?'현재 탭':'열림'}</em>:<span aria-hidden="true">›</span>}</button>;
    })}</div>}
    <footer><span>{groups.length}개 그룹 · {current+1}/{pages}</span><button aria-label="이전 그룹 목록" disabled={current===0} onClick={()=>setPage(current-1)}>‹</button><button aria-label="다음 그룹 목록" disabled={current+1>=pages} onClick={()=>setPage(current+1)}>›</button></footer>
  </div>;
}

function GroupCase({ group, shown, summaryStep, onEvidence, onSummary, onServices, analysis, caseOptions, onCaseChange, onEvidenceCaseChange }) {
  const summaryPage = summaryStep === 3 ? 3 : 0;
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    api('/groups/detail?' + query(group)).then(d => { if (live) setData(d); }).catch(e => live && setError(e.message));
    return () => { live = false; };
  }, [retry]);
  const row = data?.current;
  const detection = data?.regional?.detection;
  const structure = data?.regional?.structure;
  const evidenceRows = (analysis?.assessment || []).filter(r => r['행정동코드'] === group.code && r.age_label === group.age && r['기준연월'] === group.month);
  return <><section hidden={!shown} className="gd-case" role="tabpanel" id={'panel-' + groupKey(group)} aria-label={groupLabel(group)}>
    {error ? <div role="alert" className="gd-error">{error}<button onClick={() => { setError(''); setRetry(r => r + 1); }}>다시 연결</button></div> : !row ? <p role="status">집단별 근거를 읽고 있습니다…</p> : <>
      <div className="gd-summary" data-summary-page={summaryPage}><div className="gd-overview gd-unified-overview"><DetectionHeading group={group} detection={detection} onEvidence={onEvidence} caseOptions={shown ? caseOptions : undefined} onCaseChange={onCaseChange}/>
      {detection && <DetectionSummary detection={detection} group={group}/>}
      <section className="gd-unified-flow" aria-label="유동량 참고"><div className="gd-heading-with-note"><h3 className="gd-flow-reference-label">{group.district} {group.age} 유동량 변화</h3><small className="gd-period-note">직전 기준월 대비</small></div>
      <h3 className="gd-narrative">{Number.isFinite(row.change_pct) ? `${fmt(Math.abs(row.change_pct), 2)}% ${row.change_pct > 0 ? '증가' : row.change_pct < 0 ? '감소' : '변화 없음'}` : '비교 자료 부족'}</h3>
      <article className="gd-mini-trend"><LineChart points={data.series} label={`${groupLabel(group)} 월별 구역별 평균 유동량`}/></article>
      <article className="gd-mini-share"><h4>{group.district} 전체 유동량 중 {group.age} 비율</h4><strong>{fmt(row.share, 2)}<small>%</small></strong><div className="gd-share-track"><i style={{width: `${Number.isFinite(row.share) ? Math.max(0, Math.min(100, row.share)) : 0}%`}}/></div></article></section><button className="primary gd-support-link gd-standalone-support" onClick={onServices}><span>지원사업 후보 확인</span><Icon name="arrow" size={18}/></button><div className="gd-inline-background"><RegionContextCards structure={structure} survey={data.regional?.survey} group={group} /></div></div>
      {evidenceRows.length > 0 && <div className="gd-signal-card"><DetectionEvidence rows={evidenceRows} group={group} detection={detection} onBack={onSummary} caseOptions={shown ? caseOptions : undefined} onCaseChange={onEvidenceCaseChange}/></div>}
      </div>

    </>}
  </section></>;
}

export default function GroupDashboard({ city, month: preferredMonth, user, analysis, onActiveGroup, onMonthChange, focusCase, onServices }) {
  const [catalog, setCatalog] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  // v2: 후보 우선 규칙(처음 방문 시 1순위 후보 동의 그룹)이 생기기 전에 저장된 탭 기록은 한 번 새로 시작합니다.
  const [stored, setStored, , workspaceStorageFailed] = useDraft(draftKey(user, { city }, 'group-workspace-v2'), emptyTabs);
  const state = restoreWorkspace(stored, city);
  const cases = city === '강남구' && analysis?.analysisScope === 'dong_age' ? analysis.ageDetections || [] : [];
  const analysisVersion = cases[0]?.model_version || '';
  const migrate = Boolean(analysisVersion && state.analysisVersion !== analysisVersion);
  const signalMonths = [...new Set(cases.filter(r => r.any_signal).map(r => r.month))].sort();
  const [appliedFocus,setAppliedFocus]=useState(null);
  const focusPending=focusCase?.city===city && focusCase.requestId !== appliedFocus;
  const month = focusPending ? focusCase.month : migrate ? signalMonths.at(-1) || preferredMonth : state.month || preferredMonth;
  useEffect(() => { if (month) onMonthChange?.(month); }, [month, onMonthChange]);
  const setState = update => setStored(old => update(restoreWorkspace(old, city)));
  const tabRefs = useRef({});
  // 종합 현황에서 고른 기준월로 동별 판정을 다시 계산해, 후보 동의 그룹을 먼저 보여 줍니다.
  const statusByDistrict = useMemo(() => {
    if (!analysis) return {};
    const regions = summarizeRegions(analysis.assessment, analysis.geometry, city, month, analysis.months);
    return Object.fromEntries(regions.map(r => [r.name, { status: r.status, count: r.count }]));
  }, [analysis, city, month]);
  const statusOf = g => analysis?.analysisScope === 'dong_age'
    ? ageStatus(analysis.ageDetections || [], { ...g, month: g.month || month })
    : statusByDistrict[g.district] || (g.code === '1123074' ? statusByDistrict['일원2동'] : undefined);
  // 탐지 현황과 조사 파일은 고정 탭입니다. 그룹 탭을 열거나 고르면 브리핑으로 전환됩니다.
  const [workspaceTab, setWorkspaceTab] = useState('group');
  const [summaryStep, setSummaryStep] = useState(1);
  useEffect(() => {
    if (!focusCase || focusCase.city !== city) return;
    setState(old => {
      const next={...old,month:focusCase.month,initialized:true,analysisVersion};
      return focusCase.code && focusCase.age && focusCase.district ? openGroup(next,focusCase) : next;
    });
    setAppliedFocus(focusCase.requestId);
    setWorkspaceTab('group');setSummaryStep(1);
  }, [focusCase?.requestId]);
  const setShowFiles = value => { setWorkspaceTab(value ? 'files' : 'group'); if (!value) setSummaryStep(1); };
  useEffect(() => {
    let live = true; setLoading(true); setError(''); setCatalog(null);
    api('/groups?' + query({ city, month })).then(result => {
      if (!live) return;
      if (!Array.isArray(result.groups)) throw new Error('집단별 자료 응답 형식을 확인하세요.');
      setCatalog(cases.length ? {...result,groups:detectionTabs(cases,city,month)} : result);
      setState(old => {
        const valid = availableWorkspace(migrate ? { ...old, month, initialized:false, analysisVersion } : old, result, month);
        if (cases.length) {
          const tabs = detectionTabs(cases, city, month);
          if (!tabs.length) {
            // Keep the basic screen and carry the selected group into the new month.
            // These are actual monthly observations, never added to the detection list.
            const previous=old.tabs.find(g=>groupKey(g)===old.active);
            const observations=orderedCases(cases.filter(r=>r.month===month));
            const row=observations.find(r=>r.code===previous?.code && r.age===previous?.age) || observations[0];
            const group=row ? {city,code:row.code,district:row.district,age:row.age,sex:'통합',month} : null;
            return {...valid,tabs:group?[group]:[],initialized:true,active:group?groupKey(group):''};
          }
          return {...valid, tabs, initialized:true, active:tabs.some(g => groupKey(g) === valid.active) ? valid.active : groupKey(tabs[0])};
        }
        if (valid.initialized || !result.groups.length || valid.month !== month) return valid;
        const first = pickInitialGroup(result.groups, statusOf);
        return openGroup({ ...valid, initialized: true }, { city, code: first.code, district: first.district, age: first.age, sex: first.sex, month });
      });
    }).catch(e => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [city, month, retry, analysisVersion]);
  const open = (group, keepEvidence = false) => { setState(s => openGroup({ ...s, initialized: true }, group)); setShowFiles(false); if (keepEvidence) setSummaryStep(3); };
  const active = state.tabs.find(g => groupKey(g) === state.active && g.month === month);
  const qualityShown = workspaceTab === 'quality';
  const filesShown = workspaceTab === 'files';
  const activeKey = active ? groupKey(active) : '';
  useEffect(() => { onActiveGroup?.(active || null); }, [activeKey, onActiveGroup]);
  // 파일 탭의 키보드 탐색 순서입니다.
  const changeTab = (event,index) => {
    const ids=['overview','files','quality'];let next=index;
    if(event.key==='ArrowRight') next=(index+1)%3;
    else if(event.key==='ArrowLeft') next=(index+2)%3;
    else if(event.key==='Home') next=0;
    else if(event.key==='End') next=2;
    else return;
    event.preventDefault();setWorkspaceTab(['group','files','quality'][next]);setSummaryStep(1);
    requestAnimationFrame(()=>tabRefs.current[ids[next]]?.focus());
  };
  return <div className="gd-root">
    {document.getElementById('group-period-slot') && createPortal(<label>기준월<select aria-label="집단 자료 기준월" value={catalog?.months.includes(month) ? month : ''} disabled={loading || !catalog?.months.length} onChange={e => { const selected = e.target.value; setState(s => ({ ...s, month: selected, initialized:false })); }}>
      {!catalog?.months.includes(month) && <option value="">{loading ? '기간 확인 중…' : '제공 자료 없음'}</option>}{catalog?.months.slice().reverse().map(m => <option key={m} value={m}>{m}{cases.length ? ` · 탐지 ${cases.filter(r => r.month === m && r.any_signal).length}건` : ''}</option>)}
    </select>{cases.length > 0 && <small className="gd-observation-window">통신·이동 관측 {observationWindow(month)}</small>}</label>, document.getElementById('group-period-slot'))}
    {workspaceStorageFailed && <p className="gd-scope-note" role="status">탭 임시 저장에 실패했습니다. 새로고침 시 열린 탭을 복원하지 못할 수 있습니다.</p>}
    {active && active.month !== month && <p className="gd-scope-note">조사 파일 기준월은 {month}, 현재 열린 브리핑은 <b>{active.month} · {groupLabel(active)}</b>입니다.</p>}
    <div className="gd-workspace"><ol className="gd-process" aria-label="브리핑 읽는 순서">{[['연락·이동 변화 확인', '탐지된 변화와 감소 폭을 살펴봅니다.'], ['가구·관계망 함께 보기', '가구 구성과 사회적 연결을 함께 봅니다.'], ['필요한 지원 검토', '확인한 필요에 맞는 지원을 검토합니다.']].map(([title, text], i) => <li key={title}><div className="gd-step-guide"><b>{i + 1}</b><span className="gd-step-icon"><Icon name={['discover', 'neighborhood', 'support'][i]} size={26}/></span><div><strong>{title}</strong><span>{text}</span></div></div></li>)}</ol><div className="gd-tabbar"><div className="gd-tabs-window"><div className="gd-tabs-track" role="tablist" aria-label="사례 검토 파일">
        {[['overview','탐지 현황','clipboard'],['files','조사 파일','report'],['quality','자료 확인','clipboard']].map(([id,label,icon],index)=>{const selected=id==='quality'?qualityShown:id==='files'?filesShown:!filesShown&&!qualityShown;return <div key={id} className={`gd-tab ${selected?'active':''}`}><button role="tab" id={'tab-'+id} aria-selected={selected} aria-controls={id==='quality'?'panel-quality':id==='files'?'panel-files':active?'panel-'+groupKey(active):'panel-evidence-empty'} tabIndex={selected?0:-1} ref={el=>{tabRefs.current[id]=el;}} onKeyDown={e=>changeTab(e,index)} onClick={()=>{setWorkspaceTab(['group','files','quality'][index]);setSummaryStep(1);}}><Icon name={icon} size={22}/><span><b>{label}</b></span></button></div>;})}
      </div></div></div>
      <section className="gd-case gd-files-panel" role="tabpanel" id="panel-files" aria-labelledby="tab-files" hidden={!filesShown}><Directory catalog={catalog} city={city} month={month} loading={loading} error={error} retry={() => setRetry(n => n + 1)} onOpen={open} state={state} statusOf={statusOf} detectionMode={cases.length > 0} /></section>
      <section className="gd-case gd-quality-panel" role="tabpanel" id="panel-quality" aria-labelledby="tab-quality" hidden={!qualityShown}><DataQuality analysis={analysis} city={city}/></section>
      {state.tabs.map(g => <GroupCase key={groupKey(g)} group={g} shown={!filesShown && !qualityShown && groupKey(g) === state.active} onServices={() => onServices(g)} caseOptions={cases.length ? detectionTabs(cases,city,month) : state.tabs.filter(item => item.month === month)} onCaseChange={open} onEvidenceCaseChange={group => open(group, true)} onEvidence={() => setSummaryStep(3)} onSummary={() => setSummaryStep(1)} summaryStep={summaryStep} analysis={analysis} />)}
<section id="panel-evidence-empty" role="tabpanel" aria-labelledby="tab-overview" className="gd-case" hidden={filesShown || qualityShown || !!active}/>
    </div>
  </div>;
}
