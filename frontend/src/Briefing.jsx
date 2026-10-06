import React, { useMemo, useState } from 'react';
import { Icon, EvidenceTable } from './components';
import { number } from './api';

// 종합 현황과 지역 현황은 같은 원자료를 사용하지만 다른 업무를 돕습니다.
// 종합 현황=이번 달 우선 확인 지역을 발견 / 지역 현황=모든 동을 필터링·비교.
export function summarizeRegions(assessment, geometry, city, month, months) {
  const current = city === '강남구' ? assessment.filter((r) => r['기준연월'] === month) : [];
  const previous = months.filter((m) => m < month).at(-1);
  const old = city === '강남구' ? assessment.filter((r) => r['기준연월'] === previous) : [];
  return (geometry?.units || []).map((unit) => {
    const rows = current.filter((r) => r['행정동명'] === unit.n);
    const earlier = old.filter((r) => r['행정동명'] === unit.n);
    const count = rows.filter((r) => r.is_risk_signal).length;
    const comparable =
      rows.some((r) => r.has_enough_history) && earlier.some((r) => r.has_enough_history);
    const pending = rows.length > 0 && rows.some((r) => !r.has_enough_history);
    const status = !rows.length
      ? '자료 없음'
      : count > 0
        ? comparable
          ? earlier.some((r) => r.is_risk_signal)
            ? '연속 후보'
            : '신규 후보'
          : '변화 후보'
        : pending
          ? '판단 보류'
          : '기준 미해당';
    const zValues = rows.map((r) => r.risk_robust_z).filter(Number.isFinite);
    return {
      name: unit.n,
      unit,
      rows,
      count,
      pending,
      status,
      minZ: zValues.length ? Math.min(...zValues) : null,
    };
  });
}

const tone = (status) =>
  status === '신규 후보'
    ? 'rose'
    : status === '연속 후보'
      ? 'orange'
      : status === '판단 보류'
        ? 'sky'
        : status === '변화 후보'
          ? 'rose'
          : 'quiet';
const colors = { rose: '#ff527b', orange: '#ff9b35', sky: '#4f9cf8', quiet: '#cddbcf' };

// 작은 입체 건물/나무는 SVG 장식입니다. 실제 건물 위치나 3D 지형 데이터가 아닙니다.
// 행정동 폴리곤만 기존 경계 JSON을 그대로 사용하며, 수치는 실제 Analysis2 결과입니다.
function Building({ x, y, height = 34 }) {
  const w = 13,
    h = 9;
  return (
    <g transform={`translate(${x} ${y})`} className="scene-building">
      <ellipse cx="18" cy="8" rx="24" ry="10" fill="#63725d" opacity=".2" />
      <path d={`M0 0 ${w} ${h} ${w} ${h - height} 0 ${-height}Z`} fill="#a1aba3" />
      <path d={`M${w} ${h} ${w * 2} 0 ${w * 2} ${-height} ${w} ${h - height}Z`} fill="#e1e5dc" />
      <path
        d={`M0 ${-height} ${w} ${-height - h} ${w * 2} ${-height} ${w} ${h - height}Z`}
        fill="#fbfcf7"
      />
      {[0, 1, 2].map((i) => (
        <path
          key={i}
          d={`M3 ${-height + 8 + i * 9} 10 ${-height + 12 + i * 9} M17 ${-height + 11 + i * 9} 23 ${-height + 7 + i * 9}`}
          stroke="#aebea9"
          strokeWidth="2"
        />
      ))}
    </g>
  );
}
function Tree({ x, y }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <ellipse cy="4" rx="7" ry="3" fill="#aabca7" opacity=".25" />
      <path d="M0 3V-11" stroke="#c0ac8f" strokeWidth="3" />
      <ellipse cy="-14" rx="8" ry="11" fill="#a5c680" />
      <ellipse cx="-3" cy="-17" rx="4" ry="7" fill="#bdd998" />
    </g>
  );
}

export function MissionMap({ regions, selected, onSelect, geometry, flat = false }) {
  const [zoom, setZoom] = useState(1);
  if (!geometry) return <div className="empty">연결된 지도 경계가 없습니다.</div>;
  // 원래 경계의 가로/세로 크기를 고려해 같은 행렬로 폴리곤·핀을 함께 투영합니다.
  const scale = Math.min(640 / geometry.w, 586 / geometry.h);
  const project = (x, y) =>
    flat
      ? [110 + x * scale, 15 + y * scale * 0.83]
      : [295 + scale * (0.86 * x - 0.32 * y), 35 + scale * (0.2 * x + 0.65 * y)];
  const transform = flat
    ? `translate(110 15) scale(${scale} ${scale * 0.83})`
    : `translate(295 35) matrix(${0.86 * scale} ${0.2 * scale} ${-0.32 * scale} ${0.65 * scale} 0 0)`;
  const priority = regions
    .filter((r) => r.count > 0)
    .sort((a, b) => a.minZ - b.minZ)
    .slice(0, 3);
  return (
    <div className={`mission-map ${flat ? 'flat' : ''}`}>
      <div className="map-tools">
        <button onClick={() => setZoom((z) => Math.min(1.65, z + 0.15))} aria-label="지도 확대">
          +
        </button>
        <button onClick={() => setZoom((z) => Math.max(0.85, z - 0.15))} aria-label="지도 축소">
          −
        </button>
        <button onClick={() => setZoom(1)} aria-label="지도 배율 초기화">
          <Icon name="map" size={15} />
        </button>
      </div>
      <svg
        viewBox="0 0 900 510"
        className="mission-scene"
        role="group"
        aria-label="행정동 확인 후보 지도"
      >
        <defs>
          <pattern
            id="city-blocks"
            width="160"
            height="94"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(-12)"
          >
            <rect width="160" height="94" fill="#edf0e5" />
            <path d="M0 0H160M0 0V94" stroke="#fff" strokeWidth="14" />
            <path d="M0 0H160M0 0V94" stroke="#dddcca" strokeWidth="2" />
            <rect x="24" y="21" width="48" height="39" rx="5" fill="#dbe6cc" />
            <rect x="97" y="19" width="33" height="43" rx="4" fill="#e4e8dc" />
          </pattern>
          <filter id="district-relief">
            <feDropShadow dx="0" dy="8" stdDeviation="5" floodColor="#3b6044" floodOpacity=".12" />
          </filter>
          <filter id="pin-shadow">
            <feDropShadow dx="0" dy="3" stdDeviation="3" floodOpacity=".15" />
          </filter>
        </defs>
        {!flat && (
          <g aria-hidden="true">
            <rect width="900" height="510" fill="url(#city-blocks)" />
            <path
              d="M-30 103C180 10 310 127 510 67S700 20 960 91"
              fill="none"
              stroke="#fff"
              strokeWidth="54"
            />
            <path
              d="M-30 103C180 10 310 127 510 67S700 20 960 91"
              fill="none"
              stroke="#b3daeb"
              strokeWidth="39"
            />
            <path d="M45 40 820 480M140 480 790 15" stroke="#fafbf6" strokeWidth="18" />
            {[
              [55, 190],
              [145, 180],
              [210, 92],
              [610, 67],
              [720, 145],
              [815, 155],
              [62, 315],
              [136, 362],
              [231, 445],
              [360, 459],
              [712, 404],
              [817, 365],
              [780, 275],
              [553, 453],
              [640, 313],
              [135, 267],
              [434, 56],
            ].map(([x, y], i) => (
              <Building key={i} x={x} y={y} height={25 + (i % 4) * 14} />
            ))}
            {[
              [34, 234],
              [100, 207],
              [170, 153],
              [181, 300],
              [110, 430],
              [272, 473],
              [655, 455],
              [778, 403],
              [805, 232],
              [684, 149],
              [748, 69],
              [580, 36],
              [472, 468],
              [295, 70],
              [843, 440],
            ].map(([x, y], i) => (
              <Tree key={i} x={x} y={y} />
            ))}
          </g>
        )}
        <g transform={`translate(450 255) scale(${zoom}) translate(-450 -255)`}>
          <g transform={transform} filter="url(#district-relief)">
            {regions.map((region) => {
              const fill =
                region.name === selected
                  ? '#326ee6'
                  : region.count
                    ? colors[tone(region.status)]
                    : region.status === '판단 보류'
                      ? '#b9d6f5'
                      : region.status === '자료 없음'
                        ? '#e2e4e0'
                        : '#d0dfbf';
              return (
                <g
                  key={region.name}
                  className={`mission-district ${selected === region.name ? 'selected' : ''}`}
                  role="button"
                  tabIndex="0"
                  aria-label={`${region.name}, ${region.status}, 후보 ${region.count}개`}
                  aria-pressed={selected === region.name}
                  onClick={() => onSelect(region.name)}
                  onKeyDown={(e) => {
                    if (['Enter', ' '].includes(e.key)) {
                      e.preventDefault();
                      onSelect(region.name);
                    }
                  }}
                >
                  <title>
                    {region.name} · {region.status}
                  </title>
                  {/* 경계의 아래 면을 먼저 그린 뒤 윗면을 올려 실제 두께를 표현합니다. */}
                  {!flat && (
                    <path
                      className="district-side"
                      d={region.unit.d}
                      transform="translate(0 17)"
                      fill={region.count ? '#b73853' : '#809976'}
                    />
                  )}
                  <path d={region.unit.d} fill={fill} />
                  <text x={region.unit.cx} y={region.unit.cy} textAnchor="middle">
                    {region.name}
                  </text>
                </g>
              );
            })}
          </g>
          {!flat && (
            <g className="district-buildings" aria-hidden="true" pointerEvents="none">
              {/* 건물은 지형 실측이 아닌 도시 분위기의 장식입니다. 선택 영역을 가로막지 않습니다. */}
              {regions
                .filter((r) => !r.count)
                .map((r, i) => {
                  const [x, y] = project(r.unit.cx, r.unit.cy);
                  return (
                    <g key={r.name} opacity=".94">
                      <Building x={x - 23} y={y + 18} height={30 + (i % 4) * 12} />
                      {i % 2 === 0 && <Building x={x + 8} y={y + 31} height={22 + (i % 3) * 10} />}
                      <Tree x={x - 34} y={y + 23} />
                    </g>
                  );
                })}
            </g>
          )}
          {!flat &&
            priority.map((r, i) => {
              const [x, y] = project(r.unit.cx, r.unit.cy),
                color = colors[tone(r.status)];
              // 핀에서 Enter/Space도 지역을 선택할 수 있도록 키보드 동작을 제공합니다.
              return (
                <g
                  key={r.name}
                  transform={`translate(${x} ${y - 16})`}
                  className="mission-pin"
                  role="button"
                  tabIndex="0"
                  aria-label={`${r.name} ${r.status} 상세`}
                  onClick={() => onSelect(r.name)}
                  onKeyDown={(e) => {
                    if (['Enter', ' '].includes(e.key)) {
                      e.preventDefault();
                      onSelect(r.name);
                    }
                  }}
                  filter="url(#pin-shadow)"
                >
                  <ellipse rx="18" ry="7" fill={color} opacity=".22" />
                  <path
                    d="M0 0C-5-11-20-25-20-40a20 20 0 0 1 40 0C20-25 5-11 0 0Z"
                    fill={color}
                    stroke="#fff"
                    strokeWidth="3"
                  />
                  <text y="-34" textAnchor="middle" fill="white" fontSize="18" fontWeight="800">
                    {i + 1}
                  </text>
                  <rect x="26" y="-62" width="146" height="57" rx="11" fill="#fff" />
                  <text x="39" y="-40" fontSize="14" fontWeight="800" fill="#213758">
                    {r.name}
                  </text>
                  <text x="39" y="-20" fontSize="11" fontWeight="600" fill={color}>
                    {r.status} · {r.count}개 지표
                  </text>
                </g>
              );
            })}
        </g>
      </svg>
      <div className="scene-note">
        {flat ? '행정동 경계 기반' : '행정동 경계 기반 · 건물 배경은 이해를 돕는 일러스트'}
      </div>
    </div>
  );
}

export function RegionInsight({ region, city, month, onClose, onStart, onChat, busy }) {
  if (!region) return null;
  return (
    <section className="region-insight" aria-label={`${region.name} REGION INSIGHT`}>
      <header>
        <div>
          <span className="eyebrow">REGION INSIGHT</span>
          <h2>{region.name}</h2>
        </div>
        <button className="icon-button" aria-label="지역 상세 닫기" onClick={onClose}>
          <Icon name="close" size={17} />
        </button>
      </header>
      <div className="insight-summary">
        <span className={`status-tag ${tone(region.status)}`}>{region.status}</span>
        <small>
          {city} · {month}
        </small>
      </div>
      <div className="insight-count">
        <strong>
          {region.count}
          <small>개</small>
        </strong>
        <span>함께 확인할 변화 지표</span>
      </div>
      {region.rows.length ? (
        <EvidenceTable rows={region.rows} />
      ) : (
        <p className="empty">이 동의 실제 분석 자료가 없습니다.</p>
      )}
      <p className="hint">
        개인의 고립 판정이 아닙니다.
        <br />
        계절·행사·집계 변화는 추가 확인이 필요합니다.
      </p>
      <div className="insight-actions">
        <button className="primary" disabled={busy || !region.rows.length} onClick={onStart}>
          상세 분석·업무 시작
          <Icon name="arrow" size={16} />
        </button>
        <button className="secondary" disabled={!region.rows.length} onClick={onChat}>
          보미와 근거 살펴보기
          <Icon name="chat" size={16} />
        </button>
      </div>
    </section>
  );
}

export function Briefing({
  regions,
  assessment,
  city,
  month,
  geometry,
  selected,
  onSelect,
  onStart,
  onChat,
  busy,
  months,
}) {
  const selectedRegion = regions.find((r) => r.name === selected);
  const candidates = regions.filter((r) => r.count > 0);
  const previous = months.filter((m) => m < month).at(-1);
  const comparable =
    regions.some((r) => r.rows.some((row) => row.has_enough_history)) &&
    assessment.some((r) => city === '강남구' && r['기준연월'] === previous && r.has_enough_history);
  const stats = [
    [
      '신규 확인 후보',
      comparable ? regions.filter((r) => r.status === '신규 후보').length : null,
      '이전 분석월에 없던 후보',
      'rose',
      'chart',
    ],
    [
      '연속 확인 후보',
      comparable ? regions.filter((r) => r.status === '연속 후보').length : null,
      '이전·현재 분석월 모두 후보',
      'orange',
      'chart',
    ],
    [
      '판단 보류 지역',
      regions.filter((r) => r.pending).length,
      '일부 지표의 이력 확인 필요',
      'sky',
      'report',
    ],
  ];
  const highlights = candidates
    .flatMap((r) =>
      r.rows.filter((row) => row.is_risk_signal).map((row) => ({ ...row, name: r.name })),
    )
    .sort((a, b) => a.risk_robust_z - b.risk_robust_z)
    .slice(0, 3);
  return (
    <div className="briefing-v2">
      <div className="mission-kpis">
        {stats.map(([label, value, note, color, icon]) => (
          <section key={label} className={`mission-kpi ${color}`}>
            <div className="mission-kpi-icon">
              <Icon name={icon} size={26} />
            </div>
            <div>
              <span>{label}</span>
              <strong>
                {value === null ? '—' : value}
                <small>{value === null ? '비교 보류' : '곳'}</small>
              </strong>
              <p>{note}</p>
            </div>
            <span className="mission-kpi-note">{color === 'sky' ? '이력 확인' : '전월 비교'}</span>
          </section>
        ))}
      </div>
      <section className={`card mission-map-card ${selectedRegion ? 'insight-open' : ''}`}>
        <header>
          <div>
            <span className="map-folder">
              <Icon name="map" size={20} />
            </span>
            <h2>
              이번 달 우선 확인 지역 <strong>{candidates.length}곳</strong>
            </h2>
          </div>
          <span className="pill">
            {city} · {month}
          </span>
        </header>
        <div className="mission-map-content">
          <MissionMap
            regions={regions}
            geometry={geometry}
            selected={selected}
            onSelect={onSelect}
          />
          {selectedRegion && (
            <RegionInsight
              region={selectedRegion}
              city={city}
              month={month}
              onClose={() => onSelect('')}
              onStart={onStart}
              onChat={onChat}
              busy={busy}
            />
          )}
          <div className="mission-legend">
            <span>
              <i className="rose" />
              신규 후보
            </span>
            <span>
              <i className="orange" />
              연속 후보
            </span>
            <span>
              <i className="sky" />
              판단 보류
            </span>
            <span>
              <i className="quiet" />
              기준 미해당
            </span>
          </div>
        </div>
      </section>
      <section className="card mission-highlights">
        <header>
          <h2>
            <Icon name="chart" size={18} />
            이번 달 주요 변화
          </h2>
          <span>실제 분석값 · 전월 대비</span>
        </header>
        <div className="highlight-grid">
          {highlights.length ? (
            highlights.map((r, i) => (
              <button
                key={r.name + r.metric_label}
                className={['rose', 'sky', 'orange'][i]}
                onClick={() => onSelect(r.name)}
              >
                <div className="change-symbol">
                  <Icon name={i === 2 ? 'services' : 'chart'} size={22} />
                </div>
                <div>
                  <span>
                    {r.name} · {r.metric_label}
                  </span>
                  <strong>{number(r.change_pct)}%</strong>
                </div>
                <svg viewBox="0 0 52 30" aria-hidden="true">
                  <path
                    d={
                      r.change_pct < 0
                        ? 'M2 5 12 10 21 7 31 18 40 15 50 26'
                        : 'M2 25 12 20 21 23 31 12 40 15 50 4'
                    }
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="3"
                  />
                </svg>
              </button>
            ))
          ) : (
            <p className="hint">
              현재 기준을 통과한 변화 후보가 없습니다. 자료 없음과 판단 보류도 함께 확인하세요.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

export function RegionalOverview({
  regions,
  geometry,
  selected,
  onSelect,
  city,
  month,
  onStart,
  onChat,
  busy,
}) {
  const [filter, setFilter] = useState('전체'),
    [search, setSearch] = useState(''),
    [sort, setSort] = useState('후보 우선');
  const shown = useMemo(
    () =>
      regions
        .filter(
          (r) =>
            (filter === '전체' || (filter === '확인 후보' ? r.count > 0 : r.status === filter)) &&
            r.name.includes(search),
        )
        .sort((a, b) =>
          sort === '이름순'
            ? a.name.localeCompare(b.name, 'ko')
            : b.count - a.count || (a.minZ ?? Infinity) - (b.minZ ?? Infinity),
        ),
    [regions, filter, search, sort],
  );
  const region = regions.find((r) => r.name === selected);
  return (
    <div className="regional-overview">
      <section className="card region-directory">
        <header>
          <div>
            <span className="eyebrow">COMPARE ALL DISTRICTS</span>
            <h2>
              동별 분석 현황 <span>{shown.length}개 동</span>
            </h2>
          </div>
        </header>
        <div className="directory-filters">
          <input
            aria-label="행정동 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="행정동 검색"
          />
          <select
            aria-label="지역 상태 필터"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            {[
              '전체',
              '확인 후보',
              '신규 후보',
              '연속 후보',
              '판단 보류',
              '자료 없음',
              '기준 미해당',
            ].map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
          <select aria-label="지역 정렬" value={sort} onChange={(e) => setSort(e.target.value)}>
            <option>후보 우선</option>
            <option>이름순</option>
          </select>
        </div>
        <div className="directory-table">
          <table>
            <thead>
              <tr>
                <th>행정동</th>
                <th>분석 상태</th>
                <th>후보 지표</th>
                <th>최저 Robust Z</th>
                <th>근거</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.name} className={r.name === selected ? 'selected' : ''}>
                  <td>
                    <button className="district-link" onClick={() => onSelect(r.name)}>
                      {r.name}
                    </button>
                  </td>
                  <td>
                    <span className={`status-tag ${tone(r.status)}`}>{r.status}</span>
                  </td>
                  <td>{r.count}개</td>
                  <td>{number(r.minZ, 2)}</td>
                  <td>
                    <button
                      className="text-button"
                      aria-label={`${r.name} 근거 보기`}
                      onClick={() => onSelect(r.name)}
                    >
                      보기 →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!shown.length && <p className="empty">검색 조건에 맞는 지역이 없습니다.</p>}
        </div>
        <footer>최저 Z는 정렬 참고값입니다. 지표 묶음의 판정 결과를 함께 확인하세요.</footer>
      </section>
      <section className="card directory-map">
        <header>
          <h2>지역 비교 지도</h2>
          <span className="pill">{month}</span>
        </header>
        <div className="directory-map-body">
          <MissionMap
            flat
            geometry={geometry}
            regions={regions}
            selected={selected}
            onSelect={onSelect}
          />
          {region && (
            <RegionInsight
              region={region}
              city={city}
              month={month}
              onClose={() => onSelect('')}
              onStart={onStart}
              onChat={onChat}
              busy={busy}
            />
          )}
        </div>
        <footer className="hint">
          표 또는 지도에서 동을 선택하면 해당 지역의 근거를 확인합니다.
        </footer>
      </section>
    </div>
  );
}
