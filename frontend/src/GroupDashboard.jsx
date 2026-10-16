import DetectionEvidence, { SignalBadges, signalState, signalExplanation } from './DetectionEvidence';
import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, query } from './api';
import { Icon } from './components';
import { useDraft } from './useDraft';
import { draftKey } from './draftStore.mjs';
import { groupKey, groupLabel, openGroup, restoreWorkspace, availableWorkspace, rankGroups, pickInitialGroup, CANDIDATE_ORDER } from './groupTabs.mjs';
import { summarizeRegions } from './Briefing';
import './group-dashboard.css';
import RegionContextCards from './RegionContextCards';
import { comparisonRows, signedBar } from './regionalPresentation.mjs';
import { ageStatus, detectionTabs, observationWindow } from './ageSignals.mjs';

const fmt = (n, digits = 1) => Number.isFinite(n) ? n.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '—';
const pct = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${fmt(n, 2)}%` : '비교 불가';
const emptyTabs = { tabs: [], active: '' };
const PAGE_SIZE = 12;

function PageButtons({ page, pages, onPage, label }) {
  return <div className="gd-page-buttons" aria-label={label}><button disabled={!page} onClick={() => onPage(page - 1)}>이전</button><span>{page + 1} / {pages}</span><button disabled={page + 1 >= pages} onClick={() => onPage(page + 1)}>다음</button></div>;
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

function DetectionHeading({group, detection, onEvidence}) {
  const p=detection?.payload || {};
  const domains=[['communication','전화·문자 연락','chat'],['mobility','평일·휴일 이동','chart']].filter(([key])=>detection?.[key+'_signal']);
  return <header className="gd-case-heading gd-unified-heading"><div className="gd-case-title"><h2>{groupLabel(group)}</h2>{domains.map(([key,label,icon])=><span key={key} className={`gd-domain-chip signal-${signalState(p[key+'_absolute_signal'],p[key+'_local_signal'])}`}><Icon name={icon} size={20}/>{label} 감소 탐지</span>)}<button className="text-button gd-heading-evidence" onClick={onEvidence}>탐지 근거 보기 →</button></div><div className="gd-path-explanation">{domains.map(([key])=><span className="gd-domain-explanation" key={key}>{domains.length>1&&<b>{key==='communication'?'통신':'이동'}</b>}<SignalBadges absolute={p[key+'_absolute_signal']} local={p[key+'_local_signal']}/></span>)}{domains.length===1&&<p>{signalExplanation(p[domains[0][0]+'_absolute_signal'], p[domains[0][0]+'_local_signal'], group.city)}</p>}</div></header>;
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

function GroupCase({ group, shown, evidenceShown, summaryStep, user, onEvidence, analysis, onSummary }) {
  const [summaryPage, setSummaryPage] = useState(0);
  useEffect(() => { setSummaryPage(0); }, [summaryStep]);
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const [draft, setDraft, clearDraft, storageFailed] = useDraft(draftKey(user, group, `group-review:${group.code}:${group.age}:${group.sex}`), { note: '', need: '' });
  const [saved, setSaved] = useState(null), [status, setStatus] = useState(''), [saving, setSaving] = useState(false);
  const [matches, setMatches] = useState(null), [serviceError, setServiceError] = useState(''), [searching, setSearching] = useState(false);
  const serviceRequest = useRef(null);
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
  const openServices = () => onEvidence();
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
  return <><section hidden={!shown && !evidenceShown} className={`gd-case ${evidenceShown ? 'gd-evidence-panel' : ''}`} role="tabpanel" id={'panel-' + groupKey(group)} aria-label={groupLabel(group)}>
    {error ? <div role="alert" className="gd-error">{error}<button onClick={() => { setError(''); setRetry(r => r + 1); }}>다시 연결</button></div> : !row ? <p role="status">집단별 근거를 읽고 있습니다…</p> : <>
      <div hidden={evidenceShown} className="gd-summary" data-summary-page={summaryPage}><div className="gd-overview gd-unified-overview"><DetectionHeading group={group} detection={detection} onEvidence={() => setSummaryPage(3)}/>
      {detection && <DetectionSummary detection={detection} group={group}/>}
      <section className="gd-unified-flow" aria-label="유동량 참고"><div className="gd-heading-with-note"><h3 className="gd-flow-reference-label">{group.district} {group.age} 유동량 변화</h3><small className="gd-period-note">직전 기준월 대비</small></div>
      <h3 className="gd-narrative">{Number.isFinite(row.change_pct) ? `${fmt(Math.abs(row.change_pct), 2)}% ${row.change_pct > 0 ? '증가' : row.change_pct < 0 ? '감소' : '변화 없음'}` : '비교 자료 부족'}</h3>
      <article className="gd-mini-trend"><LineChart points={data.series} label={`${groupLabel(group)} 월별 구역별 평균 유동량`}/></article>
      <article className="gd-mini-share"><h4>{group.district} 전체 유동량 중 {group.age} 비율</h4><strong>{fmt(row.share, 2)}<small>%</small></strong><div className="gd-share-track"><i style={{width: `${Number.isFinite(row.share) ? Math.max(0, Math.min(100, row.share)) : 0}%`}}/></div></article></section><button className="primary gd-support-link gd-standalone-support" onClick={openServices}>지원사업 후보 확인 <Icon name="arrow" size={18}/></button><div className="gd-inline-background"><RegionContextCards structure={structure} survey={data.regional?.survey} group={group} /></div></div>
      {evidenceRows.length > 0 && <div className="gd-signal-card"><DetectionEvidence rows={evidenceRows} group={group} detection={detection} onBack={() => { setSummaryPage(0); onSummary(); }}/></div>}
      </div><section hidden={!evidenceShown} className="gd-support-panel" aria-label="지원 검토"><header className="gd-evidence-heading"><h2>지원 검토</h2><p>{groupLabel(group)} · {group.month}</p></header><details open className="gd-review"><summary>지원 필요 확인 · 메모와 사업 검토</summary><p>탐지 결과만으로 지원 필요나 이용 자격을 확정하지 않습니다. 검토 목적을 선택하고 실제 사업의 조건을 확인하세요.</p><label>검토할 지원 목적<select value={need} disabled={saving} onChange={e => { changeDraft({ need: e.target.value }); serviceRequest.current?.abort(); setMatches(null); setServiceError(''); }}><option value="">선택하세요</option>{['관계·사회참여', '안부·상담', '생활·경제'].map(n => <option key={n}>{n}</option>)}</select></label><label>이 집단의 검토 메모<textarea aria-label="집단 검토 메모" disabled={saving} rows="3" maxLength={3000} placeholder="관측 사실, 추가 확인 사항, 실제로 확인한 필요를 구분해서 기록하세요." value={note} onChange={e => changeDraft({ note: e.target.value })} /></label><div className="gd-review-actions"><button className="secondary" onClick={save} disabled={saving}>{saving ? '저장 중…' : '검토 메모 저장'}</button><button className="primary" disabled={!need || searching} onClick={findServices}>{searching ? '사업을 찾는 중…' : '조건 확인할 사업 찾기'}</button></div><p role="status">{storageFailed ? "임시 저장에 실패했습니다. 내용을 복사하거나 저장해 주세요." : status || (saved?.updatedAt ? `마지막 저장 ${saved.updatedAt.slice(0, 16).replace('T', ' ')}` : '')}</p>{serviceError && <p role="alert" className="gd-error">{serviceError}</p>}</details>{matches && <details open><summary>관련 사업 검색 결과</summary><ServiceResults matches={matches}/></details>}</section>

    </>}
  </section></>;
}

export default function GroupDashboard({ city, month: preferredMonth, user, analysis, onActiveGroup, onMonthChange }) {
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
  const active = state.tabs.find(g => groupKey(g) === state.active);
  const evidenceShown = workspaceTab === 'support';
  const filesShown = workspaceTab === 'files' || (!active && !evidenceShown);
  const activeKey = active ? groupKey(active) : '';
  useEffect(() => { onActiveGroup?.(active || null); }, [activeKey, onActiveGroup]);
  const openEvidence = () => { setWorkspaceTab('support'); setSummaryStep(3); };
  // 파일 탭의 키보드 탐색 순서입니다.
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
      {state.tabs.map(g => <GroupCase key={groupKey(g)} group={g} shown={!filesShown && !evidenceShown && groupKey(g) === state.active} evidenceShown={evidenceShown && groupKey(g) === state.active} onEvidence={openEvidence} summaryStep={summaryStep} user={user} analysis={analysis} onSummary={() => {setWorkspaceTab('group'); setSummaryStep(1);}} />)}
<section id="panel-evidence-empty" role="tabpanel" aria-labelledby="tab-support" className="gd-case" hidden={filesShown || !!active}><h2>검토할 사례를 선택하세요</h2><p>선택한 월의 탐지 사례가 없습니다. 조사 파일에서 기준월과 사례를 확인하세요.</p><button className="primary" onClick={() => openFiles()}>조사 파일에서 그룹 선택</button></section>
    </div>
  </div>;
}
