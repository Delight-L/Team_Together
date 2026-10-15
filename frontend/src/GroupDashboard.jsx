import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { api, query } from './api';
import { Icon } from './components';
import { useDraft } from './useDraft';
import { useTransientMessage } from './useTransientMessage';
import { draftKey } from './draftStore.mjs';
import { groupKey, groupLabel, openGroup, closeGroup, restoreWorkspace, availableWorkspace, rankGroups, pickInitialGroup, CANDIDATE_ORDER } from './groupTabs.mjs';
import { summarizeRegions } from './Briefing';
import './group-dashboard.css';
import RegionContextCards from './RegionContextCards';
import { areaUnit } from './regionalPresentation.mjs';
import { showToast } from './toast';
import { tabPage, tabPageForSelected } from './tabPaging.mjs';
import { fitDomain } from './chartScale.mjs';
import { ReferenceServiceList } from './ReferenceServices';

const fmt = (n, digits = 1) => Number.isFinite(n) ? n.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '—';
const pct = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${fmt(n, 2)}%` : '비교 불가';
// 마지막 글자의 받침 여부로 조사를 고릅니다(예: 삼성1동은, 역삼2동은).
const withJosa = (word, batchim, plain) => {
  const code = String(word).charCodeAt(String(word).length - 1) - 0xac00;
  return word + (code >= 0 && code <= 11171 && code % 28 ? batchim : plain);
};
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

// 요약 왼쪽 칸의 핵심 수치 세 가지. 모두 화면이 이미 받은 집단 자료로 계산합니다(위험 순위가 아님).
function GroupFacts({ group, row, data }) {
  const previous = data.series.length > 1 ? data.series.at(-2)?.mean : undefined;
  const shares = data.composition.filter(g => Number.isFinite(g.share)).sort((a, b) => b.share - a.share);
  const shareRank = shares.findIndex(g => g.age === group.age && g.sex === group.sex) + 1;
  const changes = data.peers.map(p => p.change_pct).filter(Number.isFinite).sort((a, b) => a - b);
  const mid = changes.length ? (changes.length % 2 ? changes[(changes.length - 1) / 2] : (changes[changes.length / 2 - 1] + changes[changes.length / 2]) / 2) : null;
  const facts = [
    // 전월 값은 전체 구역 평균이라, 공통 구역끼리 비교한 아래 변화율과 직접 나눠 맞지 않습니다.
    Number.isFinite(row.mean) && ['월 평균 유동량', fmt(row.mean, 1), Number.isFinite(previous) ? `전월 ${fmt(previous, 1)} · 전체 구역 평균` : '전월 자료 없음'],
    shareRank > 0 && ['동 안 비율 순서', `${shareRank}번째`, `${group.district} ${shares.length}개 그룹 중`],
    mid !== null && [`비교: ${group.city} 중앙값`, `${mid > 0 ? '+' : ''}${fmt(mid, 2)}%`, `같은 ${group.age} ${group.sex} · ${changes.length}개 동의 전월 대비`],
  ].filter(Boolean);
  if (!facts.length) return null;
  return <dl className="gd-facts">{facts.map(([label, value, note]) => <div key={label}><dt>{label}</dt><dd><b>{value}</b><small>{note}</small></dd></div>)}</dl>;
}

// 동 유동량 중 이 그룹의 비율: 이번 달 값, 전월 대비 %p, 월별 추이를 함께 보여 줍니다.
function ShareTrend({ row, series, label, title }) {
  const shares = series.filter(p => Number.isFinite(p.share));
  const previous = series.length > 1 ? series.at(-2)?.share : undefined;
  const delta = Number.isFinite(row.share) && Number.isFinite(previous) ? row.share - previous : null;
  const down = delta !== null && delta < 0;
  // 기간 안에서 가장 높거나 낮을 때만 짧게 해석을 붙입니다.
  let insight = '';
  if (shares.length >= 3 && Number.isFinite(row.share)) {
    const values = shares.map(p => p.share);
    if (row.share <= Math.min(...values)) insight = `최근 ${shares.length}개월 중 가장 낮은 비율입니다.`;
    else if (row.share >= Math.max(...values)) insight = `최근 ${shares.length}개월 중 가장 높은 비율입니다.`;
  }
  return <article className="gd-mini-share"><h4>{title}</h4>
    <div className="gd-share-head"><strong>{fmt(row.share, 2)}<small>%</small></strong>
      {delta !== null && <span className={`gd-share-delta ${down ? 'down' : 'up'}`}>전월 대비 {delta > 0 ? '+' : delta < 0 ? '−' : '±'}{fmt(Math.abs(delta), 2)}%p</span>}</div>
    {shares.length >= 2 ? <LineChart points={series} field="share" unit="%" label={label} lastColor={down ? '#e0264a' : '#2563eb'} detail={(p, i) => { const before = series[i - 1]?.share; return Number.isFinite(before) ? `전월 대비 ${p.share - before > 0 ? '+' : p.share - before < 0 ? '−' : '±'}${fmt(Math.abs(p.share - before), 2)}%p` : '전월 비교 불가'; }} /> : null}
    {insight && <p className="gd-share-insight">{insight}</p>}
    <p>유동량은 실제 사람 수와 다릅니다.</p></article>;
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
      // 실제 높이에 들어가는 줄만 표시하고 나머지는 다음 페이지로 넘깁니다.
      const height = cardHeight(list);
      const rows = Math.max(1, Math.min(Math.ceil(PAGE_SIZE / cols), Math.floor((list.clientHeight + rowGap) / (height + rowGap))));
      list.style.setProperty('--gd-card-h', height + 'px');
      setGrid(old => old.cols === cols && old.rows === rows ? old : { cols, rows });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [list]);
  return grid;
}

function Directory({ catalog, loading, error, retry, city, month, onOpen, state, searchRef, statusOf }) {
  const unit = areaUnit(city);
  const [search, setSearch] = useState(''), [age, setAge] = useState(''), [sex, setSex] = useState(''), [district, setDistrict] = useState(''), [page, setPage] = useState(0);
  const filtered = rankGroups((catalog?.groups || []).filter(g => (!district || g.code === district) && (!age || g.age === age) && (!sex || g.sex === sex) && `${g.district} ${g.age} ${g.sex}`.includes(search.trim())), statusOf);
  useEffect(() => setPage(0), [search, age, sex, district, month, city]);
  // 목록이 다시 그려져 요소가 바뀌어도 크기 감시를 새 요소에 연결하도록 state로 받습니다.
  const [listElement, setListElement] = useState(null);
  const { cols, rows } = useCardGrid(listElement);
  const pageSize = cols * rows;
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const current = Math.min(page, pages - 1);
  return <div className="gd-directory"><header><h2>조사 파일</h2><span>{month}</span></header><p>살펴볼 {unit}·연령·성별 그룹을 고르면 옆에 브리핑 탭이 열립니다. 집단별 유동인구 자료이며 위험 순위가 아닙니다.</p>
    <input ref={searchRef} aria-label={`${unit}·연령·성별 검색`} placeholder={`${unit}·연령·성별 검색`} value={search} onChange={e => setSearch(e.target.value)} />
    <div className="gd-directory-filters"><label>{unit}<select aria-label={`${unit} 필터`} value={district} onChange={e => setDistrict(e.target.value)}><option value="">전체 {unit}</option>{catalog?.districts.map(d => <option key={d.code} value={d.code}>{d.name}</option>)}</select></label><select aria-label="연령 필터" value={age} onChange={e => setAge(e.target.value)}><option value="">모든 연령</option>{catalog?.ages.map(a => <option key={a}>{a}</option>)}</select><select aria-label="성별 필터" value={sex} onChange={e => setSex(e.target.value)}><option value="">모든 성별</option>{catalog?.sexes.map(s => <option key={s}>{s}</option>)}</select></div>
    {loading ? <p role="status">그룹 자료를 읽고 있습니다…</p> : error ? <div role="alert" className="gd-error">{error}<button onClick={retry}>다시 연결</button></div> : !filtered.length ? <p className="gd-empty">선택 조건의 자료가 없습니다.{catalog?.months.length > 0 && <span> 제공 기간 {catalog.months[0]} ~ {catalog.months.at(-1)}</span>}</p> : <div className="gd-file-list" ref={setListElement} style={{ '--gd-cols': cols, '--gd-rows': rows }}>{filtered.slice(current * pageSize, current * pageSize + pageSize).map(g => {
      const group = { city, code: g.code, district: g.district, age: g.age, sex: g.sex, month: g.month }, id = groupKey(group);
      const opened = state.tabs.some(t => groupKey(t) === id);
      return <button key={id} className={state.active === id ? 'selected' : ''} title={groupLabel(g)} onClick={() => onOpen(group)}><Icon name="report" size={21} /><span><strong>{groupLabel(g)}</strong><small>{g.month} · 구성비 {fmt(g.share)}%{Number.isFinite(g.change_pct) ? ` · 유동량 ${pct(g.change_pct)}` : ''}</small></span>{CANDIDATE_ORDER.includes(statusOf(g)?.status) && <i className="gd-candidate" title={`${g.district} ${unit} 전체 판정입니다. 이 그룹 자체의 판정이 아닙니다.`}>{unit === '동' ? '동' : '지역'} {statusOf(g).status}</i>}{opened ? <em>{state.active === id ? '현재 탭' : '열림'}</em> : <span aria-hidden="true">›</span>}</button>;
    })}</div>}
    <footer><span>{filtered.length}개 그룹 · {current + 1}/{pages}</span><button aria-label="이전 그룹 목록" disabled={current === 0} onClick={() => setPage(current - 1)}>‹</button><button aria-label="다음 그룹 목록" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>›</button></footer>
    <p className="gd-source">유동인구 연령·성별 집계<br />집단별 통화·문자 신호는 아직 연결되지 않았습니다.</p>
  </div>;
}

function FittedBriefing({ hidden, children }) {
  const frameRef = useRef(null), bodyRef = useRef(null);
  useLayoutEffect(() => {
    const frame = frameRef.current, body = bodyRef.current;
    const fit = () => {
      if (!frame.clientWidth || !frame.clientHeight) return;
      const style = getComputedStyle(frame);
      const width = frame.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      const height = frame.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
      // 축소한 뒤에도 실제 가로폭을 채우도록 원본 폭을 함께 늘립니다.
      // 높이에 맞는 가장 큰 배율을 찾으므로 오른쪽에 빈 공간이 남지 않습니다.
      let low = 0.1, high = Math.min(1, width / 1050);
      for (let i = 0; i < 12; i += 1) {
        const scale = (low + high) / 2;
        body.style.width = width / scale + 'px';
        if (body.offsetHeight * scale <= height) low = scale;
        else high = scale;
      }
      body.style.width = width / low + 'px';
      body.style.zoom = low;
    };
    const observer = new ResizeObserver(fit);
    observer.observe(frame); observer.observe(body);
    fit();
    return () => observer.disconnect();
  }, [hidden]);
  return <div hidden={hidden} className="gd-summary" ref={frameRef}><div className="gd-summary-content" ref={bodyRef}>{children}</div></div>;
}

function GroupCase({ group, active, shown, evidenceShown, summaryStep, user, onRegion, onEvidence, candidate }) {
  const unit = areaUnit(group.city);
  const [reviewRequest, setReviewRequest] = useState(0);
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const [draft, setDraft, clearDraft, storageFailed] = useDraft(draftKey(user, group, `group-review:${group.code}:${group.age}:${group.sex}`), { note: '', need: '' });
  const [saved, setSaved] = useState(null), [saving, setSaving] = useState(false);
  const [status, setStatus] = useTransientMessage();
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
  const regionalRows = detection ? [['call_contacts', '전화 연락', 'communication_signal'], ['text_contacts', '문자 연락', 'communication_signal'], ['weekday_move_count', '평일 이동', 'mobility_signal'], ['weekend_move_count', '휴일 이동', 'mobility_signal']].map(([metric, label, signal]) => ({
    metric_label: label,
    change_pct: Number.isFinite(detection.payload[metric + '_log_change']) ? Math.expm1(detection.payload[metric + '_log_change']) * 100 : null,
    is_risk_signal: detection[signal],
    has_enough_history: Number.isFinite(detection.payload[metric + '_residual_change_expanding_rz']),
  })) : [];
  const openServices = () => { onEvidence(); setReviewRequest(value => value + 1); };
  async function save() {
    setSaving(true); setStatus('');
    try { const result = await api('/groups/review', { ...group, note, need, sourceRun: data.runId }); setSaved(result); clearDraft(); showToast(`${groupLabel(group)} · ${group.month} · 검토 메모를 저장했어요.`); }
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
      <FittedBriefing hidden={evidenceShown}><div className="gd-overview"><div className="gd-overview-copy"><header className="gd-case-heading"><div><span className="gd-eyebrow">{group.month} · 집단 브리핑</span><h2>{groupLabel(group)}</h2></div>{candidate ? <span className="gd-badge gd-candidate-badge" title={`${unit} 전체 판정입니다. 이 그룹 자체의 판정이 아닙니다.`}>{group.district} {candidate.status}</span> : <span className="gd-badge">선택한 집단</span>}</header>
      {candidate && <p className="gd-candidate-note">{withJosa(group.district, '은', '는')} {group.month} {unit} 전체 분석에서 <b>{candidate.status}</b>입니다({candidate.metrics?.length ? candidate.metrics.join('·') : `후보 지표 ${candidate.count}개`}). {group.age} {group.sex} 그룹 자체의 판정은 아니며, 후보 {unit === '동' ? '동' : '지역'}의 그룹이라 먼저 보여 드려요.</p>}
      <GroupFacts group={group} row={row} data={data} /><div className="gd-headline-row"><div><h3 className="gd-narrative">{Number.isFinite(row.change_pct) ? `${fmt(Math.abs(row.change_pct), 2)}% ${row.change_pct > 0 ? '증가' : row.change_pct < 0 ? '감소' : '변화 없음'}` : '비교 자료 부족'}</h3><p className="gd-metric-label">이 그룹의 전월 대비 유동량 · 두 달 모두 관측된 구역 기준</p></div><button className="primary gd-support-link" onClick={openServices}>지원사업 후보 확인 <Icon name="arrow" size={22}/></button></div>
      <p className="gd-caption"><abbr title="그 지역에서 관측된 활동 규모입니다. 실제 사람 수와는 다릅니다.">유동량</abbr>은 그 지역에서 관측된 활동 규모(실제 사람 수 아님)이며, 지난달과 이번 달 모두 자료가 있는 구역끼리 비교했습니다.</p></div>
      <article className="gd-mini-trend"><h4>월별 유동량 추이</h4><div className="gd-share-head"><strong>{fmt(row.mean, 1)}</strong><span className="gd-trend-value-label">월 평균 유동량</span></div><LineChart points={data.series} label={`${groupLabel(group)} 월별 구역별 평균 유동량`} detail={p => Number.isFinite(p.change_pct) ? `전월 대비 ${pct(p.change_pct)} · 공통 구역 기준` : '전월 비교 불가'} /><small>각 월 전체 구역의 평균</small></article>
      <ShareTrend row={row} series={data.series} label={`${groupLabel(group)} 월별 ${group.district} 유동량 중 비율`} title={`${group.district} 유동량 중 ${group.age} ${group.sex} 비율`} /></div>
      <RegionContextCards structure={structure} detection={detection} group={group}/>
      </FittedBriefing><section hidden={!evidenceShown} ref={moreRef} className="gd-more" aria-label="전체 근거와 지원 검토"><header className="gd-evidence-heading"><h2>전체 근거와 지원 검토</h2><p>{groupLabel(group)} · {group.month}</p></header>
      <EvidencePages requestedPage={reviewRequest || (summaryStep === 3 ? 1 : 0)}>
<details open><summary>월별 유동량·구성비 값</summary><PagedTable><thead><tr><th>기준월</th><th>구역별 평균 유동량</th><th>구성비</th></tr></thead><tbody>{data.series.map(p => <tr key={p.month}><th>{p.month}</th><td>{fmt(p.mean, 2)}</td><td>{fmt(p.share, 2)}%</td></tr>)}</tbody></PagedTable></details>
<details open><summary><Icon name="services" size={21}/>요일·시간대 활동 · 지역 전체 별도 집계</summary><p className="gd-caution">이 집단의 요일·시간대가 아닙니다. 지역 전체의 활동으로 서비스 운영 접점을 검토합니다.</p><div className="gd-activity"><div><h4>요일별 활동 <small>요일 평균=100</small></h4>{data.activity.weekdays?.map(d => <div className="gd-day" key={d.label}><span>{d.label}</span><i style={{ width: `${Math.min((d.index || 0) / 2, 100)}%` }} /><b>{fmt(d.index)}</b></div>) || <p>요일 자료 없음</p>}</div><div><h4>시간대 활동 <small>최대 시간대=100</small></h4>{data.activity.hours ? <LineChart points={data.activity.hours} field="index" label="지역 전체 시간대 활동 지수" /> : <p>시간대 자료 없음</p>}</div></div></details>
<details open><summary>자료 출처·범위와 계산 방법</summary><p>연령·성별 유동인구 자료 · 기준월 {group.month}</p><p>{data.note}</p>{user.admin && <p>{data.source} · {data.mapping}</p>}<p>구성비 = 집단 유동량 / {unit} 전체 유동량. 구역별 평균 = 유동량 합 / 관측 구역 수. 전월 변화율 = (공통 구역의 현재 평균 / 전월 평균 − 1) × 100. 분모 0·전월 누락은 계산하지 않습니다.</p><p>연령·성별 그룹별 통화·문자·이동 분석은 아직 연결되지 않았습니다. {unit} 전체 분석과는 집계 범위가 달라 값을 섞지 않습니다.</p>{user.admin && <small>자료 버전 {data.runId.slice(0, 16)} · {unit} 전체 지역 배경과 별도 집계</small>}</details>
<details open ref={servicesRef} className="gd-review"><summary>지원 필요 확인 · 메모와 사업 검토</summary><p>유동량만으로 지원 필요나 이용 자격을 확정하지 않습니다. 검토 목적을 선택하고 실제 사업의 조건을 확인하세요.</p><label>검토할 지원 목적<select value={need} disabled={saving} onChange={e => { changeDraft({ need: e.target.value }); serviceRequest.current?.abort(); setMatches(null); setServiceError(''); }}><option value="">선택하세요</option>{['관계·사회참여', '안부·상담', '생활·경제'].map(n => <option key={n}>{n}</option>)}</select></label><label>이 집단의 검토 메모<textarea aria-label="집단 검토 메모" disabled={saving} rows="3" maxLength={3000} placeholder="관측 사실, 추가 확인 사항, 실제로 확인한 필요를 구분해서 기록하세요." value={note} onChange={e => changeDraft({ note: e.target.value })} /></label><div className="gd-review-actions"><button className="secondary" onClick={save} disabled={saving}>{saving ? '저장 중…' : '검토 메모 저장'}</button><button className="primary" disabled={!need || searching} onClick={findServices}>{searching ? '사업을 찾는 중…' : '조건 확인할 사업 찾기'}</button></div><p role="status">{storageFailed ? "임시 저장에 실패했습니다. 내용을 복사하거나 저장해 주세요." : status || (saved?.updatedAt ? `마지막 저장 ${saved.updatedAt.slice(0, 16).replace('T', ' ')}` : '')}</p>{serviceError && <p role="alert" className="gd-error">{serviceError}</p>}</details>
<details open><summary><Icon name="chart" size={21}/>{unit} 전체 변화의 상세 근거</summary><p className="gd-caution">{unit} 전체 통화·문자·이동 결과이며, 선택한 {group.age} {group.sex} 집단의 결과가 아닙니다.</p>{regionalRows.length ? <PagedTable><thead><tr><th>지표</th><th>전월 변화</th><th>{unit} 전체 판정</th></tr></thead><tbody>{regionalRows.map(r => <tr key={r.metric_label}><th>{r.metric_label}</th><td>{pct(r.change_pct)}</td><td>{r.is_risk_signal ? '변화 후보' : r.has_enough_history ? '기준 미해당' : '비교 보류'}</td></tr>)}</tbody></PagedTable> : <p>같은 동·월의 분석 자료가 없습니다.</p>}<p>과거 흐름과 여러 지표를 함께 비교한 결과입니다.</p><button className="text-button" onClick={() => onRegion(group)}>{unit} 전체 분석 화면으로 →</button></details>
<details open><summary><Icon name="report" size={21}/>지역 배경 자료 출처</summary><p className="gd-caution">{unit} 전체의 지역 유형이며 이 집단의 가구·건강 상태를 뜻하지 않습니다. 월별 유동자료와 기준기간이 다릅니다.</p>{structure ? <><h3>{structure.cluster_type}</h3><p>1인가구 비중 {fmt(structure.payload.hh_1_ratio * 100)}% · 65세 이상 주민 비중 {fmt(structure.payload.resident_ratio_65_plus * 100)}%</p><small>지역 유형 분석 자료 · 기간은 자료마다 다릅니다{user.admin ? ` · ${structure.source_file}` : ''}</small></> : <p>연결된 지역 유형 자료가 없습니다.</p>}</details>
<details open><summary>같은 동의 연령·성별 유동량 구성</summary><p>선택한 동의 유동량 구성입니다. 주민등록 인구나 가구 유형을 의미하지 않습니다.</p><div className="gd-composition">{data.composition.map(g => <div key={g.age + g.sex} className={g.age === group.age && g.sex === group.sex ? 'selected' : ''}><span>{g.age} · {g.sex}</span><div><i style={{ width: `${g.share || 0}%` }} /></div><b>{fmt(g.share, 2)}%</b></div>)}</div></details>
<details open><summary>같은 연령·성별의 지역별 변화 비교</summary><p>각 동의 전월 공통 구역 기준 변화율입니다. 위험 순위나 개인 이동 경로가 아닙니다.</p><PagedTable><thead><tr><th>행정동</th><th>유동량 변화</th><th>공통 구역</th></tr></thead><tbody>{data.peers.map(p => <tr key={p.code}><th>{p.district}{p.code === group.code ? ' · 선택' : ''}</th><td>{pct(p.change_pct)}</td><td>{fmt(p.matched_points, 0)}개</td></tr>)}</tbody></PagedTable></details>
<details open><summary>시간대 활동 값 · {unit} 전체</summary><p>{unit} 전체 집계이며 선택한 연령·성별 집단의 결과가 아닙니다.</p><PagedTable><thead><tr><th>시간대</th><th>활동 지수 (최대 시간대=100)</th></tr></thead><tbody>{(data.activity.hours || []).map(point => <tr key={point.label}><th>{point.label}</th><td>{fmt(point.index,2)}</td></tr>)}</tbody></PagedTable></details>
{matches && <details open><summary>관련 사업 검색 결과</summary><ServiceResults matches={matches}/></details>}
{matches && <details open className="gd-reference"><summary>다른 지역 참고 사례</summary><p className="gd-caution">같은 지원 목적과 관련된 다른 지역의 사업입니다. 이 집단의 연계 후보가 아니며, 새 사업을 기획할 때 참고용으로 보세요.</p>{matches.references?.length ? <ReferenceServiceList items={matches.references.map(r => ({ service: r.service, terms: r.matchedTerms }))}/> : <p>관련된 다른 지역 사업이 없습니다.</p>}</details>}
</EvidencePages>
      </section>

    </>}
  </section></>;
}

// ＋(탭 추가) 버튼이 차지하는 너비(여백 포함)
const ADD_TAB_WIDTH = 44;
const TAB_WIDTHS = { evidence: 196, files: 140, group: 272 }, TAB_MIN_WIDTH = 110;

export default function GroupDashboard({ city, month: preferredMonth, user, onRegion, analysis, onActiveGroup }) {
  const unit = areaUnit(city);
  const [catalog, setCatalog] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  // v2: 후보 우선 규칙(처음 방문 시 1순위 후보 동의 그룹)이 생기기 전에 저장된 탭 기록은 한 번 새로 시작합니다.
  const [stored, setStored, , workspaceStorageFailed] = useDraft(draftKey(user, { city }, 'group-workspace-v2'), emptyTabs);
  const state = restoreWorkspace(stored, city);
  const month = state.month || preferredMonth;
  const setState = update => setStored(old => update(restoreWorkspace(old, city)));
  const searchRef = useRef(null), tabRefs = useRef({});
  const tabsWindowRef = useRef(null), tabsTrackRef = useRef(null);
  const [tabWindowWidth, setTabWindowWidth] = useState(336);
  const [firstTab, setFirstTab] = useState(0);
  const measureTabs = useCallback(() => {
    const window = tabsWindowRef.current;
    // 크롬처럼 마지막 탭 바로 뒤에 ＋ 버튼을 두므로 그 자리를 빼고 탭을 나눕니다.
    if (window) setTabWindowWidth(Math.max(120, window.clientWidth - ADD_TAB_WIDTH));
  }, []);
  useEffect(() => {
    const observer = new ResizeObserver(measureTabs);
    if (tabsWindowRef.current) observer.observe(tabsWindowRef.current);
    measureTabs();
    return () => observer.disconnect();
  }, [measureTabs]);
  // 탭 기본 너비(전체 근거·조사 파일·그룹). 좁은 화면에서도 탭 두 개는 함께 보이도록 영역의 절반까지 줄입니다.
  const half = Math.floor(tabWindowWidth / 2), minTab = Math.min(TAB_MIN_WIDTH, tabWindowWidth);
  const tabWidths = [TAB_WIDTHS.evidence, TAB_WIDTHS.files, ...state.tabs.map(() => TAB_WIDTHS.group)]
    .map(width => Math.max(minTab, Math.min(width, half)));
  const page = tabPage(tabWidths, firstTab, tabWindowWidth);
  const scrollTabs = direction => setFirstTab(direction < 0 ? page.previous : page.end);
  // 종합 현황에서 고른 기준월로 동별 판정을 다시 계산해, 후보 동의 그룹을 먼저 보여 줍니다.
  const statusByDistrict = useMemo(() => {
    if (!analysis) return {};
    const regions = summarizeRegions(analysis.assessment, analysis.geometry, city, month, analysis.months);
    return Object.fromEntries(regions.map(r => [r.name, { status: r.status, count: r.count, metrics: r.rows.filter(x => x.is_risk_signal).map(x => x.metric_label) }]));
  }, [analysis, city, month]);
  const statusOf = g => statusByDistrict[g.district] || (g.code === '1123074' ? statusByDistrict['일원2동'] : undefined);
  // 전체 근거와 조사 파일은 고정 탭입니다. 그룹 탭을 열거나 고르면 브리핑으로 전환됩니다.
  const [workspaceTab, setWorkspaceTab] = useState('group');
  const [summaryStep, setSummaryStep] = useState(1);
  const setShowFiles = value => { setWorkspaceTab(value ? 'files' : 'group'); if (!value) setSummaryStep(1); };
  useEffect(() => {
    let live = true; setLoading(true); setError(''); setCatalog(null);
    api('/groups?' + query({ city, month })).then(result => {
      if (!live) return;
      if (!Array.isArray(result.groups)) throw new Error('집단별 자료 응답 형식을 확인하세요.');
      setCatalog(result);
      setState(old => {
        const valid = availableWorkspace(old, result, month);
        if (valid.initialized || !result.groups.length || valid.month !== month) return valid;
        const first = pickInitialGroup(result.groups, statusOf);
        return openGroup({ ...valid, initialized: true }, { city, code: first.code, district: first.district, age: first.age, sex: first.sex, month });
      });
    }).catch(e => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [city, month, retry]);
  const open = group => { setState(s => openGroup({ ...s, initialized: true }, group)); setShowFiles(false); };
  const openFiles = (focus = false) => { setShowFiles(true); if (focus) setTimeout(() => searchRef.current?.focus(), 0); };
  const close = id => setState(s => closeGroup(s, id));
  const active = state.tabs.find(g => groupKey(g) === state.active);
  const evidenceShown = workspaceTab === 'evidence';
  const filesShown = workspaceTab === 'files' || (!active && !evidenceShown);
  const activeKey = active ? groupKey(active) : '';
  const selectedTabIndex = evidenceShown ? 0 : filesShown ? 1 : state.tabs.findIndex(g => groupKey(g) === activeKey) + 2;
  useEffect(() => {
    setFirstTab(tabPageForSelected(tabWidths, selectedTabIndex, tabWindowWidth).start);
  }, [selectedTabIndex, tabWindowWidth, state.tabs.length]);
  useEffect(() => { onActiveGroup?.(active || null); }, [activeKey, onActiveGroup]);
  const openEvidence = () => setWorkspaceTab('evidence');
  // 위쪽 3단계를 누르면 열린 브리핑의 해당 부분으로 이동합니다. 3단계는 지원 검토 칸을 펼칩니다.
  const goStep = (step) => {
    if (!active) return;
    setSummaryStep(step);
    setWorkspaceTab(step === 3 ? 'evidence' : 'group');
    setTimeout(() => {
      const panel = document.getElementById('panel-' + groupKey(active));
      const target = panel?.querySelector(step === 1 ? '.gd-overview' : step === 2 ? '.gd-context-cards' : '.gd-review');
      if (step === 3 && target) { target.open = true;  }
      if (step === 3) target?.querySelector('select')?.focus();
      const scroller = target?.closest('.main-content');
      if (scroller) scroller.scrollTo({ top: scroller.scrollTop + target.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 12, behavior: 'smooth' });
    }, 0);
  };
  // index -1은 조사 파일 탭입니다. 방향키로 조사 파일과 그룹 탭 사이를 순환합니다.
  const changeTab = (event, index) => {
    const count = state.tabs.length + 2;
    let i = index + 2;
    if (event.key === 'ArrowRight') i = (i + 1) % count;
    else if (event.key === 'ArrowLeft') i = (i - 1 + count) % count;
    else if (event.key === 'Home') i = 0;
    else if (event.key === 'End') i = count - 1;
    else if (event.key === 'Delete' && index >= 0) { close(groupKey(state.tabs[index])); return; }
    else return;
    event.preventDefault();
    setFirstTab(tabPageForSelected(tabWidths, i, tabWindowWidth).start);
    const focusTab = id => requestAnimationFrame(() => tabRefs.current[id]?.focus());
    if (i === 0) { openEvidence(); focusTab('evidence'); return; }
    if (i === 1) { setShowFiles(true); focusTab('files'); return; }
    const id = groupKey(state.tabs[i - 2]); setState(s => ({ ...s, active: id })); setShowFiles(false); focusTab(id);
  };
  return <div className="gd-root">
    {document.getElementById('group-period-slot') && createPortal(<label>기준월<select aria-label="집단 자료 기준월" value={catalog?.months.includes(month) ? month : ''} disabled={loading || !catalog?.months.length} onChange={e => { const selected = e.target.value; setState(s => ({ ...s, month: selected })); }}>
      {!catalog?.months.includes(month) && <option value="">{loading ? '기간 확인 중…' : '제공 자료 없음'}</option>}{catalog?.months.slice().reverse().map(m => <option key={m} value={m}>{m}</option>)}
    </select></label>, document.getElementById('group-period-slot'))}
    {workspaceStorageFailed && <p className="gd-scope-note" role="status">탭 임시 저장에 실패했습니다. 새로고침 시 열린 탭을 복원하지 못할 수 있습니다.</p>}
    {active && active.month !== month && <p className="gd-scope-note">조사 파일 기준월은 {month}, 현재 열린 브리핑은 <b>{active.month} · {groupLabel(active)}</b>입니다.</p>}
    <div className="gd-workspace"><ol className="gd-process" aria-label="브리핑 읽는 순서">{[['변화 발견', '지역과 집단의 변화를 확인합니다.'], ['지역 배경 확인', `가구 구성과 ${unit} 전체의 변화를 봅니다.`], ['지원 서비스 검토', '확인한 필요에 맞는 사업을 검토합니다.']].map(([title, text], i) => <li key={title} className={active && !filesShown && summaryStep === i + 1 && (evidenceShown === (i === 2)) ? 'current' : ''}><button aria-current={active && !filesShown && summaryStep === i + 1 && (evidenceShown === (i === 2)) ? 'step' : undefined} disabled={!active} onClick={() => goStep(i + 1)} title={active ? `${title}로 이동` : '먼저 그룹을 여세요'}><b>{i + 1}</b><span className="gd-step-icon"><Icon name={['discover', 'neighborhood', 'support'][i]} size={34}/></span><div><strong>{title}</strong><span>{text}</span></div></button></li>)}</ol><div className="gd-tabbar"><div className="gd-tabs-window" ref={tabsWindowRef}><div className="gd-tabs-track" ref={tabsTrackRef} role="tablist" aria-label="조사 파일과 관찰 그룹 브리핑 탭"><span className="gd-tabs-label">관찰 그룹 브리핑 <small>· 동·연령·성별 그룹을 열어 보는 탭</small></span>
        <div className={`gd-tab gd-evidence-tab ${evidenceShown ? 'active' : ''}`} hidden={page.start > 0} style={{ width: tabWidths[0] }}><button role="tab" id="tab-evidence" aria-selected={evidenceShown} aria-controls={active ? 'panel-' + groupKey(active) : 'panel-evidence-empty'} tabIndex={evidenceShown ? 0 : -1} ref={el => { tabRefs.current.evidence = el; }} onKeyDown={e => changeTab(e, -2)} onClick={openEvidence}><Icon name="clipboard" size={20}/><span><b>전체 근거와 지원 검토</b></span></button></div>
        <div className={`gd-tab gd-files-tab ${filesShown ? 'active' : ''}`} hidden={page.start > 1 || page.end <= 1} style={{ width: tabWidths[1] }}><button role="tab" id="tab-files" aria-selected={filesShown} aria-controls="panel-files" tabIndex={filesShown ? 0 : -1} ref={el => { tabRefs.current.files = el; }} onKeyDown={e => changeTab(e, -1)} onClick={() => openFiles()}><Icon name="report" size={20} /><span><b>조사 파일</b></span></button></div>
        {state.tabs.map((g, i) => { const id = groupKey(g), selected = !filesShown && !evidenceShown && id === state.active; return <div className={`gd-tab gd-group-tab ${selected ? 'active' : ''}`} key={id} hidden={i + 2 < page.start || i + 2 >= page.end} style={{ width: tabWidths[i + 2] }}><button role="tab" id={'tab-' + id} aria-selected={selected} aria-controls={'panel-' + id} tabIndex={selected ? 0 : -1} ref={el => { tabRefs.current[id] = el; }} onKeyDown={e => changeTab(e, i)} onClick={() => { setState(s => ({ ...s, active: id })); setShowFiles(false); }}><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M3 7V5h6l2 2h10v14H3Z"/></svg><span><b>{groupLabel(g)}</b><small title={g.month}>{g.month.slice(2).replace('-', '.')}</small></span></button><button aria-label={`${groupLabel(g)} ${g.month} 탭 닫기`} onClick={() => close(id)}><Icon name="close" size={18}/></button></div>; })}</div><button className="gd-add" aria-label="조사 파일에서 관찰 그룹 추가" title="조사 파일에서 그룹 추가" onClick={() => openFiles(true)}>＋</button></div><div className="gd-tab-controls"><button className="gd-tab-arrow previous" aria-label="이전 파일 탭 보기" disabled={page.start === 0} onClick={() => scrollTabs(-1)}><Icon name="arrow" size={18}/></button><button className="gd-tab-arrow" aria-label="다음 파일 탭 보기" disabled={page.end >= tabWidths.length} onClick={() => scrollTabs(1)}><Icon name="arrow" size={18}/></button></div></div>
      <section className="gd-case gd-files-panel" role="tabpanel" id="panel-files" aria-labelledby="tab-files" hidden={!filesShown}><Directory catalog={catalog} city={city} month={month} loading={loading} error={error} retry={() => setRetry(n => n + 1)} onOpen={open} state={state} searchRef={searchRef} statusOf={statusOf} /></section>
      {state.tabs.map(g => <GroupCase key={groupKey(g)} group={g} active={groupKey(g) === state.active} shown={!filesShown && !evidenceShown && groupKey(g) === state.active} evidenceShown={evidenceShown && groupKey(g) === state.active} onEvidence={openEvidence} summaryStep={summaryStep} user={user} onRegion={onRegion} candidate={CANDIDATE_ORDER.includes(statusOf(g)?.status) ? statusOf(g) : null} />)}
<section id="panel-evidence-empty" role="tabpanel" aria-labelledby="tab-evidence" className="gd-case" hidden={!evidenceShown || !!active}><h2>전체 근거와 지원 검토</h2><p>조사 파일에서 동·연령·성별 그룹을 선택하면 전체 근거와 지원 검토 내용을 확인할 수 있습니다.</p><button className="primary" onClick={() => openFiles()}>조사 파일에서 그룹 선택</button></section>
    </div>
  </div>;
}
