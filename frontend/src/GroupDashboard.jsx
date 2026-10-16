import DetectionEvidence, { SignalBadges, signalState } from './DetectionEvidence';
import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { fitDomain } from './chartScale.mjs';

import { createPortal } from 'react-dom';
import { api, query } from './api';
import { Icon } from './components';
import { useDraft } from './useDraft';
import { draftKey } from './draftStore.mjs';
import { groupKey, groupLabel, openGroup, closeGroup, restoreWorkspace, availableWorkspace, rankGroups, pickInitialGroup, CANDIDATE_ORDER } from './groupTabs.mjs';
import { summarizeRegions } from './Briefing';
import './group-dashboard.css';
import RegionContextCards from './RegionContextCards';
import { comparisonRows, signedBar } from './regionalPresentation.mjs';
import { tabPage, tabPageForSelected } from './tabPaging.mjs';
import { ageStatus, detectionTabs, observationWindow, detectionBadge } from './ageSignals.mjs';

const fmt = (n, digits = 1) => Number.isFinite(n) ? n.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '—';
const pct = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${fmt(n, 2)}%` : '비교 불가';
const emptyTabs = { tabs: [], active: '' };
const PAGE_SIZE = 12;

function PageButtons({ page, pages, onPage, label }) {
  return <div className="gd-page-buttons" aria-label={label}><button disabled={!page} onClick={() => onPage(page - 1)}>이전</button><span>{page + 1} / {pages}</span><button disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>다음</button></div>;
}

function EvidencePages({ children, requestedPage }) {
  const sections = React.Children.toArray(children);
  const [page, setPage] = useState(0);
  useEffect(() => { if (requestedPage) setPage(3); }, [requestedPage]);
  const active = Math.min(page, sections.length - 1);
  const label = section => React.Children.toArray(section.props.children)[0]?.props?.children;
  return <div className="gd-evidence-pages"><div className="gd-evidence-navigation"><label>확인할 근거<select aria-label="확인할 근거" value={active} onChange={e => setPage(Number(e.target.value))}>{sections.map((section, index) => <option key={index} value={index}>{React.Children.toArray(label(section)).filter(child => typeof child === 'string').join('')}</option>)}</select></label><PageButtons page={active} pages={sections.length} onPage={setPage} label="근거 항목 이동"/></div><div className="gd-evidence-content">{sections[active]}</div></div>;
}

function PagedTable({ children }) {
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(() => window.innerHeight >= 850 ? Math.max(4, Math.min(10, Math.floor((window.innerHeight - 650) / 46))) : 4);
  useEffect(() => {
    const resize = () => setPageSize(window.innerHeight >= 850 ? Math.max(4, Math.min(10, Math.floor((window.innerHeight - 650) / 46))) : 4);
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  const parts = React.Children.toArray(children);
  const body = parts.find(part => part.type === 'tbody');
  const rows = React.Children.toArray(body?.props.children);
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const current = Math.min(page, pages - 1);
  return <><table>{parts.map((part,index) => part.type === 'tbody' ? React.cloneElement(part, {key:index}, rows.slice(current * pageSize, current * pageSize + pageSize)) : part)}</table>{pages > 1 && <PageButtons page={current} pages={pages} onPage={setPage} label="표 페이지"/>}</>;
}

function ServiceResults({ matches }) {
  const [page, setPage] = useState(0), [textPage, setTextPage] = useState(0);
  const current = Math.min(page, Math.max(0, matches.items.length - 1));
  const item = matches.items[current];
  if (!item) return <p>선택한 지원 목적에 관련된 사업이 없습니다. 검토 목적을 바꿔 다시 찾아보세요.</p>;
  const service = item.service;
  const text = [item.reason, '대상: ' + (service.target_text || '원문 확인 필요'), '선정 조건: ' + (service.eligibility_text || '기관 확인 필요'), '신청 방법: ' + (service.application_text || '기관 확인 필요'), item.qualification].join('\n\n');
  const pages = Math.max(1, Math.ceil(text.length / 400));
  const part = Math.min(textPage, pages - 1);
  return <article className="gd-service-result"><h3>{service.name}</h3><PageButtons page={current} pages={matches.items.length} onPage={value => {setPage(value);setTextPage(0);}} label="사업 이동"/><p style={{whiteSpace:'pre-wrap'}}>{text.slice(part * 400, part * 400 + 400)}</p>{pages > 1 && <PageButtons page={part} pages={pages} onPage={setTextPage} label="사업 상세 내용 이동"/>}{/^https?:\/\//i.test(service.source_url || '') && <a href={service.source_url} target="_blank" rel="noreferrer">공식 안내 확인 ↗</a>}</article>;
}

// 말풍선 글자 폭 어림값(한글은 넓게). 그린 뒤에는 실제 글자 폭으로 다시 맞춥니다.
const tipWidth = text => [...text].reduce((w, c) => w + (c.charCodeAt(0) > 0x1100 ? 14 : 8), 0);

// unit: 눈금 단위(예: '%'), lastColor: 이번 달 점을 강조할 색(없으면 강조하지 않음)
// detail(p, i): 마우스를 올린 달의 말풍선 둘째 줄(예: 전월 대비 변화). 없으면 값만 보여 줍니다.
function LineChart({ points, field = 'mean', label, unit = '', lastColor, detail }) {
  const fillId = useId();
  const [hover, setHover] = useState(null), [tipText, setTipText] = useState(0), tipRef = useRef(null);
  useLayoutEffect(() => {
    const texts = tipRef.current ? [...tipRef.current.querySelectorAll('text')] : [];
    const width = texts.length ? Math.ceil(Math.max(...texts.map(t => t.getComputedTextLength()))) : 0;
    setTipText(old => old === width ? old : width);
  }, [hover]);
  // 그래프 칸의 실제 높이에 맞춰 viewBox 높이를 정합니다. 칸이 커지면 글자는 그대로, 선만 세로로 넓어집니다.
  const svgRef = useRef(null), [height, setHeight] = useState(148);
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width: w, height: h } = entry.contentRect;
      if (w && h) setHeight(Math.max(120, Math.round(430 * h / w)));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  const values = points.filter(p => Number.isFinite(p[field]));
  if (!values.length) return <p className="gd-empty">표시할 자료가 없습니다.</p>;
  // 세로축은 자료 범위에 맞춰 변화가 잘 보이게 합니다(0부터 시작하지 않을 수 있음).
  const { low, high, ticks, fromZero } = fitDomain(values.map(p => p[field]));
  const digits = high - low < 6 ? 1 : 0;
  const lastIndex = points.findLastIndex(p => Number.isFinite(p[field]));
  // 단위(%)가 붙은 눈금은 글자가 길어 왼쪽 여백을 더 둡니다.
  const left = unit ? 48 : 32;
  const x = i => left + i * (402 - left) / Math.max(points.length - 1, 1);
  const base = height - 36;
  const y = v => base - (v - low) / (high - low) * (height - 52);
  // 월이 빠진 구간은 선으로 연결하지 않는다.
  const segments = []; let segment = [];
  points.forEach((p, i) => { if (Number.isFinite(p[field])) segment.push([x(i), y(p[field])]); else if (segment.length) { segments.push(segment); segment = []; } });
  if (segment.length) segments.push(segment);
  return <><svg ref={svgRef} className="gd-line" viewBox={`0 0 430 ${height}`} role="img" aria-label={label}>
    <defs><linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#60a5fa" stopOpacity=".24"/><stop offset="1" stopColor="#60a5fa" stopOpacity=".02"/></linearGradient></defs>
    {segments.map((seg, i) => <polygon key={i} points={[...seg, [seg.at(-1)[0], base], [seg[0][0], base]].map(p => p.join(",")).join(" ")} fill={`url(#${fillId})`} />)}
    {ticks.map((v, i) => <g key={i}><line x1={left} x2="405" y1={y(v)} y2={y(v)} stroke="#e2e8f0" /><text x={left - 6} y={y(v) + 4} textAnchor="end">{fmt(v, digits)}{unit}</text></g>)}
    {segments.map((s, i) => <polyline key={i} points={s.map(p => p.join(',')).join(' ')} fill="none" stroke="#2563eb" strokeWidth="3" />)}
    {points.map((p, i) => <g key={p.month || p.label}>{Number.isFinite(p[field]) && <circle cx={x(i)} cy={y(p[field])} r={hover === i ? 6 : lastColor && i === lastIndex ? 6 : 4} fill={lastColor && i === lastIndex ? lastColor : '#2563eb'} stroke={lastColor && i === lastIndex || hover === i ? '#fff' : undefined} strokeWidth="2" />}{(points.length < 9 || i % 6 === 0 || i === points.length - 1) && <text x={x(i)} y={height - 10} textAnchor="middle">{p.month ? Number(p.month.slice(5)) + '월' : p.label}</text>}</g>)}
    {hover !== null && Number.isFinite(points[hover]?.[field]) && (() => {
      const p = points[hover], lines = [`${p.month ? `${p.month.slice(0, 4)}년 ${Number(p.month.slice(5))}월` : p.label} · ${fmt(p[field], 2)}${unit}`, detail?.(p, hover)].filter(Boolean);
      const w = (tipText || Math.max(...lines.map(tipWidth))) + 18, h = lines.length * 18 + 10;
      const tx = Math.min(Math.max(x(hover) - w / 2, 2), 428 - w), py = y(p[field]);
      const ty = py - h - 10 >= 2 ? py - h - 10 : Math.min(py + 10, base - h);
      return <g className="gd-tip" pointerEvents="none" ref={tipRef}><line x1={x(hover)} x2={x(hover)} y1={8} y2={base} stroke="#94a3b8" strokeDasharray="3 3" /><rect x={tx} y={ty} width={w} height={h} rx="6" />{lines.map((t, k) => <text key={k} x={tx + 9} y={ty + 19 + k * 18} className={k ? 'sub' : ''}>{t}</text>)}</g>;
    })()}
    {points.map((p, i) => Number.isFinite(p[field]) && <rect key={'hit' + i} x={i ? (x(i - 1) + x(i)) / 2 : 0} width={(i ? (x(i) - x(i - 1)) / 2 : x(0)) + (i < points.length - 1 ? (x(i + 1) - x(i)) / 2 : 430 - x(i))} y="0" height={base} fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(h => h === i ? null : h)} onClick={() => setHover(i)} />)}
  </svg>{!fromZero && <small className="gd-axis-note">세로축은 {fmt(low, digits)}{unit}부터 시작합니다.</small>}</>;
}

function DetectionSummary({detection, group}) {
  const metrics = comparisonRows(detection?.payload, [['call_contacts','전화 연락'],['text_contacts','문자 연락'],['weekday_move_count','평일 이동'],['weekend_move_count','휴일 이동']]);
  const extent = Math.max(1,...metrics.flatMap(r => [r.local,r.common]).filter(Number.isFinite).map(Math.abs));
  return <section className="gd-detection-summary gd-summary-with-graphs" aria-label="통신·이동 탐지 요약">
    <div className="gd-metrics-heading"><h3>통신·이동 변화</h3><div className="gd-summary-graph-legend"><span><i/>{group.district} {group.age}</span><span><i/>{group.city} {group.age} 공통 변화</span></div></div>
    <div className="gd-summary-graphs">{metrics.map((r,i) => <article key={r.label} className={`gd-summary-metric ${detection[i<2?'communication_signal':'mobility_signal'] === true ? `is-detected signal-${signalState(detection.payload?.[(i<2?'communication':'mobility')+'_absolute_signal'],detection.payload?.[(i<2?'communication':'mobility')+'_local_signal'])}` : ''}`}><header><h4><Icon name={i<2?'chat':'chart'} size={22}/>{r.label}</h4></header><div className="gd-metric-value"><strong>{pct(r.local)}</strong>{Number.isFinite(r.local) && <span>{r.local<0?'감소':r.local>0?'증가':'변화 없음'}</span>}</div><div className="gd-summary-bars" role="img" aria-label={`${r.label}: ${group.district} ${pct(r.local)}, ${group.city} 같은 연령 공통 변화 ${pct(r.common)}`}>
      {['local','common'].map(key => <div key={key} className={`gd-summary-bar ${key}`}><span>{key === 'local' ? group.district : group.city}</span><div className="gd-summary-track"><i style={signedBar(r[key],extent)}/></div><small>{pct(r[key])}</small></div>)}
    </div></article>)}</div><div className="gd-detection-footer"><small>직전 기준월 대비 · 중앙선 0 · ← 감소 / 증가 →</small></div>
  </section>;
}

function DetectionHeading({group, detection, onEvidence}) {
  const p=detection?.payload || {};
  const domains=[['communication','전화·문자 연락','chat'],['mobility','평일·휴일 이동','chart']].filter(([key])=>detection?.[key+'_signal']);
  return <header className="gd-case-heading gd-unified-heading"><div className="gd-case-title"><h2>{groupLabel(group)}</h2>{domains.map(([key,label,icon])=><span key={key} className={`gd-domain-chip signal-${signalState(p[key+'_absolute_signal'],p[key+'_local_signal'])}`}><Icon name={icon} size={20}/>{label} 감소 탐지</span>)}<button className="text-button gd-heading-evidence" onClick={onEvidence}>탐지 근거 보기 →</button></div><div className="gd-path-explanation">{domains.map(([key,label])=><span className="gd-domain-explanation" key={key}>{domains.length>1&&<b>{key==='communication'?'통신':'이동'}</b>}<SignalBadges absolute={p[key+'_absolute_signal']} local={p[key+'_local_signal']}/></span>)}{domains.length===1&&<p>{p[domains[0][0]+'_absolute_signal']&&p[domains[0][0]+'_local_signal']?'평소보다 크게 감소했고, 공통 흐름을 고려해도 감소가 두드러집니다.':p[domains[0][0]+'_local_signal']?'강남구 같은 연령대의 공통 흐름을 고려해도 이 지역의 감소가 두드러집니다.':'이 지역·연령대의 감소가 평소보다 크게 나타났습니다.'}</p>}</div></header>;
}

// 조사 파일 카드가 글자 겹침 없이 들어가는 최소 폭입니다. 높이는 실제 카드 내용과 여백으로 잽니다.
const CARD_MIN_WIDTH = 260, CARD_MIN_HEIGHT = 56;

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
  const [grid, setGrid] = useState({ cols: 4, rows: 3 });
  useEffect(() => {
    if (!list || typeof ResizeObserver === 'undefined') return;
    const measure = () => {
      if (!list.clientWidth || !list.clientHeight) return; // 숨겨진 탭에서는 크기를 재지 않습니다.
      const style = getComputedStyle(list);
      const columnGap = parseFloat(style.columnGap) || 0, rowGap = parseFloat(style.rowGap) || 0;
      const cols = Math.max(1, Math.min(4, Math.floor((list.clientWidth + columnGap) / (CARD_MIN_WIDTH + columnGap))));
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

function Directory({ catalog, loading, error, retry, city, month, onOpen, state, searchRef, statusOf, detectionMode = false }) {
  const [search, setSearch] = useState(''), [age, setAge] = useState(''), [sex, setSex] = useState(''), [district, setDistrict] = useState(''), [page, setPage] = useState(0);
  const filtered = rankGroups((catalog?.groups || []).filter(g => (!district || g.code === district) && (!age || g.age === age) && (!sex || g.sex === sex) && `${g.district} ${g.age} ${g.sex}`.includes(search.trim())), statusOf);
  useEffect(() => setPage(0), [search, age, sex, district, month, city]);
  // 목록이 다시 그려져 요소가 바뀌어도 크기 감시를 새 요소에 연결하도록 state로 받습니다.
  const [listElement, setListElement] = useState(null);
  const { cols, rows } = useCardGrid(listElement);
  const pageSize = cols * rows;
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const current = Math.min(page, pages - 1);
  return <div className="gd-directory"><header><h2>조사 파일</h2><span>{month}</span></header><p>{detectionMode ? '선택한 월에 탐지된 행정동·연령대별 사례입니다.' : '살펴볼 읍·면·동·연령·성별 그룹을 고르면 옆에 브리핑 탭이 열립니다.'}</p>
    <input ref={searchRef} aria-label="행정동·연령 검색" placeholder="행정동·연령 검색" value={search} onChange={e => setSearch(e.target.value)} />
    <div className="gd-directory-filters"><label>읍·면·동<select aria-label="읍·면·동 필터" value={district} onChange={e => setDistrict(e.target.value)}><option value="">전체 읍·면·동</option>{catalog?.districts.map(d => <option key={d.code} value={d.code}>{d.name}</option>)}</select></label><select aria-label="연령 필터" value={age} onChange={e => setAge(e.target.value)}><option value="">모든 연령</option>{catalog?.ages.map(a => <option key={a}>{a}</option>)}</select>{!detectionMode && <select aria-label="성별 필터" value={sex} onChange={e => setSex(e.target.value)}><option value="">모든 성별</option>{catalog?.sexes.map(s => <option key={s}>{s}</option>)}</select>}</div>
    {loading ? <p role="status">그룹 자료를 읽고 있습니다…</p> : error ? <div role="alert" className="gd-error">{error}<button onClick={retry}>다시 연결</button></div> : !filtered.length ? <p className="gd-empty">선택 조건의 자료가 없습니다.{catalog?.months.length > 0 && <span> 제공 기간 {catalog.months[0]} ~ {catalog.months.at(-1)}</span>}</p> : <div className="gd-file-list" ref={setListElement} style={{ '--gd-cols': cols, '--gd-rows': rows }}>{filtered.slice(current * pageSize, current * pageSize + pageSize).map(g => {
      const group = { city, code: g.code, district: g.district, age: g.age, sex: g.sex, month: g.month }, id = groupKey(group);
      const opened = state.tabs.some(t => groupKey(t) === id);
      return <button key={id} className={state.active === id ? 'selected' : ''} title={groupLabel(g)} onClick={() => onOpen(group)}><Icon name="report" size={21} /><span><strong>{groupLabel(g)}</strong><small>{g.month}{!detectionMode && ` · 구성비 ${fmt(g.share)}%`}</small></span>{CANDIDATE_ORDER.includes(statusOf(g)?.status) && <i className="gd-candidate">{statusOf(g).status}</i>}{opened ? <em>{state.active === id ? '현재 탭' : '열림'}</em> : <span aria-hidden="true">›</span>}</button>;
    })}</div>}
    <footer><span>{filtered.length}개 그룹 · {current + 1}/{pages}</span><button aria-label="이전 그룹 목록" disabled={current === 0} onClick={() => setPage(current - 1)}>‹</button><button aria-label="다음 그룹 목록" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>›</button></footer>
    <p className="gd-source">{detectionMode ? 'DB1 · Analysis2 동·연령별 이상 탐지 결과' : '유동인구 연령·성별 집계'}</p>
  </div>;
}

function GroupCase({ group, active, shown, evidenceShown, summaryStep, user, onRegion, onEvidence, candidate, analysis, onSummary }) {
  const [summaryPage, setSummaryPage] = useState(0);
  useEffect(() => { setSummaryPage(0); }, [summaryStep]);
  const [reviewRequest, setReviewRequest] = useState(0);
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const [draft, setDraft, clearDraft, storageFailed] = useDraft(draftKey(user, group, `group-review:${group.code}:${group.age}:${group.sex}`), { note: '', need: '' });
  const [saved, setSaved] = useState(null), [status, setStatus] = useState(''), [saving, setSaving] = useState(false);
  const [matches, setMatches] = useState(null), [serviceError, setServiceError] = useState(''), [searching, setSearching] = useState(false);
  const servicesRef = useRef(null), moreRef = useRef(null), contentRef = useRef(null), serviceRequest = useRef(null);
  useEffect(() => {
    let live = true;
    api('/groups/detail?' + query(group)).then(d => { if (live) setData(d); }).catch(e => live && setError(e.message));
    api('/groups/review?' + query(group)).then(d => { if (live) setSaved(d); }).catch(e => live && setStatus(e.message));
    return () => { live = false; serviceRequest.current?.abort(); };
  }, [retry]);
  const currentDraft = { note: draft.note || saved?.note || '', need: draft.need || saved?.need || '' };
  // 사용자가 내용을 지운 경우도 저장할 수 있도록 편집 여부를 따로 보관한다.
  const note = draft.edited ? draft.note : currentDraft.note, need = draft.edited ? draft.need : currentDraft.need;
  const changeDraft = patch => setDraft({ note, need, ...patch, edited: true });
  const row = data?.current;
  const detection = data?.regional?.detection;
  const structure = data?.regional?.structure;
  const evidenceRows = (analysis?.assessment || []).filter(r => r['행정동코드'] === group.code && r.age_label === group.age && r['기준연월'] === group.month);
  const regionalRows = detection ? [['call_contacts', '전화 연락', 'communication_signal'], ['text_contacts', '문자 연락', 'communication_signal'], ['weekday_move_count', '평일 이동', 'mobility_signal'], ['weekend_move_count', '휴일 이동', 'mobility_signal']].map(([metric, label, signal]) => ({
    metric_label: label + (detection.payload[signal.replace('_signal', '_absolute_signal')] ? ' · 자체 이력' : detection.payload[signal.replace('_signal', '_local_signal')] ? ' · 공통 변화 조정' : ''),
    change_pct: Number.isFinite(detection.payload[metric + '_log_change']) ? Math.expm1(detection.payload[metric + '_log_change']) * 100 : null,
    is_risk_signal: detection[signal],
    has_enough_history: detection[signal] !== null && (detection.payload[metric + '_absolute_assessable'] === true || detection.payload[metric + '_local_assessable'] === true),
  })) : [];
  const openServices = () => { onEvidence(); setReviewRequest(value => value + 1); };
  async function save() {
    setSaving(true); setStatus('');
    try { const result = await api('/groups/review', { ...group, note, need, sourceRun: data.runId }); setSaved(result); clearDraft(); setStatus('이 집단의 검토 메모를 저장했습니다.'); }
    catch (e) { setStatus(e.message); } finally { setSaving(false); }
  }
  async function findServices() {
    serviceRequest.current?.abort(); const controller = new AbortController(); serviceRequest.current = controller;
    setSearching(true); setMatches(null); setServiceError('');
    try { const result = await api('/groups/services?' + query({ ...group, need }), undefined, { signal: controller.signal }); if (!controller.signal.aborted) setMatches(result); }
    catch (e) { if (e.name !== 'AbortError') setServiceError(e.message); } finally { if (serviceRequest.current === controller) setSearching(false); }
  }
  return <><section hidden={!shown && !evidenceShown} className={`gd-case ${evidenceShown ? 'gd-evidence-panel' : ''}`} role="tabpanel" id={'panel-' + groupKey(group)} aria-label={groupLabel(group)} ref={contentRef}>
    {error ? <div role="alert" className="gd-error">{error}<button onClick={() => { setError(''); setRetry(r => r + 1); }}>다시 연결</button></div> : !row ? <p role="status">집단별 근거를 읽고 있습니다…</p> : <>
      <div hidden={evidenceShown} className="gd-summary" data-summary-page={summaryPage}><div className="gd-overview gd-unified-overview"><DetectionHeading group={group} detection={detection} onEvidence={() => setSummaryPage(3)}/>
      {detection && <DetectionSummary detection={detection} rows={evidenceRows} group={group} onEvidence={() => setSummaryPage(3)}/>}
      <section className="gd-unified-flow" aria-label="유동량 참고"><div className="gd-flow-reference-label">관측된 활동량 변화</div><div className="gd-headline-row"><div><h3 className="gd-narrative">{Number.isFinite(row.change_pct) ? `${fmt(Math.abs(row.change_pct), 2)}% ${row.change_pct > 0 ? '증가' : row.change_pct < 0 ? '감소' : '변화 없음'}` : '비교 자료 부족'}</h3><p className="gd-metric-label">지난달과 비교한 활동량입니다.</p></div></div>
      <article className="gd-mini-trend"><h4>월별 유동량 추이</h4><LineChart points={data.series} label={`${groupLabel(group)} 월별 구역별 평균 유동량`} detail={p => Number.isFinite(p.change_pct) ? `전월 대비 ${pct(p.change_pct)} · 공통 구역 기준` : '전월 비교 불가'} /><small>각 월 전체 구역의 평균</small></article>
      <article className="gd-mini-share"><h4>동 전체에서 차지하는 비중</h4><strong>{fmt(row.share, 2)}<small>%</small></strong><div className="gd-share-track"><i style={{width: `${Number.isFinite(row.share) ? Math.max(0, Math.min(100, row.share)) : 0}%`}}/></div></article>
      <div className="gd-unified-flow-footer"><span>관측 활동량이며, 실제 사람 수와 다릅니다.</span></div></section><button className="primary gd-support-link gd-standalone-support" onClick={openServices}>지원사업 후보 확인 <Icon name="arrow" size={18}/></button><div className="gd-inline-background"><RegionContextCards structure={structure} survey={data.regional?.survey} detection={detection} group={group} backgroundOnly /></div></div>

      <p className="gd-detection-note">탐지 신호는 개인의 고립 판정이 아닙니다.</p>
      {evidenceRows.length > 0 && <div className="gd-signal-card"><DetectionEvidence rows={evidenceRows} group={group} detection={detection} onBack={() => { setSummaryPage(0); onSummary(); }}/></div>}
      </div><details hidden={evidenceShown || summaryPage !== 0} className="gd-all-details"><summary>자료 출처와 상세 값 보기</summary><div className="gd-more"><header className="gd-evidence-heading"><h2>상세 근거</h2><p>{groupLabel(group)} · {group.month}</p></header>
      <EvidencePages requestedPage={0}>
<details open><summary>월별 유동량·구성비 값</summary><PagedTable><thead><tr><th>기준월</th><th>구역별 평균 유동량</th><th>구성비</th></tr></thead><tbody>{data.series.map(p => <tr key={p.month}><th>{p.month}</th><td>{fmt(p.mean, 2)}</td><td>{fmt(p.share, 2)}%</td></tr>)}</tbody></PagedTable></details>
<details open><summary><Icon name="services" size={21}/>요일·시간대 활동 · 지역 전체 별도 집계</summary><p className="gd-caution">이 집단의 요일·시간대가 아닙니다. 지역 전체의 활동으로 서비스 운영 접점을 검토합니다.</p><div className="gd-activity"><div><h4>요일별 활동 <small>요일 평균=100</small></h4>{data.activity.weekdays?.map(d => <div className="gd-day" key={d.label}><span>{d.label}</span><i style={{ width: `${Math.min((d.index || 0) / 2, 100)}%` }} /><b>{fmt(d.index)}</b></div>) || <p>요일 자료 없음</p>}</div><div><h4>시간대 활동 <small>최대 시간대=100</small></h4>{data.activity.hours ? <LineChart points={data.activity.hours} field="index" label="지역 전체 시간대 활동 지수" /> : <p>시간대 자료 없음</p>}</div></div></details>
<details open><summary>자료 출처·범위와 계산 방법</summary><p>연령별 유동인구 자료 · 기준월 {group.month}</p><p>{data.note}</p>{user.admin && <p>{data.source} · {data.mapping}</p>}<p>구성비 = 집단 유동량 / 읍·면·동 전체 유동량. 구역별 평균 = 유동량 합 / 관측 구역 수. 전월 변화율 = (공통 구역의 현재 평균 / 전월 평균 − 1) × 100. 분모 0·전월 누락은 계산하지 않습니다.</p><p>동·연령별 통화·문자·이동 판정은 성별 통합입니다. 유동량과 통신·이동 탐지는 서로 다른 자료입니다.</p>{user.admin && <small>자료 버전 {data.runId.slice(0, 16)} · 읍·면·동 전체 지역 배경과 별도 집계</small>}</details>

<details open><summary><Icon name="chart" size={21}/>동·연령별 변화의 상세 근거</summary><DetectionEvidence rows={evidenceRows} group={group} detection={detection} onBack={() => { setSummaryPage(0); onSummary(); }}/><button className="text-button" onClick={() => onRegion(group)}>동·연령 분석 화면으로 →</button></details>
<details open><summary><Icon name="report" size={21}/>지역 배경 자료 출처</summary><p className="gd-caution">읍·면·동 전체의 지역 유형이며 이 집단의 가구·건강 상태를 뜻하지 않습니다. 월별 유동자료와 기준기간이 다릅니다.</p>{structure ? <><h3>{structure.cluster_type}</h3><p>1인가구 비중 {fmt(structure.payload.hh_1_ratio * 100)}% · 65세 이상 주민 비중 {fmt(structure.payload.resident_ratio_65_plus * 100)}%</p><small>지역 유형 분석 자료 · 기간은 자료마다 다릅니다{user.admin ? ` · ${structure.source_file}` : ''}</small></> : <p>연결된 지역 유형 자료가 없습니다.</p>}</details>
<details open><summary>같은 동의 연령별 유동량 구성</summary><p>선택한 동의 유동량 구성입니다. 주민등록 인구나 가구 유형을 의미하지 않습니다.</p><div className="gd-composition">{data.composition.map(g => <div key={g.age + g.sex} className={g.age === group.age && g.sex === group.sex ? 'selected' : ''}><span>{g.age}{g.sex === '통합' ? '' : ` · ${g.sex}`}</span><div><i style={{ width: `${g.share || 0}%` }} /></div><b>{fmt(g.share, 2)}%</b></div>)}</div></details>
<details open><summary>같은 연령대의 지역별 변화 비교</summary><p>각 동의 전월 공통 구역 기준 변화율입니다. 위험 순위나 개인 이동 경로가 아닙니다.</p><PagedTable><thead><tr><th>행정동</th><th>유동량 변화</th><th>공통 구역</th></tr></thead><tbody>{data.peers.map(p => <tr key={p.code}><th>{p.district}{p.code === group.code ? ' · 선택' : ''}</th><td>{pct(p.change_pct)}</td><td>{fmt(p.matched_points, 0)}개</td></tr>)}</tbody></PagedTable></details>
<details open><summary>시간대 활동 값 · 읍·면·동 전체</summary><p>읍·면·동 전체 집계이며 선택한 연령·성별 집단의 결과가 아닙니다.</p><PagedTable><thead><tr><th>시간대</th><th>활동 지수 (최대 시간대=100)</th></tr></thead><tbody>{(data.activity.hours || []).map(point => <tr key={point.label}><th>{point.label}</th><td>{fmt(point.index,2)}</td></tr>)}</tbody></PagedTable></details>

</EvidencePages></div></details><section hidden={!evidenceShown} className="gd-support-panel" aria-label="지원 검토"><header className="gd-evidence-heading"><h2>지원 검토</h2><p>{groupLabel(group)} · {group.month}</p></header><details open ref={servicesRef} className="gd-review"><summary>지원 필요 확인 · 메모와 사업 검토</summary><p>탐지 결과만으로 지원 필요나 이용 자격을 확정하지 않습니다. 검토 목적을 선택하고 실제 사업의 조건을 확인하세요.</p><label>검토할 지원 목적<select value={need} disabled={saving} onChange={e => { changeDraft({ need: e.target.value }); serviceRequest.current?.abort(); setMatches(null); setServiceError(''); }}><option value="">선택하세요</option>{['관계·사회참여', '안부·상담', '생활·경제'].map(n => <option key={n}>{n}</option>)}</select></label><label>이 집단의 검토 메모<textarea aria-label="집단 검토 메모" disabled={saving} rows="3" maxLength={3000} placeholder="관측 사실, 추가 확인 사항, 실제로 확인한 필요를 구분해서 기록하세요." value={note} onChange={e => changeDraft({ note: e.target.value })} /></label><div className="gd-review-actions"><button className="secondary" onClick={save} disabled={saving}>{saving ? '저장 중…' : '검토 메모 저장'}</button><button className="primary" disabled={!need || searching} onClick={findServices}>{searching ? '사업을 찾는 중…' : '조건 확인할 사업 찾기'}</button></div><p role="status">{storageFailed ? "임시 저장에 실패했습니다. 내용을 복사하거나 저장해 주세요." : status || (saved?.updatedAt ? `마지막 저장 ${saved.updatedAt.slice(0, 16).replace('T', ' ')}` : '')}</p>{serviceError && <p role="alert" className="gd-error">{serviceError}</p>}</details>{matches && <details open><summary>관련 사업 검색 결과</summary><ServiceResults matches={matches}/></details>}</section>

    </>}
  </section></>;
}

export default function GroupDashboard({ city, month: preferredMonth, user, onRegion, analysis, onActiveGroup, onMonthChange }) {
  const [catalog, setCatalog] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  // v2: 후보 우선 규칙(처음 방문 시 1순위 후보 동의 그룹)이 생기기 전에 저장된 탭 기록은 한 번 새로 시작합니다.
  const [stored, setStored, , workspaceStorageFailed] = useDraft(draftKey(user, { city }, 'group-workspace-v2'), emptyTabs);
  const state = restoreWorkspace(stored, city);
  const cases = city === '강남구' && analysis?.analysisScope === 'dong_age' ? analysis.ageDetections || [] : [];
  const analysisVersion = cases[0]?.model_version || '';
  const migrate = Boolean(analysisVersion && state.analysisVersion !== analysisVersion);
  const signalMonths = [...new Set(cases.filter(r => r.any_signal).map(r => r.month))].sort();
  const month = migrate ? signalMonths.at(-1) || preferredMonth : state.month || preferredMonth;
  useEffect(() => { if (month) onMonthChange?.(month); }, [month, onMonthChange]);
  const setState = update => setStored(old => update(restoreWorkspace(old, city)));
  const searchRef = useRef(null), tabRefs = useRef({});
  const tabsWindowRef = useRef(null), tabsTrackRef = useRef(null);
  const [tabWindowWidth, setTabWindowWidth] = useState(336);
  const [firstTab, setFirstTab] = useState(0);
  const measureTabs = useCallback(() => {
    const window = tabsWindowRef.current;
    if (window) setTabWindowWidth(window.clientWidth);
  }, []);
  useEffect(() => {
    const observer = new ResizeObserver(measureTabs);
    if (tabsWindowRef.current) observer.observe(tabsWindowRef.current);
    measureTabs();
    return () => observer.disconnect();
  }, [measureTabs]);
  const scrollTabs = direction => {
    const current=state.tabs.findIndex(g => groupKey(g) === state.active);
    const next=Math.max(0,Math.min(state.tabs.length-1,current+direction));
    if (state.tabs[next]) setState(old => ({...old,active:groupKey(old.tabs[next])}));
    if (workspaceTab === 'files') setShowFiles(false);
  };
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
          return {...valid, tabs, initialized:true, active:tabs.some(g => groupKey(g) === valid.active) ? valid.active : tabs.length ? groupKey(tabs[0]) : ''};
        }
        if (valid.initialized || !result.groups.length || valid.month !== month) return valid;
        const first = pickInitialGroup(result.groups, statusOf);
        return openGroup({ ...valid, initialized: true }, { city, code: first.code, district: first.district, age: first.age, sex: first.sex, month });
      });
    }).catch(e => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [city, month, retry, analysisVersion]);
  const open = group => { setState(s => openGroup({ ...s, initialized: true }, group)); setShowFiles(false); };
  const openFiles = (focus = false) => { setShowFiles(true); if (focus) setTimeout(() => searchRef.current?.focus(), 0); };
  const close = id => setState(s => closeGroup(s, id));
  const active = state.tabs.find(g => groupKey(g) === state.active);
  const evidenceShown = workspaceTab === 'support';
  const filesShown = workspaceTab === 'files' || (!active && !evidenceShown);
  const activeKey = active ? groupKey(active) : '';
  useEffect(() => { onActiveGroup?.(active || null); }, [activeKey, onActiveGroup]);
  const openEvidence = () => { setWorkspaceTab('support'); setSummaryStep(3); };
  // 위쪽 3단계를 누르면 열린 브리핑의 해당 부분으로 이동합니다. 3단계는 지원 검토 칸을 펼칩니다.
  const changeTab = (event,index) => {
    const ids=['overview','support','files'];let next=index;
    if(event.key==='ArrowRight') next=(index+1)%3;
    else if(event.key==='ArrowLeft') next=(index+2)%3;
    else if(event.key==='Home') next=0;
    else if(event.key==='End') next=2;
    else return;
    event.preventDefault();setWorkspaceTab(['group','support','files'][next]);setSummaryStep(next===1?3:1);
    requestAnimationFrame(()=>tabRefs.current[ids[next]]?.focus());
  };
  return <div className="gd-root">
    {document.getElementById('group-period-slot') && createPortal(<label>기준월<select aria-label="집단 자료 기준월" value={catalog?.months.includes(month) ? month : ''} disabled={loading || !catalog?.months.length} onChange={e => { const selected = e.target.value; setState(s => ({ ...s, month: selected, initialized:false })); }}>
      {!catalog?.months.includes(month) && <option value="">{loading ? '기간 확인 중…' : '제공 자료 없음'}</option>}{catalog?.months.slice().reverse().map(m => <option key={m} value={m}>{m}{cases.length ? ` · 탐지 ${cases.filter(r => r.month === m && r.any_signal).length}건` : ''}</option>)}
    </select>{cases.length > 0 && <small className="gd-observation-window">통신·이동 관측 {observationWindow(month)}</small>}</label>, document.getElementById('group-period-slot'))}
    {workspaceStorageFailed && <p className="gd-scope-note" role="status">탭 임시 저장에 실패했습니다. 새로고침 시 열린 탭을 복원하지 못할 수 있습니다.</p>}
    {active && active.month !== month && <p className="gd-scope-note">조사 파일 기준월은 {month}, 현재 열린 브리핑은 <b>{active.month} · {groupLabel(active)}</b>입니다.</p>}
    <div className="gd-workspace"><ol className="gd-process" aria-label="브리핑 읽는 순서">{[['연락·이동 변화 확인', '탐지된 변화와 감소 폭을 살펴봅니다.'], ['가구·관계망 함께 보기', '가구 구성과 사회적 연결을 함께 봅니다.'], ['필요한 지원 검토', '확인한 필요에 맞는 지원을 검토합니다.']].map(([title, text], i) => <li key={title}><div className="gd-step-guide"><b>{i + 1}</b><span className="gd-step-icon"><Icon name={['discover', 'neighborhood', 'support'][i]} size={26}/></span><div><strong>{title}</strong><span>{text}</span></div></div></li>)}</ol><div className="gd-tabbar"><div className="gd-tabs-window"><div className="gd-tabs-track" role="tablist" aria-label="사례 검토 파일">
        {[['overview','탐지 현황','clipboard'],['support','지원 검토','services'],['files','조사 파일','report']].map(([id,label,icon],index)=>{const selected=id==='overview'?!filesShown&&!evidenceShown:id==='support'?evidenceShown:filesShown;return <div key={id} className={`gd-tab ${selected?'active':''}`}><button role="tab" id={'tab-'+id} aria-selected={selected} aria-controls={id==='files'?'panel-files':active?'panel-'+groupKey(active):'panel-evidence-empty'} tabIndex={selected?0:-1} ref={el=>{tabRefs.current[id]=el;}} onKeyDown={e=>changeTab(e,index)} onClick={()=>{setWorkspaceTab(['group','support','files'][index]);setSummaryStep(index===1?3:1);}}><Icon name={icon} size={22}/><span><b>{label}</b></span></button></div>;})}
      </div></div><div className="gd-tab-controls">{state.tabs.length>0 && <span className="gd-case-counter" aria-label="현재 탐지 사례 순서">{state.tabs.findIndex(g=>groupKey(g)===state.active)+1} / {state.tabs.length}</span>}<button className="gd-tab-arrow previous" aria-label="이전 탐지 사례" disabled={state.tabs.findIndex(g=>groupKey(g)===state.active)<=0} onClick={()=>scrollTabs(-1)}><Icon name="arrow" size={18}/></button><button className="gd-tab-arrow" aria-label="다음 탐지 사례" disabled={!state.tabs.length || state.tabs.findIndex(g=>groupKey(g)===state.active)>=state.tabs.length-1} onClick={()=>scrollTabs(1)}><Icon name="arrow" size={18}/></button></div></div>
      <section className="gd-case gd-files-panel" role="tabpanel" id="panel-files" aria-labelledby="tab-files" hidden={!filesShown}><Directory catalog={catalog} city={city} month={month} loading={loading} error={error} retry={() => setRetry(n => n + 1)} onOpen={open} state={state} searchRef={searchRef} statusOf={statusOf} detectionMode={cases.length > 0} /></section>
      {state.tabs.map(g => <GroupCase key={groupKey(g)} group={g} active={groupKey(g) === state.active} shown={!filesShown && !evidenceShown && groupKey(g) === state.active} evidenceShown={evidenceShown && groupKey(g) === state.active} onEvidence={openEvidence} summaryStep={summaryStep} user={user} onRegion={onRegion} analysis={analysis} onSummary={() => {setWorkspaceTab('group'); setSummaryStep(1);}} candidate={CANDIDATE_ORDER.includes(statusOf(g)?.status) ? statusOf(g) : null} />)}
<section id="panel-evidence-empty" role="tabpanel" aria-labelledby="tab-support" className="gd-case" hidden={filesShown || !!active}><h2>검토할 사례를 선택하세요</h2><p>선택한 월의 탐지 사례가 없습니다. 조사 파일에서 기준월과 사례를 확인하세요.</p><button className="primary" onClick={() => openFiles()}>조사 파일에서 그룹 선택</button></section>
    </div>
  </div>;
}
