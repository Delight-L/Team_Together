import React, { useEffect, useRef, useState } from 'react';
import { api, number, streamWelfareChat } from './api';

export function Icon({ name, size = 20 }) {
  const paths = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="2" />
        <rect x="14" y="3" width="7" height="7" rx="2" />
        <rect x="3" y="14" width="7" height="7" rx="2" />
        <rect x="14" y="14" width="7" height="7" rx="2" />
      </>
    ),
    map: (
      <>
        <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z" />
        <path d="M9 3v15M15 6v15" />
      </>
    ),
    chart: (
      <>
        <path d="M4 3v17h17M8 15l4-6 4 3 5-8" />
      </>
    ),
    services: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M19 14a5 5 0 0 1 3 6" />
      </>
    ),
    report: (
      <>
        <path d="M14 3H5v18h14V8zM14 3v5h5M8 12h8M8 16h6" />
      </>
    ),
    data: (
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" />
      </>
    ),
    chat: <path d="M4 4h16v13H9l-5 4Z" />,
    send: <path d="m3 11 18-8-7 18-3-7-8-3Zm8 3 10-11" />,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    expand: <path d="M9 3H3v6M15 21h6v-6M3 3l7 7M21 21l-7-7" />,
    minimize: <path d="M4 14h6v6M20 10h-6V4M10 14l-6 6M14 10l6-6" />,
    logout: <path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4" />,
    clipboard: <><rect x="5" y="5" width="14" height="16" rx="2"/><rect x="9" y="3" width="6" height="5" rx="1"/><path d="M9 12h6M9 16h6"/></>,
    briefcase: <><rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4h8v3M3 12h18M10 12v3h4v-3"/></>,
    phone: <path d="M7 3H4a1 1 0 0 0-1 1c0 10 7 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 2a14 14 0 0 1-7-7l2-2Z"/>,
    bulb: <><path d="M9 18h6M9 21h6M8 15a6 6 0 1 1 8 0l-1 3H9ZM12 1v1M3 4l1 1M20 5l1-1"/></>,
    sparkle: <><path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z"/><path d="M20 2v4M18 4h4"/></>,
    help: <><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 4M12 16h.01"/></>,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.chart}
    </svg>
  );
}

export function Bomi({ busy = false }) {
  // 답변을 기다리는 동안에만 GIF를 DOM에 넣습니다.
  // 평소에는 PNG이므로 숨겨진 GIF가 계속 재생되거나 상시 흔들리지 않습니다.
  const [reducedMotion, setReducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return (
    <div className={`bomi ${busy ? 'thinking' : ''}`}>
      <span className="bomi-halo" />
      <img
        key={busy && !reducedMotion ? 'waiting' : 'idle'}
        src={busy && !reducedMotion ? '/brand/bomi-waiting.gif' : '/brand/welfind_character.png'}
        alt={busy ? '답변을 준비하는 보미' : '분석 도우미 보미'}
      />
    </div>
  );
}

// geometry=기존 SVG 경계, rows=선택 월 분석, selected=선택 동, onSelect=부모 상태 변경 함수.
// 클릭하면 App의 district가 바뀌어 옆 상세 패널과 챗봇이 함께 갱신됩니다.
export function RegionMap({ geometry, rows, selected, onSelect }) {
  if (!geometry) return <div className="empty">연결된 지도 경계가 없습니다.</div>;
  const count = (name) => rows.filter((r) => r['행정동명'] === name && r.is_risk_signal).length;
  const hasHistory = (name) => rows.some((r) => r['행정동명'] === name && r.has_enough_history);
  return (
    <svg
      className="region-map"
      viewBox={`-18 -18 ${geometry.w + 36} ${geometry.h + 36}`}
      aria-label="행정동별 확인 후보 분포"
    >
      <defs>
        <filter id="map-shadow">
          <feDropShadow dx="0" dy="5" stdDeviation="5" floodColor="#16336c" floodOpacity=".12" />
        </filter>
      </defs>
      <g filter="url(#map-shadow)">
        {geometry.units.map((u) => (
          <g
            key={u.n}
            className={`map-region ${selected === u.n ? 'selected' : ''}`}
            role="button"
            tabIndex="0"
            aria-label={`${u.n}, ${hasHistory(u.n) ? '확인 후보 ' + count(u.n) + '개' : '판단 보류'}`}
            aria-pressed={selected === u.n}
            onClick={() => onSelect(u.n)}
            onKeyDown={(e) => {
              if (['Enter', ' '].includes(e.key)) {
                e.preventDefault();
                onSelect(u.n);
              }
            }}
          >
            <path
              d={u.d}
              fill={!hasHistory(u.n) ? '#e7ebf1' : count(u.n) ? '#76a5ff' : '#dceaff'}
            />
            <text x={u.cx} y={u.cy} textAnchor="middle">
              {u.n}
            </text>
            {count(u.n) > 0 && <circle cx={u.cx} cy={u.cy + 16} r="3.5" fill="#2563eb" />}
          </g>
        ))}
      </g>
    </svg>
  );
}

export function EvidenceTable({ rows }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>지표</th>
            <th>전월 변화</th>
            <th><abbr title="과거 변화 흐름에서 얼마나 벗어났는지 나타내는 값입니다. 판정은 여러 지표를 묶어 수행합니다.">변화 참고값(Z)</abbr></th>
            <th>판단</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.metric_label}>
              <td>{r.metric_label}</td>
              <td>
                {number(r.change_pct)}
                {Number.isFinite(r.change_pct) ? '%' : ''}
              </td>
              <td>{number(r.risk_robust_z, 2)}</td>
              <td>
                <span
                  className={`badge ${r.is_risk_signal ? 'blue' : !r.has_enough_history ? 'amber' : ''}`}
                >
                  {!r.has_enough_history
                    ? '이력 부족'
                    : r.is_risk_signal
                      ? '확인 후보'
                      : '기준 미해당'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// 실제 분석값만 그립니다. null은 0으로 바꾸지 않고 선을 끊어 누락을 표시합니다.
export function Trend({ assessment, district, metric = '전화 연락', maxRows = 12, extent, compact = false }) {
  const allRows = assessment
    .filter((r) => r['행정동명'] === district && r.metric_label === metric)
    .sort((a, b) => a['기준연월'].localeCompare(b['기준연월']));
  const rows = maxRows ? allRows.slice(-maxRows) : allRows;
  const values = rows.map((r) => r.change_pct).filter(Number.isFinite);
  if (!values.length) return <div className="empty">변화 추이를 계산할 자료가 없습니다.</div>;
  const low = extent?.[0] ?? Math.min(0, ...values),
    high = extent?.[1] ?? Math.max(0, ...values),
    range = high - low || 1;
  const chartWidth = compact ? 400 : 740;
  const x = (i) => 40 + (i * (chartWidth - 80)) / Math.max(1, rows.length - 1),
    y = (v) => 150 - ((v - low) * 120) / range;
  const segments = [];
  let current = [];
  rows.forEach((r, i) => {
    if (Number.isFinite(r.change_pct)) current.push(`${x(i)},${y(r.change_pct)}`);
    else if (current.length) {
      segments.push(current);
      current = [];
    }
  });
  if (current.length) segments.push(current);
  return (
    <svg
      className={`trend${compact ? ' compact-trend' : ''}`}
      viewBox={`0 0 ${chartWidth} 195`}
      role="img"
      aria-label={`${district} ${metric} ${maxRows ? '최근 분석월' : '선택 기간'} 전월 변화율`}
    >
      {[low, (low + high) / 2, high].map((v, i) => (
        <g key={i}>
          <line x1="40" y1={y(v)} x2={chartWidth - 40} y2={y(v)} stroke="#e8edf6" />
          <text x="0" y={y(v) + 4}>
            {number(v)}%
          </text>
        </g>
      ))}
      {segments.map((points, i) => (
        <polyline key={i} points={points.join(' ')} fill="none" stroke="#2563eb" strokeWidth="3" />
      ))}
      {rows.map((r, i) =>
        Number.isFinite(r.change_pct) ? (
          <g key={r['기준연월']}>
            <circle cx={x(i)} cy={y(r.change_pct)} r="4" fill="#2563eb">
              <title>
                {r['기준연월']} · {number(r.change_pct)}%
              </title>
            </circle>
            {(i % Math.max(1, Math.ceil(rows.length / (compact ? 3 : 6))) === 0 || i === rows.length - 1) && (
              <text x={x(i)} y="181" textAnchor="middle">
                {r['기준연월']}
              </text>
            )}
          </g>
        ) : null,
      )}
    </svg>
  );
}

// App의 context로 지도와 같은 지역/월을 질문합니다.
// messages=대화 상태, busy=처리 중 표시/중복 전송 방지. AI 키는 서버에만 있습니다.
export function ChatPanel({ context, expanded, onExpand, onClose, visible, draft }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [mode, setMode] = useState('연결 확인 중');
  const end = useRef(null), request = useRef(null), inputField = useRef(null), appliedDraft = useRef(null);
  const contextKey = JSON.stringify(context);
  useEffect(() => {
    let active = true;
    api('/chat/config').then(data => {
      if (active) setMode(`${data.mode} · 사업 ${data.resourceCount}건`);
    }).catch(() => { if (active) setMode('연결 확인 필요'); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    request.current?.abort(); request.current = null;
    setMessages([]); setInput(''); setError(''); setBusy(false);
    return () => { request.current?.abort(); request.current = null; };
  }, [contextKey]);
  useEffect(() => {
    if (draft?.contextKey === contextKey && appliedDraft.current !== draft.id) {
      appliedDraft.current = draft.id;
      setInput(draft.question);
      inputField.current?.focus();
    }
  }, [draft, contextKey]);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }, [messages, busy]);
  function stop() {
    request.current?.abort(); request.current = null; setBusy(false);
    setMessages(previous => previous.map((m, i) => i === previous.length - 1 && m.role === 'assistant'
      ? { ...m, text: m.text || '응답이 중지되었습니다.', interrupted: true } : m));
  }
  async function send(value = input) {
    const question = value.trim();
    if (!question || request.current) return;
    const controller = new AbortController(); request.current = controller;
    const history = messages.filter(m => m.text && !m.interrupted).slice(-38);
    const next = [...history, { role: 'user', text: question }];
    const index = next.length;
    setMessages([...next, { role: 'assistant', text: '', sources: [] }]);
    setInput(''); setError(''); setBusy(true);
    function update(fn) {
      if (request.current !== controller) return;
      setMessages(previous => previous.map((m, i) => i === index ? fn(m) : m));
    }
    try {
      await streamWelfareChat(context, next.map(m => ({ role: m.role, content: m.text })), (event, payload) => {
        if (request.current !== controller) return;
        if (event === 'token') update(m => ({ ...m, text: m.text + payload.text }));
        else if (event === 'sources') update(m => ({ ...m, sources: payload.records, mode: payload.mode }));
        else if (event === 'replace') update(m => ({ ...m, text: payload.text, mode: payload.mode }));
        else if (event === 'error') setError(payload.message);
      }, controller.signal);
    } catch (e) {
      if (request.current === controller && e.name !== 'AbortError') {
        setError(e.message); update(m => ({ ...m, interrupted: true }));
      }
    } finally {
      if (request.current === controller) { request.current = null; setBusy(false); }
    }
  }
  return <aside className={`chat-panel welfare-chat ${expanded ? 'expanded' : ''}`}
    style={{ display: visible ? undefined : 'none' }} aria-label="복지이음 챗봇">
    <header className="chat-heading"><div><span className="eyebrow">TEAM TOGETHER</span>
      <h2>✳ 복지이음 <span className="online-dot" /></h2></div>
      <button className="icon-button" onClick={onExpand} aria-label={expanded ? '챗봇 패널로 돌아가기' : '챗봇 크게 보기'}><Icon name={expanded ? 'close' : 'chat'} /></button>
      <button className="icon-button" onClick={onClose} aria-label="챗봇 닫기"><Icon name="close" size={17} /></button>
    </header>
    <div className="chat-intro"><Bomi busy={busy} /><div><b>필요한 지원을 함께 찾아요</b><p>복지사업과 담당 기관을<br/>팀 자료에서 찾아 안내합니다.</p></div></div>
    <div className="context-chip"><span className="online-dot"/>{context.city} {context.district || '전체'}<span>{context.month}</span></div>
    <div className="welfare-status"><small>{mode}</small><button className="text-button" disabled={busy} onClick={() => { setMessages([]); setInput(''); setError(''); }}>＋ 새 대화</button></div>
    <div className="chat-messages" aria-live="polite">
      {!messages.length && <div className="welcome"><span className="assistant-label">당신의 일상에 필요한 연결</span><h3>어떤 도움이 필요하신가요?</h3>
        <p>거주 지역과 필요한 지원을 알려주세요. 관련 사업과 확인할 다음 단계를 찾아드릴게요.</p>
        <div className="suggestions">{['혼자 사는 어르신 돌봄 지원', '병원에 함께 가줄 지원이 있나요?', '청년이 참여할 관계 모임을 찾아주세요', '세곡동 식생활 지원이 궁금해요'].map(q =>
          <button key={q} disabled={busy} onClick={() => send(q)}>{q}<Icon name="arrow" size={15}/></button>)}</div>
        <p className="welfare-notice">계획·검토 자료가 포함되어 있습니다. 현재 운영·자격·접수는 담당 기관 확인이 필요합니다.</p>
      </div>}
      {messages.map((m, i) => <article className={`message ${m.role}`} key={i}>
        {m.role === 'assistant' && <span className="assistant-label">✳ 복지이음</span>}
        <div>{m.text || (busy ? '관련 자료를 찾고 있어요…' : '답변을 완료하지 못했습니다.')}</div>
        {m.mode && <small>{m.mode}</small>}
        {m.sources?.length > 0 && <details className="welfare-sources"><summary>참고한 팀 자료 · {m.sources.length}건</summary>
          {m.sources.map(r => <div key={r.id}><strong>{r.name}</strong><p>{r.source} · p. {r.pages}</p><small>{r.status}</small></div>)}
        </details>}
      </article>)}
      {error && <p className="error" role="alert">{error}</p>}<div ref={end}/>
    </div>
    <div className="chat-footer"><p className="free-chat-note">서울시·강남구 중심의 팀 자료를 검색합니다.</p>
      <form className="chat-input" onSubmit={e => { e.preventDefault(); send(); }}>
        <textarea ref={inputField} rows="2" value={input} maxLength={2000} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }}
          placeholder="예: 병원 동행 지원이 필요해요" aria-label="복지지원 질문"/>
        {busy ? <button type="button" onClick={stop}>중지</button> : <button disabled={!input.trim()} aria-label="질문 보내기"><Icon name="send"/></button>}
      </form><small>주민등록번호·정확한 주소 등 개인정보는 입력하지 마세요.</small>
    </div>
  </aside>;
}
