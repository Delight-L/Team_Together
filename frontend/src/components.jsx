import React, { useEffect, useState } from 'react';
import { number } from './api';

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
            <th><abbr title="과거 흐름에서 얼마나 벗어났는지 나타내는 값입니다. 0에서 멀수록 평소와 다릅니다. 판정은 여러 지표를 묶어 수행합니다.">평소 대비 차이</abbr></th>
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

