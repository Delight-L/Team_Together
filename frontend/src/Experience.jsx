import React, { useEffect, useRef, useState } from 'react';
import { api, query, number } from './api';
import { Trend } from './components';
import { reportChecks } from './experienceLogic.mjs';

const steps = [['dashboard', '지역 선택'], ['chart', '분석 확인·근거 검토'], ['services', '사업 검토'], ['report', '보고서 저장']];
export function SupportDialog({ onClose, data, context, rows, workflow, onView, onSelect, regions, user, onTrial, busy, trialError, page }) {
  const dialog = useRef(null);
  const [tab, setTab] = useState('guide');
  useEffect(() => { const el = dialog.current; el.showModal(); return () => el.close(); }, []);
  const navigate = view => { onView(view); onClose(); };
  return <dialog ref={dialog} className="support-dialog" aria-labelledby="support-title" onClose={onClose}>
    <header className="experience-toolbar"><h2 id="support-title">이용 안내</h2><button className="secondary" onClick={onClose} aria-label="이용 안내 닫기">닫기</button></header>
    <div className="support-tabs" role="group" aria-label="안내 종류">{[['guide', '체험·업무 안내'], ['data', '데이터 기준'], ['feedback', '체험 의견']].map(([id, label]) => <button className={tab === id ? 'primary' : 'secondary'} key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
    {tab === 'guide' && <ExperienceGuide context={context} workflow={workflow} onView={navigate} onSelect={onSelect} regions={regions} user={user} onTrial={async mode => { if (await onTrial(mode)) onClose(); }} busy={busy} trialError={trialError} trialSupported={data.capabilities?.isolatedTrial === true} />}
    {tab === 'data' && <DataSummary data={data} context={context} rows={rows} expanded />}
    {tab === 'feedback' && <Feedback page={page} user={user} expanded />}
  </dialog>;
}
export function ExperienceGuide({ context, workflow, onView, onSelect, regions, user, onTrial, busy, trialSupported, trialError }) {
  const done = workflow.done || [];
  const next = !context.district ? 0 : !done.includes(1) ? 1 : !done.includes(2) ? 2 : 3;
  const hasData = regions.some(r => r.rows.length);
  return <section className="card experience-guide">
    <h3>{user.trial ? '체험 중입니다' : '업무 흐름 안내'}</h3>
    <p className="hint">지역 선택 → 분석 근거 확인 → 사업 검토 → 보고서 작성 순서로 진행합니다.</p>
    <ol className="experience-steps">{steps.map(([view, label], i) => <li key={view} className={i === next ? 'current' : ''}>
      <button className="text-button" disabled={busy} aria-current={i === next ? 'step' : undefined} onClick={() => onView(view)}>{i + 1}. {label} {i === 0 ? context.district ? '✓' : '' : done.includes(i === 1 ? 1 : i === 2 ? 2 : 3) ? '✓' : ''}</button>
    </li>)}</ol>
    <p className="hint">다음 행동: {['지도의 동을 선택하세요.', '지역 분석에서 분석 확인을 저장한 뒤 근거 검토를 완료하세요.', '사업을 조회하고 검토 근거를 저장하세요.', done.includes(3) ? '보고서가 저장되었습니다. 후속 조치를 기록하세요.' : '초안을 편집하고 파일을 확인한 뒤 최종 저장하세요.'][next]}</p>
    <div className="trial-section">
      <h3>{user.trial ? '체험 기록 관리' : '업무를 연습해 보세요'}</h3>
      <p>{user.trial ? '현재 저장하는 내용은 이번 체험의 연습 기록입니다. 체험을 종료하면 시작 전에 보던 업무 화면으로 돌아갑니다.' : '실제 분석 자료를 보며 별도의 연습 기록을 만듭니다. 시작하면 분석 가능한 동의 근거 화면으로 이동합니다.'}</p>
      {!trialSupported && <p className="hint">체험 연결이 준비되지 않았습니다. 관리자에게 문의해 주세요.</p>}
      {!hasData && <p className="hint">현재 지역·기준월에 분석 자료가 있어야 체험을 시작할 수 있습니다.</p>}
      {trialError && <p className="error" role="alert">체험 전환에 실패했습니다. {trialError}</p>}
      <div className="experience-toolbar">
        <button className={user.trial ? 'secondary' : 'primary'} disabled={busy || !trialSupported || !hasData} onClick={() => onTrial('start')}>{busy ? '전환 중…' : user.trial ? '체험 다시 시작' : '체험 시작'}</button>
        {user.trial && <button className="primary" disabled={busy || !trialSupported} onClick={() => onTrial('end')}>체험 종료 · 업무로 돌아가기</button>}
        {!user.trial && !context.district && <button className="text-button" disabled={busy || !hasData} onClick={() => { const r = regions.find(r => r.count > 0) || regions.find(r => r.rows.length); if (r) { onSelect(r.name); onView('chart'); } }}>업무 화면에서 지역 살펴보기 →</button>}
      </div>
      {user.trial && <p className="hint">다시 시작하면 새 연습 기록으로 이동합니다.</p>}
    </div>
  </section>;
}

export function DataSummary({ data, context, rows, expanded = false }) {
  const previous = data.months.filter(m => m < context.month).at(-1);
  return <details open={expanded || undefined} className="card data-summary"><summary>데이터 기준 · {context.month} · 출처 및 누락 확인</summary>
    <dl><dt>분석 출처</dt><dd>{data.source}</dd><dt>이전 분석월</dt><dd>{previous || '이전 분석월 없음'} · 신규/연속 후보 비교에 사용합니다. 전월 변화율은 원자료에 계산된 값을 사용합니다.</dd>
      <dt>결과 버전</dt><dd>{data.runId}</dd><dt>분석 파일 변경 시각</dt><dd>{data.analysisFileModifiedAt || '미확인'} · 원천자료 갱신일은 별도 확인 필요</dd><dt>연결 확인 시각</dt><dd>{data.dataCheckedAt || '미확인'}</dd>
      <dt>선택 지역 자료</dt><dd>{context.district ? `${rows.length}개 지표 · 과거 이력 부족 ${rows.filter(r => !r.has_enough_history).length}개 · 전월 변화값 누락 ${rows.filter(r => !Number.isFinite(r.change_pct)).length}개` : '동을 선택하면 제공 범위를 확인할 수 있습니다.'}</dd></dl>
    <p>변화 참고값(Z)은 과거 흐름에서 벗어난 정도입니다. 전화·문자 또는 평일·휴일 이동의 값이 모두 -2 이하일 때 후보로 표시하며, 최소 12회 과거 이력이 필요합니다. 지역 집계 결과이며 개인의 고립 여부를 판정하지 않습니다.</p>
  </details>;
}

const blank = { version: 0, checks: {}, assignee: '', due: '', note: '', followup: '', status: '확인 예정', history: [] };
export function ReviewWorkspace({ context, onView, seed }) {
  const [record, setRecord] = useState(blank), [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(true);
  const [timeline, setTimeline] = useState([]);
  async function loadTimeline() { try { setTimeline((await api('/experience/history?' + query(context))).items); } catch (e) { setError(e.message); } }
  const update = (key, value) => { setRecord(r => ({ ...r, [key]: value })); setNotice('미저장 변경 사항이 있습니다.'); };
  async function reload() {
    setBusy(true); setError('');
    try { setRecord({ ...blank, ...await api('/experience?' + query(context)) }); setNotice('최신 기록을 불러왔습니다.'); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  useEffect(() => { let active = true; api('/experience?' + query(context)).then(r => { if (active) { const imported = seed && ['city','district','month'].every(k => seed.context[k] === context[k]); setRecord({ ...blank, ...r, ...(imported ? { note: [r.note, seed.text].filter(Boolean).join('\n\n').slice(0, 2000) } : {}) }); if (imported) setNotice('챗봇 답변을 검토 의견에 가져왔습니다. 내용을 검토한 뒤 저장하세요.'); } }).catch(e => active && setError(e.message)).finally(() => active && setBusy(false)); return () => { active = false; }; }, []);
  async function save() { setBusy(true); setError(''); try { setRecord({ ...blank, ...await api('/experience', { ...record, ...context }) }); setNotice('검토·후속 조치 기록을 저장했습니다.'); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  return <section className="card info-card review-workspace"><h2>담당자 검토·후속 조치</h2><p>{context.district} · {context.month}의 기록입니다. 업무 공간에서는 같은 지역 담당자와 공유되며, 체험 공간에서는 이번 체험에만 저장됩니다.</p>
    <fieldset disabled={busy}><legend>확인한 사항만 체크하세요</legend>{[['season', '계절에 따른 변화 확인'], ['event', '지역 행사·휴일 영향 확인'], ['definition', '집계 기준 변경 확인'], ['source', '분석 출처·기간 확인']].map(([key, label]) => <label className="confirmation" key={key}><input type="checkbox" checked={!!record.checks[key]} onChange={e => update('checks', { ...record.checks, [key]: e.target.checked })} />{label}</label>)}</fieldset>
    <div className="report-form"><label>담당자·인계 대상<input maxLength={80} disabled={busy} value={record.assignee} onChange={e => update('assignee', e.target.value)} /></label><label>확인 기한<input type="date" disabled={busy} value={record.due} onChange={e => update('due', e.target.value)} /></label>
      <label className="full">검토 의견·인계 내용<textarea maxLength={2000} disabled={busy} value={record.note} onChange={e => update('note', e.target.value)} /></label>
      <label>후속 조치 상태<select disabled={busy} value={record.status} onChange={e => update('status', e.target.value)}>{['확인 예정', '기관 문의 중', '조치 진행', '후속 확인 완료'].map(s => <option key={s}>{s}</option>)}</select></label>
      <label className="full">실제 조치·다음 확인 내용<textarea maxLength={2000} disabled={busy} value={record.followup} onChange={e => update('followup', e.target.value)} placeholder="기관 문의 결과, 실시한 조치와 다음 달 확인할 지표를 기록하세요." /></label></div>
    {error && <p className="error" role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <div className="experience-toolbar"><button className="primary" disabled={busy} onClick={save}>{busy ? '처리 중…' : '검토·후속 조치 저장'}</button><button className="secondary" disabled={busy} onClick={reload}>최신 기록 다시 불러오기</button><button className="text-button" onClick={() => onView('compare')}>월별 변화 비교하기 →</button></div>
    <details><summary>변경 이력 {record.history.length}건</summary>{[...record.history].reverse().map((h, i) => <article className="service-card" key={i}><strong>{h.at} · {h.actor} · {h.status}</strong><p>담당자 {h.assignee || '미지정'} · 기한 {h.due || '미지정'}</p><p>{h.note}</p><p>{h.followup}</p></article>)}</details>
    <details><summary>다른 기준월의 후속 조치</summary><button className="secondary" onClick={loadTimeline}>월별 기록 불러오기</button>{timeline.map(item => <article className="service-card" key={item.month}><b>{item.month} · {item.record.status}</b><p>담당자 {item.record.assignee || '미지정'} · 기한 {item.record.due || '미지정'}</p><p>{item.record.followup || '후속 조치 내용 미입력'}</p></article>)}</details>
  </section>;
}

export function Comparison({ data, context }) {
  const units = data.geometry[context.city]?.units || [];
  const [selected, setSelected] = useState(context.district ? [context.district] : units.slice(0, 2).map(u => u.n));
  const metrics = [...new Set(data.assessment.map(r => r.metric_label))];
  const [metric, setMetric] = useState(metrics[0] || ''), [from, setFrom] = useState(data.months[0]), [to, setTo] = useState(context.month);
  const rows = context.city === '강남구' ? data.assessment.filter(r => r['기준연월'] >= from && r['기준연월'] <= to) : [];
  const values = rows.filter(r => selected.includes(r['행정동명']) && r.metric_label === metric).map(r => r.change_pct).filter(Number.isFinite);
  const extent = [Math.min(0, ...values), Math.max(0, ...values)];
  return <section className="card info-card"><h2>지역·기간 비교</h2><p>최대 4개 동의 실제 월별 전월 변화율을 비교합니다. 그래프는 같은 세로축을 사용하며, 누락은 0으로 채우지 않습니다. 변화율은 조치의 효과를 직접 증명하지 않습니다.</p>
    <div className="experience-toolbar"><label>지표<select value={metric} onChange={e => setMetric(e.target.value)}>{metrics.map(m => <option key={m}>{m}</option>)}</select></label><label>시작월<select value={from} onChange={e => setFrom(e.target.value)}>{data.months.map(m => <option key={m}>{m}</option>)}</select></label><label>종료월<select value={to} onChange={e => setTo(e.target.value)}>{data.months.map(m => <option key={m}>{m}</option>)}</select></label></div>
    <fieldset><legend>비교할 동 선택 (최대 4개)</legend><div className="comparison-options">{units.map(u => <label key={u.n}><input type="checkbox" checked={selected.includes(u.n)} disabled={!selected.includes(u.n) && selected.length >= 4} onChange={e => setSelected(s => e.target.checked ? [...s, u.n] : s.filter(n => n !== u.n))} />{u.n}</label>)}</div></fieldset>
    {from > to ? <p className="error">시작월은 종료월보다 늦을 수 없습니다.</p> : selected.length ? selected.map(n => <article key={n}><h3>{n} · {metric}</h3><Trend assessment={rows} district={n} metric={metric} maxRows={null} extent={extent} /><div className="table-scroll"><table><thead><tr><th>기준월</th><th>전월 변화율</th><th>판단</th></tr></thead><tbody>{rows.filter(r => r['행정동명'] === n && r.metric_label === metric).map(r => <tr key={r['기준연월']}><td>{r['기준연월']}</td><td>{number(r.change_pct)}{Number.isFinite(r.change_pct) ? '%' : ''}</td><td>{!r.has_enough_history ? '이력 부족' : r.is_risk_signal ? '확인 후보' : '기준 미해당'}</td></tr>)}</tbody></table></div></article>) : <p className="empty">비교할 동을 선택하세요.</p>}
  </section>;
}

export function Feedback({ page, user, expanded = false }) {
  const [kind, setKind] = useState('이해하기 어려움'), [message, setMessage] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [items, setItems] = useState([]);
  async function send(e) { e.preventDefault(); setBusy(true); try { await api('/feedback', { page, kind, message }); setMessage(''); setNotice('의견을 저장했습니다.'); } catch (e) { setNotice(e.message); } finally { setBusy(false); } }
  async function load() { try { setItems((await api('/feedback')).items); } catch (e) { setNotice(e.message); } }
  return <details open={expanded || undefined} className="card feedback"><summary>체험 의견 남기기</summary><form onSubmit={send}><label>의견 종류<select value={kind} onChange={e => setKind(e.target.value)}>{['이해하기 어려움', '기능 오류', '추가 요구'].map(k => <option key={k}>{k}</option>)}</select></label><label>현재 화면에 대한 의견<textarea required maxLength={2000} value={message} onChange={e => setMessage(e.target.value)} placeholder="막힌 단계와 기대한 동작을 알려 주세요. 개인정보는 입력하지 마세요." /></label><button className="primary" disabled={busy || !message.trim()}>의견 저장</button></form><p role="status">{notice}</p>{user.admin && <><button className="secondary" onClick={load}>최근 체험 의견 조회</button>{items.map(i => <article key={i.id}><b>{i.created_at} · {i.page} · {i.kind}</b><p>{i.message}</p></article>)}</>}</details>;
}

export function ReportQuality({ content, workflow }) {
  if (!content) return null;
  const { strong, unmatched, missingServiceSource } = reportChecks(content, workflow);
  return <aside className="report-quality"><h3>보고서 검토 도움말</h3><ul><li>{workflow.analysis_source ? `분석 출처: ${workflow.analysis_source}` : '분석 출처가 기록되어 있는지 확인하세요.'}</li><li>{unmatched.length ? `저장된 분석값과 바로 대조되지 않는 수치: ${unmatched.map(n => n + '%').join(', ')}. 사업 지원 비율 등 별도 출처가 있는 값인지 확인하세요.` : '입력된 백분율에서 저장된 분석값과 다른 수치가 발견되지 않았습니다. 지표·기간의 연결은 직접 확인하세요.'}</li><li>{missingServiceSource ? '원문 출처가 누락된 사업 기록이 있습니다. 운영기관에 확인하세요.' : '저장된 사업 원문 링크를 참고해 자격·접수 여부를 확인하세요.'}</li><li>{strong ? '고립 판정 또는 효과 단정으로 읽힐 수 있는 표현이 있습니다. 지역 변화 근거에 맞게 수정하세요.' : '지역 집계 신호이며 개인의 고립 판정으로 표현하지 않았는지 확인하세요.'}</li></ul><p className="hint">자동 점검은 보조 안내입니다. 전체 수치의 정확성이나 문장 의미를 보증하지 않습니다.</p></aside>;
}
