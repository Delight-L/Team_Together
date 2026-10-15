import React, { useEffect, useRef, useState } from 'react';
import { api, query, number } from './api';
import { useDraft } from './useDraft';
import { draftKey } from './draftStore.mjs';
import { reportChecks } from './experienceLogic.mjs';
import { personName } from './personas.mjs';
import { showToast } from './toast';
import { areaUnit } from './regionalPresentation.mjs';
import { useTransientMessage } from './useTransientMessage';

// 데이터 기준 창: 지역 분석·데이터 관리의 «데이터 기준 보기»에서 엽니다.
export function DataDialog({ onClose, data, context, rows, user }) {
  const dialog = useRef(null);
  useEffect(() => { const el = dialog.current; el.showModal(); return () => el.close(); }, []);
  return <dialog ref={dialog} className="support-dialog" aria-labelledby="data-dialog-title" onClose={() => { if (!dialog.current?.open) onClose(); }}>
    <header className="experience-toolbar"><h2 id="data-dialog-title">데이터 기준</h2><button className="secondary" onClick={onClose} aria-label="데이터 기준 닫기">닫기</button></header>
    <DataSummary data={data} context={context} rows={rows} user={user} expanded />
  </dialog>;
}

// 일반 사용자에게는 쉬운 설명만, 관리자에게는 분석 버전 같은 기술 정보까지 보여 줍니다.
export function DataSummary({ data, context, rows, user, expanded = false }) {
  const previous = data.months.filter(m => m < context.month).at(-1);
  return <details open={expanded || undefined} className="card data-summary"><summary>데이터 기준 · {context.month}</summary>
    <dl><dt>분석 자료</dt><dd>{areaUnit(context.city)}별 통화·문자·평일 이동·휴일 이동 분석{user?.admin ? ` (${data.source})` : ''}</dd>
      <dt>제공 기간</dt><dd>{data.months[0] || '자료 없음'} ~ {data.months.at(-1) || '자료 없음'}</dd>
      <dt>선택 지역 자료</dt><dd>{context.district ? `${context.district} · ${rows.length}개 지표` : `${areaUnit(context.city)}을 선택하면 제공 범위를 확인할 수 있습니다.`}</dd>
      <dt>누락·이력 부족</dt><dd>과거 이력 부족 {rows.filter(r => !r.has_enough_history).length}개 · 전월 변화값 누락 {rows.filter(r => !Number.isFinite(r.change_pct)).length}개</dd></dl>
    <h3>확인 후보는 어떻게 정하나요?</h3>
    <p>시·군·구 전체의 공통 변화를 뺀 뒤, 과거 흐름과 얼마나 다른지(평소 대비 차이)를 살펴봅니다. 전화·문자 또는 평일·휴일 이동의 값이 모두 -2 이하일 때 후보로 표시하며, 최소 12회 과거 이력이 필요합니다.</p>
    <p className="hint">지역 집계 결과이며 개인의 고립 여부를 판정하지 않습니다. 춘천시의 실제 분석 결과는 아직 연결되지 않았습니다.</p>
    <h3>지역 배경 지표는 무엇을 뜻하나요?</h3>
    <p>새 지역 유형 분석은 65세 이상 등록인구 중 독거노인 비율을 사용합니다. 2025년 독거노인 수를 2025년 4분기 65세 이상 등록인구로 나눈 값이며, 월별 변화나 개인의 고립 여부를 뜻하지 않습니다.</p>
    <p className="hint">연간 지역 배경자료의 공개 시점은 확인되지 않았습니다. 과거 월 당시 알려진 정보로 해석하지 않으며, 60세 이상 집단과 통계의 연령 범위도 다릅니다.</p>
    {user?.admin && <details className="secondary-details"><summary>분석 버전·갱신 정보 (관리자)</summary><dl>
      <dt>분석 규칙</dt><dd>{data.runs?.[0]?.rule_version || '분석 버전 미확인'} · 공통 변화 제거 후 Robust Z</dd>
      <dt>이전 분석월</dt><dd>{previous || '이전 분석월 없음'} · 신규/연속 후보 비교 기준입니다. 전월 변화율은 원자료에 계산된 값을 사용합니다.</dd>
      <dt>전체 근거 행</dt><dd>{data.assessment.length.toLocaleString()}개</dd>
      <dt>결과 버전</dt><dd>{data.runId}</dd>
      <dt>분석 파일 변경</dt><dd>{data.analysisFileModifiedAt || '미확인'} · 원천자료 갱신일은 별도 확인이 필요합니다.</dd>
      <dt>연결 확인</dt><dd>{data.dataCheckedAt || '미확인'}</dd>
    </dl></details>}
  </details>;
}

const blank = { version: 0, checks: {}, assignee: '', due: '', note: '', followup: '', status: '확인 예정', history: [] };
export function ReviewWorkspace({ context, onView, seed, user, onSaved, compact = false }) {
  const [localDraft, setLocalDraft, clearLocalDraft, storageFailed] = useDraft(draftKey(user, context, 'review'), null);
  const [record, setRecord] = useState(blank), [error, setError] = useState(''), [busy, setBusy] = useState(true);
  const [notice, setNotice] = useTransientMessage();
  const [timeline, setTimeline] = useState([]), [timelineLoaded, setTimelineLoaded] = useState(false), [section, setSection] = useState('review');
  async function loadTimeline() { try { setTimeline((await api('/experience/history?' + query(context))).items); setTimelineLoaded(true); } catch (e) { setError(e.message); } }
  const update = (key, value) => { const next = { ...record, [key]: value }; setRecord(next); setLocalDraft({ record: next, seedId: localDraft?.seedId }); setNotice('작성 내용을 임시 보관했습니다.'); };
  async function reload() {
    if (localDraft && !window.confirm('작성 중인 내용을 버리고 서버에 저장된 기록을 불러올까요?')) return;
    setBusy(true); setError('');
    try { setRecord({ ...blank, ...await api('/experience?' + query(context)) }); clearLocalDraft(); setNotice('최신 기록을 불러왔습니다.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  useEffect(() => {
    let active = true;
    api('/experience?' + query(context)).then(r => {
      if (!active) return;
      const restored = localDraft?.record;
      const imported = seed && seed.id !== localDraft?.seedId && ['city','district','month'].every(k => seed.context[k] === context[k]);
      const next = { ...blank, ...(restored || r) };
      if (imported) next.note = [next.note, seed.text].filter(Boolean).join('\n\n').slice(0, 2000);
      setRecord(next);
      if (imported) setLocalDraft({ record: next, seedId: seed.id });
      if (restored) setNotice(restored.version !== r.version
        ? '작성 중인 내용을 복원했습니다. 서버 기록이 변경되어 바로 저장할 수 없습니다. 작성 내용을 복사해 둔 뒤 최신 기록을 불러오세요.'
        : '작성 중인 내용을 복원했습니다.');
      else if (imported) setNotice('챗봇 답변을 검토 의견에 가져왔습니다. 내용을 검토한 뒤 저장하세요.');
    }).catch(e => { if (active) { if (localDraft?.record) setRecord(localDraft.record); setError(e.message); } })
      .finally(() => active && setBusy(false));
    return () => { active = false; };
  }, []);
  // 업무를 새 분석으로 다시 시작하면 이전 회차 기록은 읽기 전용으로 남습니다.
  const rounds = record.previous_rounds || [];
  function copyRound(round) {
    const filled = record.note || record.followup || record.assignee;
    if (filled && !window.confirm(`${round.round}회차 내용으로 지금 작성 중인 내용을 바꿀까요?`)) return;
    const next = { ...record, checks: { ...(round.checks || {}) }, assignee: round.assignee || '', due: round.due || '',
      note: round.note || '', followup: round.followup || '', status: round.status || '확인 예정' };
    setRecord(next); setLocalDraft({ record: next, seedId: localDraft?.seedId });
    setNotice(`${round.round}회차 내용을 가져왔습니다. 지금 근거에 맞게 고친 뒤 저장하세요.`);
  }
  async function save() { setBusy(true); setError(''); try { setRecord({ ...blank, ...await api('/experience', { ...record, ...context }) }); clearLocalDraft(); onSaved?.(); setNotice(''); showToast(`${context.district} · ${context.month} · 검토·후속 조치 기록을 저장했어요.`); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  return <section className={`${compact ? 'inline-review-body' : 'card info-card'} review-workspace`}>
    <div className="workspace-heading"><div><h2>검토·후속 조치</h2><p>{context.district} · {context.month}{rounds.length > 0 && ` · ${rounds.length + 1}회차`} <span className="status-caption">{record.status}</span></p></div>
      <button className="text-button" onClick={() => onView(compact ? 'records' : 'compare')}>{compact ? '업무 기록·후속 조치로 →' : '월별 변화 비교 →'}</button></div>
    <p className="hint">{storageFailed ? '브라우저 임시 보관에 실패했습니다. 새로고침 전에 기록을 저장하세요.' : '작성 중인 내용은 이 탭에 임시 보관됩니다. 로그아웃 전에 저장해 주세요.'}</p>
    {!compact && <div className="section-switch" role="group" aria-label="작성 구역">
      <button aria-pressed={section === 'review'} onClick={() => setSection('review')}>검토 기록</button>
      <button aria-pressed={section === 'followup'} onClick={() => setSection('followup')}>후속 조치</button>
    </div>}
    <div className="review-section" hidden={section !== 'review'}>
      <h3>변화의 근거를 확인하고 의견을 남겨 주세요.</h3>
      <fieldset disabled={busy}><legend>확인한 사항만 체크하세요</legend>{[['season', '계절에 따른 변화 확인'], ['event', '지역 행사·휴일 영향 확인'], ['definition', '집계 기준 변경 확인'], ['source', '분석 출처·기간 확인']].map(([key, label]) => <label className="confirmation" key={key}><input type="checkbox" checked={!!record.checks[key]} onChange={e => update('checks', { ...record.checks, [key]: e.target.checked })} />{label}</label>)}</fieldset>
      <label>검토 의견·인계 내용<textarea rows={5} maxLength={2000} disabled={busy} value={record.note} onChange={e => update('note', e.target.value)} placeholder="변화의 원인으로 살펴본 내용과 추가로 확인할 사항을 적어 주세요." /></label>
    </div>
    <div className="review-section" hidden={compact || section !== 'followup'}>
      <h3>누가, 언제, 무엇을 확인할지 정리해 주세요.</h3>
      <div className="report-form"><label>담당자·인계 대상<input maxLength={80} disabled={busy} value={record.assignee} onChange={e => update('assignee', e.target.value)} /></label><label>확인 기한<input type="date" disabled={busy} value={record.due} onChange={e => update('due', e.target.value)} /></label>
        <label className="full">후속 조치 상태<select disabled={busy} value={record.status} onChange={e => update('status', e.target.value)}>{['확인 예정', '기관 문의 중', '조치 진행', '후속 확인 완료'].map(s => <option key={s}>{s}</option>)}</select></label>
        <label className="full">실제 조치·다음 확인 내용<textarea rows={5} maxLength={2000} disabled={busy} value={record.followup} onChange={e => update('followup', e.target.value)} placeholder="기관 문의 결과와 다음에 확인할 내용을 적어 주세요." /></label></div>
    </div>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p className="hint" role="status">{notice}</p>}
    <div className="form-actions"><button className="primary" disabled={busy} onClick={save}>{busy ? '처리 중…' : compact ? '검토 의견 저장' : '검토·후속 조치 저장'}</button><span className="hint">{compact ? '업무 기록의 검토 의견과 같은 저장본입니다. 기존 후속 조치는 유지합니다.' : '두 구역의 내용을 함께 저장합니다.'}</span></div>
    {rounds.length > 0 && <details className="secondary-details"><summary>이전 회차 기록 {rounds.length}건</summary>
      <p className="hint">업무를 새 분석으로 다시 시작하기 전의 기록입니다. 고칠 수 없으며, 필요하면 지금 회차로 가져와 고친 뒤 저장하세요.</p>
      {[...rounds].reverse().map(r => <article className="service-card" key={r.round}>
        <strong>{r.round}회차 · {(r.ended_at || '').slice(0, 16).replace('T', ' ')} 종료 · {r.status}</strong>
        <p>담당자 {personName(r.assignee) || '미지정'} · 기한 {r.due || '미지정'}</p><p>{r.note}</p><p>{r.followup}</p>
        <button className="secondary" disabled={busy} onClick={() => copyRound(r)}>이 내용을 지금 회차로 가져오기</button></article>)}
    </details>}
    <details className="secondary-details"><summary>이전 기록·다시 불러오기</summary>
      <p className="hint">저장한 기록은 같은 지역 담당자와 공유합니다.</p>
      <button className="secondary" disabled={busy} onClick={reload}>최신 기록 다시 불러오기</button>
      <details><summary>변경 이력 {record.history.length}건</summary>{record.history.length === 0 && <p className="hint">아직 저장된 변경 이력이 없습니다.</p>}{[...record.history].reverse().map((h, i) => <article className="service-card" key={i}><strong>{h.at} · {personName(h.actor)} · {h.status}</strong><p>담당자 {personName(h.assignee) || '미지정'} · 기한 {h.due || '미지정'}</p><p>{h.note}</p><p>{h.followup}</p></article>)}</details>
      <details><summary>다른 기준월의 후속 조치</summary><button className="secondary" onClick={loadTimeline}>월별 기록 불러오기</button>{timelineLoaded && !timeline.length && <p className="hint">저장된 월별 기록이 없습니다.</p>}{timeline.map(item => <article className="service-card" key={item.month}><b>{item.month} · {item.record.status}</b><p>담당자 {personName(item.record.assignee) || '미지정'} · 기한 {item.record.due || '미지정'}</p><p>{item.record.followup || '후속 조치 내용 미입력'}</p></article>)}</details>
    </details>
  </section>;
}

// 비교 차트 계열 색상입니다. 동을 빼도 남은 동의 색은 바뀌지 않습니다(색은 순위가 아니라 지역을 따릅니다).
const SERIES = ['#2563eb', '#e8590c', '#0f9d76', '#9333ea'];

function CompareChart({ period, series, metric }) {
  const box = useRef(null), [width, setWidth] = useState(720), [hover, setHover] = useState(null);
  useEffect(() => {
    const el = box.current; if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(200, Math.round(entry.contentRect.width))));
    observer.observe(el); return () => observer.disconnect();
  }, []);
  const values = series.flatMap(s => s.values).filter(Number.isFinite);
  // 실제 표시 폭을 viewBox로 써서 화면이 넓어져도 글자와 선 두께가 커지지 않게 합니다.
  const height = 280, left = 48, right = width < 480 ? 64 : 92, top = 16, bottom = 34;
  let low = Math.min(0, ...values), high = Math.max(0, ...values);
  const pad = (high - low || 1) * .08; low -= pad; high += pad;
  const plotWidth = width - left - right, gap = plotWidth / Math.max(1, period.length - 1);
  const x = i => left + i * gap;
  const y = v => top + (high - v) * (height - top - bottom) / (high - low);
  // 눈금은 0%를 우선하고, 화면에서 18px보다 가까운 눈금은 생략합니다.
  const ticks = [0, high - pad, low + pad].reduce((kept, v) => kept.every(o => Math.abs(y(o) - y(v)) >= 18) ? [...kept, v] : kept, []);
  // 선 끝의 지역 이름이 겹치지 않도록 위에서부터 14px 간격으로 밀어 냅니다.
  const endLabels = series.map(s => { const i = s.values.findLastIndex(Number.isFinite); return i < 0 ? null : { name: s.name, x: x(i) + 10, y: y(s.values[i]) + 4 }; }).filter(Boolean).sort((p, q) => p.y - q.y);
  endLabels.forEach((l, i) => { if (i && l.y - endLabels[i - 1].y < 14) l.y = endLabels[i - 1].y + 14; });
  const step = Math.ceil(period.length / Math.max(2, Math.floor(plotWidth / 64)));
  const onMove = e => { const i = Math.round((e.clientX - e.currentTarget.getBoundingClientRect().left - left) / gap); setHover(i >= 0 && i < period.length ? i : null); };
  const tipLeft = hover === null ? 0 : Math.min(Math.max(x(hover) + 12, 0), width - 190);
  return <div ref={box} className="compare-chart">{!values.length ? <p className="empty">선택한 기간에 표시할 자료가 없습니다.</p> : <>
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${series.map(s => s.name).join(', ')} ${metric} 전월 변화율 비교`} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      {ticks.map(v => <g key={v}><line x1={left} x2={width - right} y1={y(v)} y2={y(v)} className={Math.abs(v) < 1e-9 ? 'zero' : 'grid'} /><text x={left - 8} y={y(v) + 4} textAnchor="end">{number(v)}%</text></g>)}
      {period.map((m, i) => (i % step === 0 || i === period.length - 1) && <text key={m} x={x(i)} y={height - 10} textAnchor="middle">{m.slice(2).replace('-', '.')}</text>)}
      {hover !== null && <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={top} y2={height - bottom} />}
      {series.map(s => {
        const segments = []; let seg = [];
        s.values.forEach((v, i) => { if (Number.isFinite(v)) seg.push(`${x(i)},${y(v)}`); else if (seg.length) { segments.push(seg); seg = []; } });
        if (seg.length) segments.push(seg);
        return <g key={s.name}>
          {segments.map((p, i) => <polyline key={i} points={p.join(' ')} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" />)}
          {s.values.map((v, i) => Number.isFinite(v) && <circle key={i} cx={x(i)} cy={y(v)} r={hover === i ? 5 : 4} fill={s.color} stroke="#fff" strokeWidth="2" />)}
        </g>;
      })}
      {endLabels.map(l => <text key={l.name} className="series-label" x={l.x} y={l.y}>{l.name}</text>)}
    </svg>
    {hover !== null && <div className="compare-tooltip" style={{ left: tipLeft }}><b>{period[hover]}</b>{series.map(s => <span key={s.name}><i style={{ background: s.color }} />{s.name}<em>{Number.isFinite(s.values[hover]) ? `${number(s.values[hover])}%` : '자료 없음'}</em></span>)}</div>}
  </>}</div>;
}

export function Comparison({ data, context }) {
  const unit = areaUnit(context.city);
  const units = data.geometry[context.city]?.units || [];
  const [selected, setSelected] = useState(context.district ? [context.district] : units.slice(0, 2).map(u => u.n));
  const colorOf = useRef({});
  // 새로 추가된 동에만 비어 있는 색을 배정합니다.
  for (const n of Object.keys(colorOf.current)) if (!selected.includes(n)) delete colorOf.current[n];
  for (const n of selected) if (!colorOf.current[n]) colorOf.current[n] = SERIES.find(c => !Object.values(colorOf.current).includes(c));
  const metrics = [...new Set(data.assessment.map(r => r.metric_label))];
  const recentStart = end => {
    const [year, month] = end.split('-').map(Number);
    const date = new Date(Date.UTC(year, month - 6, 1));
    const start = date.toISOString().slice(0, 7);
    return data.months.find(m => m >= start && m <= end) || end;
  };
  const [metric, setMetric] = useState(metrics[0] || ''), [from, setFrom] = useState(() => context.month ? recentStart(context.month) : ''), [to, setTo] = useState(context.month);
  const rows = context.city === '강남구' ? data.assessment.filter(r => r['기준연월'] >= from && r['기준연월'] <= to) : [];
  const chosenRows = rows.filter(r => selected.includes(r['행정동명']) && r.metric_label === metric);
  const period = data.months.filter(m => m >= from && m <= to);
  const series = selected.map(n => ({ name: n, color: colorOf.current[n], values: period.map(month => chosenRows.find(r => r['행정동명'] === n && r['기준연월'] === month)?.change_pct ?? null) }));
  const addable = units.filter(u => !selected.includes(u.n));
  return <section className="card info-card comparison-workspace"><h2>지역·기간 비교</h2><p className="hint">최대 4개 {unit}의 전월 변화율을 한 그래프에서 같은 눈금으로 비교합니다.</p>
    <div className="comparison-filters"><label>지표<select aria-label="지표" value={metric} onChange={e => setMetric(e.target.value)}>{metrics.map(m => <option key={m}>{m}</option>)}</select></label><label>시작월<select aria-label="시작월" value={from} onChange={e => setFrom(e.target.value)}>{data.months.map(m => <option key={m}>{m}</option>)}</select></label><label>종료월<select aria-label="종료월" value={to} onChange={e => setTo(e.target.value)}>{data.months.map(m => <option key={m}>{m}</option>)}</select></label>
      <button className="secondary" disabled={!to} onClick={() => setFrom(recentStart(to))}>최근 6개월</button></div>
    <div className="comparison-selection" aria-label="비교할 지역">{selected.map(n => <button className="region-chip" key={n} aria-label={`${n} 비교에서 제외`} onClick={() => setSelected(s => s.filter(v => v !== n))}><i className="legend-swatch" style={{ background: colorOf.current[n] }} aria-hidden="true" />{n}<span aria-hidden="true">×</span></button>)}
      <select className="region-add" aria-label={`비교할 ${unit} 추가`} value="" disabled={selected.length >= 4} onChange={e => e.target.value && setSelected(s => [...s, e.target.value])}><option value="">{selected.length >= 4 ? `최대 4개 ${unit}` : `＋ ${unit} 추가`}</option>{addable.map(u => <option key={u.n}>{u.n}</option>)}</select>
      <span className="hint">{selected.length}/4개 {unit}</span></div>
    {from > to ? <p className="error" role="alert">시작월은 종료월보다 늦을 수 없습니다.</p> : !selected.length ? <p className="empty">＋ {unit} 추가에서 비교할 지역을 선택하세요.</p> : <>
      <article className="comparison-chart"><h3>{metric} · 전월 변화율</h3><p className="hint">{from} ~ {to} · 0% 선 위는 증가, 아래는 감소입니다.</p><CompareChart period={period} series={series} metric={metric} /></article>
      <details className="secondary-details"><summary>월별 상세 수치 보기</summary>{chosenRows.length ? <div className="table-scroll"><table><thead><tr><th>지역</th><th>기준월</th><th>전월 변화율</th><th>판단</th></tr></thead><tbody>{[...chosenRows].sort((a,b) => a['행정동명'].localeCompare(b['행정동명']) || a['기준연월'].localeCompare(b['기준연월'])).map(r => <tr key={r['행정동명'] + r['기준연월']}><td>{r['행정동명']}</td><td>{r['기준연월']}</td><td>{number(r.change_pct)}{Number.isFinite(r.change_pct) ? '%' : ''}</td><td>{!r.has_enough_history ? '이력 부족' : r.is_risk_signal ? '확인 후보' : '기준 미해당'}</td></tr>)}</tbody></table></div> : <p className="hint">선택한 조건에 해당하는 자료가 없습니다.</p>}</details>
    </>}
    <p className="hint comparison-footnote">누락된 값은 그래프에서 연결하지 않습니다. 변화율만으로 조치의 효과를 판단할 수는 없습니다.</p>
  </section>;
}

export function ReportQuality({ content, workflow }) {
  if (!content) return null;
  const { strong, unmatched, missingServiceSource } = reportChecks(content, workflow);
  return <details className="report-quality" open={strong || unmatched.length > 0 || missingServiceSource || undefined}><summary>보고서 검토 도움말{strong || unmatched.length > 0 || missingServiceSource ? ' · 확인할 항목 있음' : ''}</summary><ul><li>{workflow.analysis_source ? `분석 출처: ${workflow.analysis_source}` : '분석 출처가 기록되어 있는지 확인하세요.'}</li><li>{unmatched.length ? `저장된 분석값과 바로 대조되지 않는 수치: ${unmatched.map(n => n + '%').join(', ')}. 사업 지원 비율 등 별도 출처가 있는 값인지 확인하세요.` : '입력된 백분율에서 저장된 분석값과 다른 수치가 발견되지 않았습니다. 지표·기간의 연결은 직접 확인하세요.'}</li><li>{missingServiceSource ? '원문 출처가 누락된 사업 기록이 있습니다. 운영기관에 확인하세요.' : '저장된 사업 원문 링크를 참고해 자격·접수 여부를 확인하세요.'}</li><li>{strong ? '고립 판정 또는 효과 단정으로 읽힐 수 있는 표현이 있습니다. 지역 변화 근거에 맞게 수정하세요.' : '지역 집계 신호이며 개인의 고립 판정으로 표현하지 않았는지 확인하세요.'}</li></ul><p className="hint">자동 점검은 보조 안내입니다. 전체 수치의 정확성이나 문장 의미를 보증하지 않습니다.</p></details>;
}
