import React, { useEffect, useState } from 'react';
import { number } from './api';

export function Icon({ name, size = 20 }) {
  const paths = {
    discover: <><circle cx="10" cy="10" r="7"/><path d="m15 16 6 6M5 12l4-4 3 2 3-4"/></>,
    neighborhood: <><path d="M2 22h20M4 22V9l5-4 5 4v13M7 5V3l3-2 3 2v4M7 11h1m3 0h1M7 15h1m3 0h1M7 19h1"/><circle cx="18" cy="13" r="3"/><path d="M13 22v-2a5 5 0 0 1 10 0v2M18 3v4M16 5h4"/></>,
    support: <><path d="M12 9C5 5 11 0 14 4c3-4 9 1 2 5l-2 2ZM2 15h3v7H2zM5 16l4-2 7 2q3 1 1 3h-6m6-1 4-3q3-1 2 2l-6 5H9l-4-2"/></>,
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
    compare: <path d="M3 21h18M6 21V11M10 21V5M14 21v-8M18 21V8" />,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></>,
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

export function EvidenceTable({ rows }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>지표</th>
            <th>전월 변화</th>
            <th><abbr title="과거 흐름에서 얼마나 벗어났는지 나타내는 값입니다. 0에서 멀수록 평소와 다릅니다. 판정은 여러 지표를 묶어 수행합니다.">평소 대비 차이(점수)</abbr></th>
            <th>판단</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.metric_label}>
              <td>{r.metric_label}{r.is_risk_signal && r.detection_path ? ` · ${r.detection_path}` : ''}</td>
              <td>
                {number(r.change_pct)}
                {Number.isFinite(r.change_pct) ? '%' : ''}
              </td>
              <td>{number(r.risk_robust_z, 2)}</td>
              <td>
                <span
                  className={`status-tag ${!r.has_enough_history ? 'sky' : r.is_risk_signal ? 'rose' : ''}`}
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
      <p className="score-note">
        평소 대비 차이는 단위가 없는 점수입니다. 시·군·구 전체의 공통 흐름을 뺀 변화가 이 동의
        과거 변동 폭보다 얼마나 큰지 나타내며, 음수는 평소보다 줄어든 방향입니다. 짝을 이룬
        지표(전화·문자, 평일·휴일 이동)가 함께 약 -2 이하이면 확인 후보가 됩니다. 그래서 전월에
        늘어난 지표도 다른 동보다 덜 늘었다면 후보가 될 수 있습니다.
      </p>
    </div>
  );
}

// 실제 분석값만 그립니다. null은 0으로 바꾸지 않고 선을 끊어 누락을 표시합니다.
export function Trend({ assessment, district, metric = '전화 연락', maxRows = 12, extent, compact = false }) {
  const [hover, setHover] = useState(null);
  useEffect(() => setHover(null), [assessment, district, metric, maxRows]);
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
      onPointerLeave={() => setHover(null)}
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
      {rows.map((r, i) => {
        const left = i === 0 ? 40 : (x(i - 1) + x(i)) / 2;
        const right = i === rows.length - 1 ? chartWidth - 40 : (x(i) + x(i + 1)) / 2;
        return (
          <rect key={`hover-${r['기준연월']}`} x={left} y="20" width={right - left} height="170"
            fill="transparent" tabIndex="0" role="button"
            aria-label={`${r['기준연월']} ${metric} 전월 변화율 ${Number.isFinite(r.change_pct) ? `${number(r.change_pct)}%` : '자료 없음'}`}
            onPointerEnter={() => setHover(i)} onPointerMove={() => setHover(i)}
            onFocus={() => setHover(i)} onBlur={() => setHover(null)} />
        );
      })}
      {hover !== null && rows[hover] && (
        <g pointerEvents="none">
          <line x1={x(hover)} x2={x(hover)} y1="20" y2="155" stroke="#94a3b8" strokeDasharray="4 4" />
          {Number.isFinite(rows[hover].change_pct) && (
            <circle cx={x(hover)} cy={y(rows[hover].change_pct)} r="6" fill="#2563eb" stroke="white" strokeWidth="2" />
          )}
          <g transform={`translate(${Math.max(40, Math.min(chartWidth - 210, x(hover) - 85))}, 1)`} role="tooltip">
            <rect width="170" height="48" rx="6" fill="white" stroke="#cbd5e1" />
            <text x="10" y="18" style={{ fill: '#334155', fontSize: 12 }}>{rows[hover]['기준연월']} · {metric}</text>
            <text x="10" y="36" style={{ fill: '#2563eb', fontSize: 13, fontWeight: 700 }}>
              전월 대비 {Number.isFinite(rows[hover].change_pct) ? `${number(rows[hover].change_pct)}%` : '자료 없음'}
            </text>
          </g>
        </g>
      )}
    </svg>
  );
}

