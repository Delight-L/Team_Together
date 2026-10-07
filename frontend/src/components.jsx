import React, { useEffect, useRef, useState } from 'react';
import { api, number } from './api';

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
export function Trend({ assessment, district, metric = '전화 연락', maxRows = 12, extent }) {
  const allRows = assessment
    .filter((r) => r['행정동명'] === district && r.metric_label === metric)
    .sort((a, b) => a['기준연월'].localeCompare(b['기준연월']));
  const rows = maxRows ? allRows.slice(-maxRows) : allRows;
  const values = rows.map((r) => r.change_pct).filter(Number.isFinite);
  if (!values.length) return <div className="empty">변화 추이를 계산할 자료가 없습니다.</div>;
  const low = extent?.[0] ?? Math.min(0, ...values),
    high = extent?.[1] ?? Math.max(0, ...values),
    range = high - low || 1;
  const x = (i) => 40 + (i * 660) / Math.max(1, rows.length - 1),
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
      className="trend"
      viewBox="0 0 740 195"
      role="img"
      aria-label={`${district} ${metric} ${maxRows ? '최근 분석월' : '선택 기간'} 전월 변화율`}
    >
      {[low, (low + high) / 2, high].map((v, i) => (
        <g key={i}>
          <line x1="40" y1={y(v)} x2="700" y2={y(v)} stroke="#e8edf6" />
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
            {(i % Math.max(1, Math.ceil(rows.length / 6)) === 0 || i === rows.length - 1) && (
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
export function ChatPanel({
  context,
  hasEvidence,
  onAction,
  expanded,
  onExpand,
  onClose,
  visible,
}) {
  const [messages, setMessages] = useState([]),
    [input, setInput] = useState(''),
    [busy, setBusy] = useState(false),
    [topicTab, setTopicTab] = useState('regional'),
    [error, setError] = useState('');
  const end = useRef(null),
    request = useRef(null);
  const contextKey = JSON.stringify(context);
  // 지역/월 변경 시 이전 요청을 취소하고 대화를 초기화합니다.
  // return 함수는 변경 전 또는 컴포넌트 제거 시 정리 작업을 실행합니다.
  useEffect(() => {
    setMessages([]);
    setError('');
    setInput('');
    setBusy(false);
    request.current?.abort();
    return () => request.current?.abort();
  }, [contextKey]);
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [messages, busy]);
  // async/await는 서버 답변을 기다리는 문법입니다. AbortController로 이전 요청을 취소합니다.
  async function send(question = input, topic = null) {
    if (!question.trim() || busy) return;
    const controller = new AbortController();
    request.current = controller;
    const history = messages.slice(-4);
    setMessages((m) => [...m, { role: 'user', text: question }]);
    setInput('');
    setBusy(true);
    setError('');
    try {
      const result = await api(
        '/chat',
        { ...context, question, history, topic },
        { signal: controller.signal },
      );
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: result.answer, mode: result.mode, actions: result.actions },
      ]);
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message);
    } finally {
      if (request.current === controller) setBusy(false);
    }
  }
  return (
    <aside
      className={`chat-panel ${expanded ? 'expanded' : ''}`}
      style={{ display: visible ? undefined : 'none' }}
      aria-label="보미 챗봇"
    >
      <header className="chat-heading">
        <div>
          <span className="eyebrow">YOUR WELFARE PARTNER</span>
          <h2>
            보미와 함께 살펴봐요
          </h2>
        </div>
        <div className="chat-heading-actions">
        <button
          className="icon-button"
          onClick={onExpand}
          aria-label={expanded ? '챗봇 작게 보기' : '챗봇 크게 보기'}
          title={expanded ? '챗봇 작게 보기' : '챗봇 크게 보기'}
        >
          <Icon name={expanded ? 'minimize' : 'expand'} />
        </button>
        <button className="icon-button" onClick={onClose} aria-label="챗봇 닫기">
          <Icon name="close" size={17} />
        </button>
        </div>
      </header>
      <div className="chat-intro">
        <Bomi busy={busy} />
        <div>
          <b>작은 변화도 놓치지 않도록</b>
          <p>
            지역 분석부터 사업 검토까지
            <br />
            함께 읽고 설명해 드릴게요.
          </p>
        </div>
      </div>
      <div className="context-chip">
        <span className="context-region">분석 지역: {context.district || `${context.city} 전체`}</span>
        <span>기준월: {context.month}</span>
      </div>
      <div className={`chat-messages ${!messages.length ? 'is-empty' : ''}`} aria-live="polite">
        <div className="chat-start">
          {!messages.length && (
            <div className="chat-welcome">
              <h3>무엇을 도와드릴까요?</h3>
              <p>{hasEvidence
                ? `${context.district}의 지역 변화부터 함께 살펴볼까요?`
                : '궁금한 주제를 선택하거나 자유롭게 질문해 주세요.'}</p>
            </div>
          )}
        </div>
        {messages.map((m, i) => (
          <article className={`message ${m.role}`} key={i}>
            {m.role === 'assistant' && <span className="assistant-label">보미</span>}
            <div>{m.text}</div>
            {m.mode && <small>{m.mode}</small>}
            {m.role === 'assistant' && hasEvidence && <div className="experience-toolbar"><button className="text-button" onClick={() => onAction({ view: 'chart' })}>분석 근거 확인 →</button><button className="text-button" onClick={() => onAction({ view: 'followup', reviewNote: m.text })}>검토 의견으로 가져오기 →</button></div>}
            {m.actions?.map((a) => (
              <button className="text-button" key={a.label} onClick={() => onAction(a)}>
                {a.label}
                <Icon name="arrow" size={15} />
              </button>
            ))}
          </article>
        ))}
        {busy && (
          <div className="typing" aria-label="답변을 준비하고 있습니다">
            <i />
            <i />
            <i />
            <span>분석 근거를 확인하고 있어요</span>
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div ref={end} />
      </div>
      <div className="chat-footer">
        <p className="free-chat-note">자유 질문은 총괄 AI가 담당 에이전트에 연결합니다.</p>
      {/* 고정 주제 버튼은 topic ID를 보내며 서버에서 AI를 호출하지 않습니다. */}
      <div className="chat-topics" key={visible ? 'topics-visible' : 'topics-hidden'}>
        <div className="topic-tabs">
          {[
            ['regional', '지역 분석'],
            ['matching', '사업 매칭 검토'],
            ['report', '보고서 작성'],
          ].map(([id, label]) => (
            <button
              key={id}
              className={topicTab === id ? 'active' : ''}
              onClick={() => setTopicTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="topic-buttons" key={topicTab}>
          {(topicTab === 'regional'
            ? [
                ['changes', '지역 변화 살펴보기'],
                ['method', '분석 기준 이해하기'],
                ['priority', '우선 확인 지역'],
              ]
            : topicTab === 'matching'
              ? [
                  ['matching', '복지사업 연결하기'],
                  ['eligibility', '사업 조건 확인하기'],
                ]
              : [['report', '보고서 작성 방법'], ['report_draft', '약식보고서 초안 만들기']]
          ).map(([id, label]) => (
            <button key={id} disabled={busy} onClick={() => send(label, id)}>
              {label}
            </button>
          ))}
        </div>
      </div>
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <textarea
            rows="1"
            value={input}
            maxLength={2000}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={'보미에게 자유롭게 질문해 주세요'}
            aria-label="챗봇 질문"
          />
          <button disabled={busy || !input.trim()} aria-label="질문 보내기">
            <Icon name="send" />
          </button>
        </form>
        <small>지역 집계자료의 변화이며, 개인의 고립 판정이 아닙니다.</small>
      </div>
    </aside>
  );
}
