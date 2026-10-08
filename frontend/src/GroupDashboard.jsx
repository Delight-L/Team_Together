import React, { useEffect, useRef, useState } from 'react';
import { api, query } from './api';
import { Icon } from './components';
import { useDraft } from './useDraft';
import { draftKey } from './draftStore.mjs';
import { groupKey, groupLabel, openGroup, closeGroup, restoreWorkspace, availableWorkspace } from './groupTabs.mjs';
import './group-dashboard.css';

const fmt = (n, digits = 1) => Number.isFinite(n) ? n.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '—';
const pct = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${fmt(n, 2)}%` : '비교 불가';
const emptyTabs = { tabs: [], active: '' };

function LineChart({ points, field = 'mean', label }) {
  const values = points.filter(p => Number.isFinite(p[field]));
  if (!values.length) return <p className="gd-empty">표시할 자료가 없습니다.</p>;
  const max = Math.max(...values.map(p => p[field]), 1);
  const x = i => 32 + i * 370 / Math.max(points.length - 1, 1);
  const y = v => 112 - v / max * 84;
  // 월이 빠진 구간은 선으로 연결하지 않는다.
  const segments = []; let segment = [];
  points.forEach((p, i) => { if (Number.isFinite(p[field])) segment.push([x(i), y(p[field])]); else if (segment.length) { segments.push(segment); segment = []; } });
  if (segment.length) segments.push(segment);
  return <><svg className="gd-line" viewBox="0 0 430 148" role="img" aria-label={label}>
    {[0, max / 2, max].map((v, i) => <g key={i}><line x1="32" x2="405" y1={y(v)} y2={y(v)} stroke="#e2e8f0" /><text x="26" y={y(v) + 4} textAnchor="end">{fmt(v, 0)}</text></g>)}
    {segments.map((s, i) => <polyline key={i} points={s.map(p => p.join(',')).join(' ')} fill="none" stroke="#2563eb" strokeWidth="3" />)}
    {points.map((p, i) => <g key={p.month || p.label}>{Number.isFinite(p[field]) && <circle cx={x(i)} cy={y(p[field])} r="4" fill="#2563eb"><title>{p.month || p.label}: {fmt(p[field], 2)}</title></circle>}{(points.length < 9 || i % 6 === 0 || i === points.length - 1) && <text x={x(i)} y="138" textAnchor="middle">{p.month ? Number(p.month.slice(5)) + '월' : p.label}</text>}</g>)}
  </svg><details className="gd-chart-table"><summary>그래프 값 보기</summary><table><tbody>{points.map(p => <tr key={p.month || p.label}><th>{p.month || p.label}</th><td>{fmt(p[field], 2)}</td></tr>)}</tbody></table></details></>;
}

function Directory({ catalog, loading, error, retry, city, month, onOpen, state, searchRef }) {
  const [search, setSearch] = useState(''), [age, setAge] = useState(''), [sex, setSex] = useState(''), [page, setPage] = useState(0);
  const filtered = (catalog?.groups || []).filter(g => (!age || g.age === age) && (!sex || g.sex === sex) && `${g.district} ${g.age} ${g.sex}`.includes(search.trim()));
  useEffect(() => setPage(0), [search, age, sex, month, city]);
  const pages = Math.max(1, Math.ceil(filtered.length / 7));
  const current = Math.min(page, pages - 1);
  return <div className="gd-directory"><header><h2>관찰 그룹 파일</h2><span>{month}</span></header><p>집단별 유동인구 자료입니다. 위험 순위가 아닙니다.</p>
    <input ref={searchRef} aria-label="동·연령·성별 검색" placeholder="동·연령·성별 검색" value={search} onChange={e => setSearch(e.target.value)} />
    <div className="gd-directory-filters"><select aria-label="연령 필터" value={age} onChange={e => setAge(e.target.value)}><option value="">모든 연령</option>{catalog?.ages.map(a => <option key={a}>{a}</option>)}</select><select aria-label="성별 필터" value={sex} onChange={e => setSex(e.target.value)}><option value="">모든 성별</option>{catalog?.sexes.map(s => <option key={s}>{s}</option>)}</select></div>
    {loading ? <p role="status">DB1 집단 자료를 읽고 있습니다…</p> : error ? <div role="alert" className="gd-error">{error}<button onClick={retry}>다시 연결</button></div> : !filtered.length ? <p className="gd-empty">선택 조건의 자료가 없습니다.{catalog?.months.length > 0 && <span> 제공 기간 {catalog.months[0]} ~ {catalog.months.at(-1)}</span>}</p> : <div className="gd-file-list">{filtered.slice(current * 7, current * 7 + 7).map(g => {
      const group = { city, code: g.code, district: g.district, age: g.age, sex: g.sex, month: g.month }, id = groupKey(group);
      const opened = state.tabs.some(t => groupKey(t) === id);
      return <button key={id} className={state.active === id ? 'selected' : ''} onClick={() => onOpen(group)}><Icon name="report" size={21} /><span><strong>{groupLabel(g)}</strong><small>{g.month} · 구성비 {fmt(g.share)}%</small></span>{opened ? <em>{state.active === id ? '현재 탭' : '열림'}</em> : <span aria-hidden="true">›</span>}</button>;
    })}</div>}
    <footer><span>{filtered.length}개 그룹 · {current + 1}/{pages}</span><button aria-label="이전 그룹 목록" disabled={current === 0} onClick={() => setPage(current - 1)}>‹</button><button aria-label="다음 그룹 목록" disabled={current + 1 >= pages} onClick={() => setPage(current + 1)}>›</button></footer>
    <p className="gd-source">DB1 · 유동인구 연령·성별 집계<br />집단별 통화·문자 신호는 아직 연결되지 않았습니다.</p>
  </div>;
}

function GroupChat({ group, data, messages, setMessages, input, setInput, onServices, active }) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [aiAvailable, setAiAvailable] = useState(false), [mode, setMode] = useState('data');
  const controller = useRef(null), end = useRef(null);
  useEffect(() => { let live = true; api('/groups/config').then(d => live && setAiAvailable(d.aiAvailable)).catch(() => {}); return () => { live = false; }; }, []);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { if (active) end.current?.scrollIntoView({ block: 'nearest' }); }, [messages, active]);
  async function send(event) {
    event.preventDefault(); if (!input.trim() || busy || !data) return;
    const question = input.trim(); setInput(''); setError(''); setBusy(true);
    setMessages(m => [...m, { role: 'user', text: question }]);
    controller.current = new AbortController();
    const signal = controller.current.signal;
    try { const result = await api('/groups/chat', { ...group, question, mode, history: messages.slice(-8).map(m => ({ role: m.role, content: m.text.slice(0, 4000) })) }, { signal }); if (!signal.aborted) setMessages(m => [...m, { role: 'assistant', text: result.answer, source: result.sources[0]?.label }]); }
    catch (e) { if (e.name !== 'AbortError') { setError(e.message); setInput(question); } }
    finally { setBusy(false); }
  }
  return <div className="gd-chat"><header><img src="/brand/bomi-face.png" alt="보미" /><div><strong>보미 · 분석 도우미</strong><small>{groupLabel(group)} · {group.month}</small></div><button onClick={() => { controller.current?.abort(); setMessages([]); setInput(''); setError(''); }}>새 대화</button></header>
    <label className="gd-mode">답변 방식 <select aria-label="답변 방식" value={mode} disabled={busy} onChange={e => setMode(e.target.value)}><option value="data">데이터 근거 안내 · AI 호출 없음</option><option value="ai" disabled={!aiAvailable}>AI 해석{!aiAvailable ? ' · 연결 설정 필요' : ' · 전송 시 외부 AI 사용'}</option></select></label>
    <div className="gd-messages" aria-live="polite">{!messages.length && <div className="gd-welcome"><h3>선택한 집단의 근거를 함께 살펴봐요.</h3><p>유동량의 변화와 자료 범위를 설명하고, 지원 목적에 맞는 사업 탐색을 도와드립니다.</p></div>}{messages.map((m, i) => <article key={i} className={m.role}><small>{m.role === 'user' ? '나' : '보미'}</small><p>{m.text}</p>{m.source && <span>{m.source}</span>}</article>)}{busy && <p>집단별 근거 확인 중…</p>}{error && <p role="alert" className="gd-error">{error}</p>}<div ref={end} /></div>
    <div className="gd-suggestions">{['변화 요약', '요일·시간 해석', '통화 신호가 있나요?'].map(q => <button key={q} onClick={() => setInput(q)}>{q}</button>)}<button onClick={onServices}>사업 검토 열기 →</button></div>
    <form onSubmit={send}><input aria-label="집단에 질문" placeholder="선택한 그룹에 대해 질문하세요" value={input} maxLength={2000} onChange={e => setInput(e.target.value)} /><button className="primary" type="submit" disabled={busy || !data || !input.trim()} aria-label="질문 보내기">↑</button></form>
  </div>;
}

function GroupCase({ group, active, panel, user, onAsk, onRegion }) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const [messages, setMessages] = useState([]), [input, setInput] = useState('');
  const [draft, setDraft, clearDraft, storageFailed] = useDraft(draftKey(user, group, `group-review:${group.code}:${group.age}:${group.sex}`), { note: '', need: '' });
  const [saved, setSaved] = useState(null), [status, setStatus] = useState(''), [saving, setSaving] = useState(false);
  const [matches, setMatches] = useState(null), [serviceError, setServiceError] = useState(''), [searching, setSearching] = useState(false);
  const servicesRef = useRef(null), contentRef = useRef(null), serviceRequest = useRef(null);
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
  const openServices = () => { if (servicesRef.current) { servicesRef.current.open = true; servicesRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } };
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
  return <><section hidden={!active} className="gd-case" role="tabpanel" id={'panel-' + groupKey(group)} aria-label={groupLabel(group)} ref={contentRef}>
    {error ? <div role="alert" className="gd-error">{error}<button onClick={() => { setError(''); setRetry(r => r + 1); }}>다시 연결</button></div> : !row ? <p role="status">집단별 근거를 읽고 있습니다…</p> : <>
      <header className="gd-case-heading"><div><span className="gd-eyebrow">GROUP BRIEFING · {group.month}</span><h2>{groupLabel(group)}</h2></div><span className="gd-badge">유동인구 연결</span></header>
      <h3 className="gd-narrative">{Number.isFinite(row.change_pct) ? `같은 격자에서 전월보다 유동량이 ${fmt(Math.abs(row.change_pct), 2)}% ${row.change_pct >= 0 ? '증가' : '감소'}했습니다.` : '첫 관측월이거나 비교 기준이 없어 변화율을 보류합니다.'}</h3>
      <p className="gd-caption">전월 공통 격자 {fmt(row.matched_points, 0)}개 기준 · 변화의 원인과 지원 필요는 추가 확인이 필요합니다.</p>
      <div className="gd-metrics"><article><span>지역 내 이 집단의 유동량 구성비</span><strong>{fmt(row.share, 2)}<small>%</small></strong><p>같은 동·월의 전체 연령·성별 합계 대비</p></article><article><span>공통 격자당 유동량 · 전월 → 현재</span><strong>{fmt(row.matched_before, 2)} <i>→</i> {fmt(row.matched_after, 2)}</strong><p>{pct(row.change_pct)} · 원자료 값 기준</p></article></div>
      <div className="gd-trend"><header><h3>최근 유동량 추이</h3><span>월별 관측 격자당 평균</span></header><LineChart points={data.series} label={`${groupLabel(group)} 월별 격자당 유동량`} /><p className="gd-caption">이번 달 {fmt(row.points, 0)}개 · 전월 {fmt(row.previous_points, 0)}개 격자. 그래프는 각 월 전체 격자 평균, 위 변화율은 두 달 공통 격자 평균입니다.</p></div>
      <div className="gd-ask"><Icon name="help" size={25} /><div><small>함께 살펴볼 질문</small><strong>이 집단의 활동 변화는 어떤 의미일까요?</strong></div><button className="primary" onClick={() => { setInput('변화 요약'); onAsk(); }}>AI에게 질문하기 →</button></div>
      <details><summary>지역 생활 배경 · Analysis1</summary><p className="gd-caution">동 전체의 지역 유형이며 이 집단의 가구·건강 상태를 뜻하지 않습니다. 월별 유동자료와 기준기간이 다릅니다.</p>{structure ? <><h3>{structure.cluster_type}</h3><p>1인가구 비중 {fmt(structure.payload.hh_1_ratio * 100)}% · 65세 이상 주민 비중 {fmt(structure.payload.resident_ratio_65_plus * 100)}%</p><small>DB1 · {structure.source_file} · 기간은 출처 파일 기준</small></> : <p>연결된 지역 유형 자료가 없습니다.</p>}</details>
      <details><summary>같은 동의 연령·성별 유동량 구성</summary><p>선택한 동의 유동량 구성입니다. 주민등록 인구나 가구 유형을 의미하지 않습니다.</p><div className="gd-composition">{data.composition.map(g => <div key={g.age + g.sex} className={g.age === group.age && g.sex === group.sex ? 'selected' : ''}><span>{g.age} · {g.sex}</span><div><i style={{ width: `${g.share || 0}%` }} /></div><b>{fmt(g.share, 2)}%</b></div>)}</div></details>
      <details><summary>동 전체 참고 근거 · Analysis2</summary><p className="gd-caution">아래는 동 전체 통화·문자·이동 결과입니다. {group.age} {group.sex}의 신호가 아닙니다. 집단별 통신 원본 재집계가 필요합니다.</p>{regionalRows.length ? <table><thead><tr><th>지표</th><th>전월 변화</th><th>동 전체 판정</th></tr></thead><tbody>{regionalRows.map(r => <tr key={r.metric_label}><th>{r.metric_label}</th><td>{pct(r.change_pct)}</td><td>{r.is_risk_signal ? '변화 후보' : r.has_enough_history ? '기준 미해당' : '비교 보류'}</td></tr>)}</tbody></table> : <p>같은 동·월의 Analysis2 자료가 없습니다.</p>}<p>판정은 단순 감소율이 아니라 공통 변화 보정·과거 이력과 지표 묶음의 동시 신호에 따릅니다.</p><button className="text-button" onClick={() => onRegion(group)}>동 전체 분석 화면으로 →</button></details>
      <details><summary>같은 연령·성별의 지역별 변화 비교</summary><p>각 동의 전월 공통 격자 기준 변화율입니다. 위험 순위나 개인 이동 경로가 아닙니다.</p><table><thead><tr><th>행정동</th><th>유동량 변화</th><th>공통 격자</th></tr></thead><tbody>{data.peers.map(p => <tr key={p.code}><th>{p.district}{p.code === group.code ? ' · 선택' : ''}</th><td>{pct(p.change_pct)}</td><td>{fmt(p.matched_points, 0)}개</td></tr>)}</tbody></table></details>
      <details><summary>요일·시간대 활동 · 지역 전체 별도 집계</summary><p className="gd-caution">이 집단의 요일·시간대가 아닙니다. 지역 전체의 활동으로 서비스 운영 접점을 검토합니다.</p><div className="gd-activity"><div><h4>요일별 활동 <small>요일 평균=100</small></h4>{data.activity.weekdays?.map(d => <div className="gd-day" key={d.label}><span>{d.label}</span><i style={{ width: `${Math.min((d.index || 0) / 2, 100)}%` }} /><b>{fmt(d.index)}</b></div>) || <p>요일 자료 없음</p>}</div><div><h4>시간대 활동 <small>최대 시간대=100</small></h4>{data.activity.hours ? <LineChart points={data.activity.hours} field="index" label="지역 전체 시간대 활동 지수" /> : <p>시간대 자료 없음</p>}</div></div></details>
      <details ref={servicesRef} className="gd-review"><summary>지원 필요 확인 · 메모와 사업 검토</summary><p>유동량만으로 지원 필요나 이용 자격을 확정하지 않습니다. 검토 목적을 선택하고 실제 사업의 조건을 확인하세요.</p><label>검토할 지원 목적<select value={need} disabled={saving} onChange={e => { changeDraft({ need: e.target.value }); serviceRequest.current?.abort(); setMatches(null); setServiceError(''); }}><option value="">선택하세요</option>{['관계·사회참여', '안부·상담', '생활·경제'].map(n => <option key={n}>{n}</option>)}</select></label><label>이 집단의 검토 메모<textarea aria-label="집단 검토 메모" disabled={saving} rows="3" maxLength={3000} placeholder="관측 사실, 추가 확인 사항, 실제로 확인한 필요를 구분해서 기록하세요." value={note} onChange={e => changeDraft({ note: e.target.value })} /></label><div className="gd-review-actions"><button className="secondary" onClick={save} disabled={saving}>{saving ? '저장 중…' : '검토 메모 저장'}</button><button className="primary" disabled={!need || searching} onClick={findServices}>{searching ? 'DB2 조회 중…' : '조건 확인할 사업 찾기'}</button></div><p role="status">{storageFailed ? "임시 저장에 실패했습니다. 내용을 복사하거나 저장해 주세요." : status || (saved?.updatedAt ? `마지막 저장 ${saved.updatedAt.slice(0, 16).replace('T', ' ')}` : '')}</p>{serviceError && <p role="alert" className="gd-error">{serviceError}</p>}{matches && <div className="gd-services"><p>{matches.items.length}개 관련 사업 · {matches.note}</p>{matches.items.length === 0 && <p>선택 목적의 관련어가 일치하는 사업이 없습니다. 목적을 바꾸거나 기존 사업 매칭 검토 메뉴에서 확인하세요.</p>}{matches.items.map(({ service: s, reason, qualification }) => <article key={s.service_id}><h4>{s.name}</h4><p>{reason}</p><dl><dt>대상</dt><dd>{s.target_text || '원문 확인 필요'}</dd><dt>선정 조건</dt><dd>{s.eligibility_text || '기관 확인 필요'}</dd><dt>신청 방법</dt><dd>{s.application_text || '기관 확인 필요'}</dd></dl><small>{qualification}</small>{/^https?:\/\//i.test(s.source_url || '') && <a href={s.source_url} target="_blank" rel="noreferrer">공식 안내 확인 ↗</a>}<small>정보 확인일 {s.detail_checked_at || '미확인'}</small></article>)}</div>}</details>
      <details><summary>자료 출처·범위와 계산 방법</summary><p>{data.source} · 기준월 {group.month}</p><p>{data.note}</p><p>{data.mapping}</p><p>구성비 = 집단 유동량 / 동 전체 유동량. 격자당 평균 = 유동량 합 / 관측 격자 수. 전월 변화율 = (공통 격자의 현재 평균 / 전월 평균 − 1) × 100. 분모 0·전월 누락은 계산하지 않습니다.</p><p>집단별 통화·문자·이동 신호는 미연결 상태입니다. 기존 Analysis1 자료와 집계 범위가 다를 수 있어 값을 혼합하지 않습니다.</p><small>자료 버전 {data.runId.slice(0, 16)}</small></details>
      <footer className="gd-case-footer"><span>집단 집계자료이며 개인의 고립 판정이 아닙니다.</span><button className="primary" onClick={openServices}>지원 필요·사업 검토 시작 →</button></footer>
    </>}
  </section><aside hidden={!active || panel !== 'chat'} className="gd-chat-slot"><GroupChat group={group} data={data} messages={messages} setMessages={setMessages} input={input} setInput={setInput} onServices={openServices} active={active && panel === 'chat'} /></aside></>;
}

export default function GroupDashboard({ city, month: preferredMonth, user, onRegion, chatOpen, setChatOpen }) {
  const [catalog, setCatalog] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  const [stored, setStored, , workspaceStorageFailed] = useDraft(draftKey(user, { city }, 'group-workspace'), emptyTabs);
  const state = restoreWorkspace(stored, city);
  const month = state.month || preferredMonth;
  const setState = update => setStored(old => update(restoreWorkspace(old, city)));
  const searchRef = useRef(null), tabRefs = useRef({});
  const panel = chatOpen ? 'chat' : 'files';
  useEffect(() => {
    let live = true; setLoading(true); setError(''); setCatalog(null);
    api('/groups?' + query({ city, month })).then(result => {
      if (!live) return;
      if (!Array.isArray(result.groups)) throw new Error('집단별 자료 응답 형식을 확인하세요.');
      setCatalog(result);
      setState(old => {
        const valid = availableWorkspace(old, result, month);
        if (valid.initialized || !result.groups.length || valid.month !== month) return valid;
        const first = result.groups.find(g => g.district === '역삼2동' && g.age === '30대' && g.sex === '남성') || result.groups[0];
        return openGroup({ ...valid, initialized: true }, { city, code: first.code, district: first.district, age: first.age, sex: first.sex, month });
      });
    }).catch(e => live && setError(e.message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [city, month, retry]);
  const open = group => setState(s => openGroup({ ...s, initialized: true }, group));
  const close = id => setState(s => closeGroup(s, id));
  const active = state.tabs.find(g => groupKey(g) === state.active);
  const changeTab = (event, index) => {
    let i = index;
    if (event.key === 'ArrowRight') i = (index + 1) % state.tabs.length;
    else if (event.key === 'ArrowLeft') i = (index - 1 + state.tabs.length) % state.tabs.length;
    else if (event.key === 'Home') i = 0;
    else if (event.key === 'End') i = state.tabs.length - 1;
    else if (event.key === 'Delete') { close(groupKey(state.tabs[index])); return; }
    else return;
    event.preventDefault(); const id = groupKey(state.tabs[i]); setState(s => ({ ...s, active: id })); tabRefs.current[id]?.focus();
  };
  return <div className="gd-root">
    <div className="gd-workspace-tools"><p>열어 둔 탭과 기준월은 이 브라우저 탭에서 복원됩니다.</p><label>집단 자료 기준월<select aria-label="집단 자료 기준월" value={catalog?.months.includes(month) ? month : ''} disabled={loading || !catalog?.months.length} onChange={e => { const selected = e.target.value; setState(s => ({ ...s, month: selected })); }}>
      {!catalog?.months.includes(month) && <option value="">{loading ? '기간 확인 중…' : '제공 자료 없음'}</option>}{catalog?.months.slice().reverse().map(m => <option key={m}>{m}</option>)}
    </select></label></div>
    {workspaceStorageFailed && <p className="gd-scope-note" role="status">탭 임시 저장에 실패했습니다. 새로고침 시 열린 탭을 복원하지 못할 수 있습니다.</p>}
    {active && active.month !== month && <p className="gd-scope-note">조사 파일 기준월은 {month}, 현재 열린 브리핑은 <b>{active.month} · {groupLabel(active)}</b>입니다.</p>}
    <div className="gd-stats"><article><span>연결된 관찰 그룹</span><strong>{loading ? '…' : catalog?.groups.length ?? '—'}<small>개</small></strong><p>{month} · 위험 후보 수가 아닙니다</p></article><article><span>열어 둔 브리핑</span><strong>{state.tabs.length}<small>개</small></strong><p>동 · 연령대 · 성별 · 기준월</p></article><article><span>집단별 통신 신호</span><strong className="gd-unavailable">미연결</strong><p>동 전체 결과는 참고 근거로 구분</p></article></div>
    <div className="gd-workspace"><div className="gd-tabbar" role="tablist" aria-label="관찰 그룹 브리핑 탭">{state.tabs.map((g, i) => { const id = groupKey(g); return <div className={`gd-tab ${id === state.active ? 'active' : ''}`} key={id}><button role="tab" id={'tab-' + id} aria-selected={id === state.active} aria-controls={'panel-' + id} tabIndex={id === state.active ? 0 : -1} ref={el => { tabRefs.current[id] = el; }} onKeyDown={e => changeTab(e, i)} onClick={() => setState(s => ({ ...s, active: id }))}><Icon name="report" size={18} /><span><b>{groupLabel(g)}</b><small>{g.month}</small></span></button><button aria-label={`${groupLabel(g)} ${g.month} 탭 닫기`} onClick={() => close(id)}>×</button></div>; })}<button className="gd-add" aria-label="관찰 그룹 탭 추가" onClick={() => { setChatOpen(false); setTimeout(() => searchRef.current?.focus(), 0); }}>＋</button></div>
      <div className="gd-panel-switch" role="group" aria-label="오른쪽 패널 전환"><button className={panel === 'files' ? 'active' : ''} aria-pressed={panel === 'files'} onClick={() => setChatOpen(false)}>조사 파일</button><button className={panel === 'chat' ? 'active' : ''} aria-pressed={panel === 'chat'} onClick={() => setChatOpen(true)}>AI 도우미</button></div>
      {!state.tabs.length && <section className="gd-case gd-empty"><h2>살펴볼 그룹을 선택하세요</h2><p>오른쪽 조사 파일에서 동·연령·성별을 선택하면 브리핑 탭이 열립니다.</p>{error && <p role="alert">{error}</p>}<button className="primary" onClick={() => setChatOpen(false)}>조사 파일 보기</button></section>}
      {state.tabs.map(g => <GroupCase key={groupKey(g)} group={g} active={groupKey(g) === state.active} panel={panel} user={user} onAsk={() => setChatOpen(true)} onRegion={onRegion} />)}
      <aside className="gd-directory-slot" hidden={panel !== 'files'}><Directory catalog={catalog} city={city} month={month} loading={loading} error={error} retry={() => setRetry(n => n + 1)} onOpen={open} state={state} searchRef={searchRef} /></aside>
      {!active && panel === 'chat' && <aside className="gd-chat-slot gd-empty">조사 파일에서 먼저 그룹을 선택하세요.<button onClick={() => setChatOpen(false)}>조사 파일로</button></aside>}
    </div>
  </div>;
}
