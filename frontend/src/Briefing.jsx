import React, { useMemo, useState } from 'react';
import { Icon, EvidenceTable } from './components';
import { number } from './api';
import { MissionMap } from './MissionMap';
export { MissionMap } from './MissionMap';

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

export { CaseBriefing as Briefing, BriefingStats } from './CaseBriefing';

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


