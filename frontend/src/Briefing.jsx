import React, { useMemo, useState } from 'react';
import { Icon, EvidenceTable } from './components';
import { areaUnit } from './regionalPresentation.mjs';
import { number } from './api';
import { MissionMap } from './MissionMap';
import ElderlyBackground from './ElderlyBackground';
export { MissionMap } from './MissionMap';

// 종합 현황과 지역 현황은 같은 원자료를 사용하지만 다른 업무를 돕습니다.
// 종합 현황=이번 달 우선 확인 지역을 발견 / 지역 현황=모든 동을 필터링·비교.
export function summarizeRegions(assessment, geometry, city, month, months, structures = []) {
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
      structure: city === '강남구' ? structures.find(r => r.dong_name === unit.n) : null,
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
const STATUS_HELP = {
  '신규 후보': '이번 달 처음 후보 기준에 해당한 동입니다.',
  '연속 후보': '지난달에 이어 이번 달에도 후보 기준에 해당한 동입니다.',
  '변화 후보': '비교 이력은 부족하지만 이번 달 기준에 해당한 동입니다.',
  '판단 보류': '과거 자료가 부족해 판단하지 않은 동입니다.',
  '기준 미해당': '후보 기준에 해당하지 않은 동입니다.',
  '자료 없음': '이번 달 분석 자료가 없는 동입니다.',
};
// 판정 이름만 보고는 뜻을 알기 어려워, 표 위에 짧은 설명을 둡니다.
export function StatusLegend() {
  return <details className="status-legend"><summary>판정은 무슨 뜻인가요?</summary>
    <p>통화·문자·평일 이동·휴일 이동 지표가 평소 흐름과 다른지 봅니다. «후보»는 추가로 확인해 볼 지역이라는 뜻이며, 개인의 고립 여부를 판정하지 않습니다.</p>
    <dl>{Object.entries(STATUS_HELP).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
  </details>;
}

// «보미와 근거 살펴보기»를 누르면 채팅 입력란에 넣어 줄 예시 질문입니다. 동의 판정에 맞춰 바꿉니다.
export function exampleQuestion(region) {
  if (region.count > 0) {
    return `${region.name}이 «${region.status}»로 표시된 근거를 지표별로 설명해 주고, 다음에 확인할 일을 알려 줘`;
  }
  if (region.status === '판단 보류') {
    return `${region.name}이 «판단 보류»인 이유와 추가로 확인해야 할 자료를 알려 줘`;
  }
  return `${region.name}의 이번 달 지표 변화를 요약하고, 후보 기준에 해당하지 않은 이유를 알려 줘`;
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
        <span className={`status-tag ${tone(region.status)}`} title={STATUS_HELP[region.status]}>{region.status}</span>
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
        <p className="empty">이 지역의 실제 분석 자료가 없습니다.</p>
      )}
      <p className="hint">{region.count > 0 ? `과거 흐름과 비교하여 ${region.count}개 지표가 후보 기준에 해당합니다. 아래 지표를 함께 검토하세요.` : region.status === '자료 없음' ? '분석 자료가 없어 판단할 수 없습니다.' : region.pending ? '과거 이력이 부족한 지표가 있어 추가 자료 확인이 필요합니다.' : '현재 후보 기준에 해당하는 지표가 없습니다.'}</p>
      <p className="hint">개인의 고립 판정이 아니며, 계절·행사 영향은 추가 확인이 필요합니다.</p>
      <ElderlyBackground structure={region.structure} city={city} />
      <div className="insight-actions">
        <button className="primary" disabled={busy || !region.rows.length} onClick={onStart}>
          상세 분석·업무 시작
          <Icon name="arrow" size={16} />
        </button>
        <button className="secondary" disabled={!region.rows.length} onClick={() => onChat(region)}>
          보미와 근거 살펴보기
          <Icon name="chat" size={16} />
        </button>
      </div>
    </section>
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
  const unitLabel = areaUnit(city);
  const analyzedCount = regions.filter(r => r.rows.length > 0).length;
  return (
    <div className="regional-overview">
      {/* 동을 고르면 표 자리에 상세가 열립니다. 지도는 가리지 않고 모든 동을 계속 보여 줍니다. */}
      {region ? (
        <section className="card region-directory region-detail">
          <button className="text-button back-to-list" onClick={() => onSelect('')}>← 전체 {unitLabel} 목록</button>
          <RegionInsight region={region} city={city} month={month} onClose={() => onSelect('')} onStart={onStart} onChat={onChat} busy={busy} />
        </section>
      ) : (
      <section className="card region-directory">
        <header>
          <div>
            <span className="eyebrow">COMPARE ALL DISTRICTS</span>
            <h2>
              {unitLabel}별 분석 현황 <span>{shown.length}개 {unitLabel}</span>
            </h2>
          </div>
        </header>
        <p className="hint">전체 {regions.length}개 {unitLabel} 중 분석 자료가 있는 지역 {analyzedCount}개 · {month}</p>
        <StatusLegend />
        <div className="directory-filters">
          <input
            aria-label={`${unitLabel} 검색`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={`${unitLabel} 검색`}
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
              '변화 후보',
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
                <th>{unitLabel}</th>
                <th>분석 상태</th>
                <th>후보 지표</th>
                <th title="과거 흐름에서 얼마나 벗어났는지 나타내는 값입니다. 0에서 멀수록 평소와 다릅니다.">평소 대비 차이(점수)</th>
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
                    <span className={`status-tag ${tone(r.status)}`} title={STATUS_HELP[r.status]}>{r.status}</span>
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
        <footer>‘후보 우선’은 후보 지표가 많은 지역, 그다음 평소와 차이가 큰 지역 순서입니다. 평소 대비 차이는 시·군·구 공통 흐름을 뺀 변화가 과거 변동 폭보다 얼마나 큰지 나타낸 단위 없는 점수로, 동의 지표 중 가장 낮은 값을 보여 줍니다. 음수는 평소보다 줄어든 방향이며 약 -2 이하이면 후보 기준에 가깝습니다.</footer>
      </section>
      )}
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
        </div>
        <footer className="hint">
          표나 지도에서 {unitLabel}을 선택하면 왼쪽에 근거가 열립니다. 이름에 마우스를 올리면 판정이 보입니다.
        </footer>
      </section>
    </div>
  );
}


