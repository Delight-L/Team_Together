import React, { useEffect, useId, useMemo, useState } from 'react';
import { Icon } from './components';
import { number } from './api';
import { briefingStats, rankedCases, casePage, caseMetrics, metricSeries, caseNarrative, caseQuestion, caseQuestionDraft, statusTone } from './briefingData';

export function BriefingStats(props) {
  return <div className="case-stats" aria-label="이번 달 분석 요약">
    {briefingStats(props.regions, props.assessment, props.city, props.month, props.months).map((stat) =>
      <section className={`case-stat ${stat.tone}`} key={stat.label} title={stat.value === null ? '현재 또는 이전 분석월의 비교 이력이 부족합니다.' : stat.label}>
        <span className="case-stat-icon"><Icon name={stat.icon} size={22} /></span>
        <div><span>{stat.label}</span><strong>{stat.value ?? '—'}<small>{stat.value === null ? '비교 보류' : '곳'}</small></strong></div>
      </section>)}
  </div>;
}

function FolderIcon({ number: ordinal, status }) {
  return <span className={`case-folder-icon ${statusTone(status)}`} aria-hidden="true">
    <span>{ordinal ? String(ordinal).padStart(2, '0') : <Icon name="report" size={21} />}</span>
  </span>;
}

function ValueChart({ series, label, color }) {
  const id = useId().replace(/:/g, '');
  const [hovered, setHovered] = useState(null);
  const valid = series.points.filter((point) => Number.isFinite(point.value));
  if (!valid.length) return <div className="case-chart-empty">이 기간의 그래프 자료가 없습니다.</div>;
  const minimum = Math.min(0, ...valid.map((point) => point.value));
  const maximum = Math.max(0, ...valid.map((point) => point.value));
  const range = Math.max(maximum - minimum, 1);
  const step = 10 ** Math.floor(Math.log10(range)) / 2;
  const low = Math.floor(minimum / step) * step;
  const high = Math.max(low + step, Math.ceil(maximum / step) * step);
  const x = (index) => 45 + index / Math.max(1, series.points.length - 1) * 335;
  const y = (value) => 117 - (value - low) / (high - low) * 78;
  const segments = [];
  let segment = [];
  series.points.forEach((point, index) => {
    if (Number.isFinite(point.value)) segment.push({ ...point, index });
    else if (segment.length) { segments.push(segment); segment = []; }
  });
  if (segment.length) segments.push(segment);
  const latest = series.points.findLastIndex((point) => Number.isFinite(point.value));
  const active = hovered ?? latest;
  const activePoint = series.points[active];
  const tickLabel = (value) => Number(value.toFixed(Math.abs(high) >= 10 ? 0 : 1)).toLocaleString('ko-KR');
  return <>
    <svg className="case-value-chart" viewBox="0 0 420 145" preserveAspectRatio="xMidYMid meet" role="img"
      aria-label={`${label} 최근 6개월 ${series.raw ? '월별 지표값' : '전월 변화율'} 그래프 (${series.unit})`}
      onMouseLeave={() => setHovered(null)}>
      <defs><linearGradient id={`case-area-${id}`} x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity="0.12" /><stop offset="100%" stopColor={color} stopOpacity="0" />
      </linearGradient></defs>
      {[low, (low + high) / 2, high].map((value, index) => <g key={index}>
        <line x1="45" x2="391" y1={y(value)} y2={y(value)} stroke="#e8edf5" />
        <text x="34" y={y(value) + 4} textAnchor="end">{tickLabel(value)}{series.raw ? '' : '%'}</text>
      </g>)}
      {series.points.map((point, index) => <g key={point.month}>
        <line x1={x(index)} x2={x(index)} y1="39" y2="117" stroke="#eff2f7" />
        <text x={x(index)} y="140" textAnchor="middle">{Number(point.month.slice(5))}월</text>
      </g>)}
      {segments.map((points, index) => {
        const path = points.map((point, i) => `${i ? 'L' : 'M'}${x(point.index)},${y(point.value)}`).join(' ');
        return <g key={index}><path d={`${path} L${x(points.at(-1).index)},117 L${x(points[0].index)},117 Z`} fill={`url(#case-area-${id})`} />
          <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></g>;
      })}
      {series.points.map((point, index) => Number.isFinite(point.value) && <circle key={point.month}
        cx={x(index)} cy={y(point.value)} r={active === index ? 5 : 4} fill={active === index ? 'white' : color}
        stroke={active === index ? color : 'white'} strokeWidth="2" tabIndex="0"
        aria-label={`${point.month}, ${point.value.toFixed(1)}${series.unit}`}
        onMouseEnter={() => setHovered(index)} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)}>
        <title>{point.month} · {point.value.toFixed(1)}{series.unit}</title>
      </circle>)}
      {activePoint && Number.isFinite(activePoint.value) && <g aria-hidden="true" className="case-chart-bubble">
        <rect x={Math.min(344, Math.max(43, x(active) - 29))} y={Math.max(3, y(activePoint.value) - 33)} width="62" height="23" rx="6" fill={color} />
        <text x={Math.min(375, Math.max(74, x(active) + 2))} y={Math.max(18, y(activePoint.value) - 17)} textAnchor="middle" fill="white">
          {activePoint.value.toFixed(1)}{series.raw ? '' : '%'}
        </text>
      </g>}
    </svg>
    <table className="case-sr-only"><caption>{label} 최근 6개월, {series.unit}</caption><tbody>
      {series.points.map((point) => <tr key={point.month}><th>{point.month}</th><td>{Number.isFinite(point.value) ? point.value.toFixed(1) : '자료 없음'}</td></tr>)}
    </tbody></table>
  </>;
}

function MetricCard({ row, assessment, region, month, index }) {
  const series = useMemo(() => metricSeries(assessment, region, row.metric_label, month), [assessment, region, row.metric_label, month]);
  const color = index === 0 ? '#ff4778' : '#246bff';
  const difference = Number.isFinite(row.change_pct) ? `${row.change_pct > 0 ? '+' : ''}${row.change_pct.toFixed(1)}%` : '—';
  return <article className={`case-metric ${index === 0 ? 'rose' : 'sky'}`}>
    <header><div className="case-metric-icon"><Icon name={row.metric_label.includes('이동') ? index === 0 ? 'services' : 'briefcase' : 'phone'} size={25} /></div>
      <div><h3>{row.metric_label}<span className="case-help" title="전월 대비 변화율입니다. 후보 판정은 공통 변화 보정 및 두 지표의 동시 신호를 함께 사용합니다."><Icon name="help" size={14} /></span></h3>
        <strong>{difference}<span className="case-direction" aria-label={row.change_pct < 0 ? '감소' : row.change_pct > 0 ? '증가' : '변화 없음'}>
          {Number.isFinite(row.change_pct) && row.change_pct !== 0 && <svg width="31" height="27" viewBox="0 0 31 27" aria-hidden="true">
            <path d={row.change_pct < 0 ? 'M3 5 12 15 19 10 28 22M19 22h9v-9' : 'M3 22 12 12 19 17 28 5M19 5h9v9'} fill="none" stroke="currentColor" strokeWidth="2.5" />
          </svg>}
        </span></strong>
      </div><span className="case-comparison">전월 대비</span>
    </header>
    <ValueChart series={series} label={row.metric_label} color={color} />
    <footer><span>{series.raw ? `월별 지표값 (${series.unit})` : '전월 변화율 (%)'} · 최근 6개월</span>
      <span>Robust Z <b>{number(row.risk_robust_z, 2)}</b><span className={row.is_risk_signal ? 'signal' : ''}>{row.is_risk_signal ? '확인 후보' : row.has_enough_history ? '기준 미해당' : '판단 보류'}</span></span>
    </footer>
  </article>;
}

export function CaseBriefing({ regions, assessment, city, month, selected, onSelect, onInspect, onStart, onAsk, busy }) {
  const ordered = useMemo(() => rankedCases(regions), [regions]);
  const region = ordered.find((item) => item.name === selected) || ordered[0];
  const position = region ? ordered.findIndex((item) => item.name === region.name) : -1;
  const metrics = useMemo(() => caseMetrics(region), [region]);
  const scope = `${city}/${month}`;
  const [pagination, setPagination] = useState(() => ({ scope, page: Math.max(0, Math.floor(position / 7)) }));
  // 기준월이 바뀌면 후보가 모인 첫 페이지부터 표시합니다.
  const directory = casePage(ordered, pagination.scope === scope ? pagination.page : 0);
  useEffect(() => {
    if (pagination.scope !== scope) setPagination({ scope, page: 0 });
  }, [scope, pagination.scope]);
  const changePage = (page) => setPagination({ scope, page });
  const selectFromDirectory = (name) => {
    changePage(Math.floor(ordered.findIndex((item) => item.name === name) / 7));
    onSelect(name);
  };
  useEffect(() => { if (region && region.name !== selected) onSelect(region.name); }, [region?.name, selected, onSelect]);

  if (!region) return <section className="case-no-data"><Icon name="report" size={34} /><h2>아직 연결된 분석 결과가 없습니다</h2>
    <p>{city} · {month || '기준월 미선택'}</p><p>이 지역의 실제 분석 자료가 연결되면 조사 브리핑과 월별 그래프를 표시합니다.</p></section>;
  return <div className="briefing-case-view">
    <section className="case-board" aria-label="이번 달 복지 미션 브리핑">
      <article className="case-document" aria-label={`${region.name} 분석 브리핑`}>
        <div className="case-tab">CASE <b>{String(position + 1).padStart(2, '0')}</b></div><span className="case-paperclip" aria-hidden="true" />
        <div className="case-paper">
          <div className="case-document-caption">복지탐정 <span>/</span> {region.count > 0 ? '이번 달 주요 조사 대상' : region.pending ? '분석 이력 확인 대상' : '이번 달 참고 지역'}</div>
          <header className="case-title-row"><span className="case-clipboard"><Icon name="clipboard" size={31} /></span>
            <h2>{region.name}</h2><span className={`status-tag ${statusTone(region.status)}`}>{region.status}</span>
            <span className="case-evidence-count">{region.count > 0 ? `${region.count}개 지표에서 변화 후보 감지` : region.pending ? '비교 이력 확인 필요' : '현재 탐지 기준 미해당'}</span>
          </header>
          <p className="case-narrative">{caseNarrative(region, metrics)}</p>
          <div className="case-metrics">{metrics.map((row, index) => <MetricCard key={`${region.name}/${row.metric_label}/${month}`}
            row={row} assessment={assessment} region={region.name} month={month} index={index} />)}</div>
          <div className="case-investigation"><span className="case-question-icon"><Icon name="bulb" size={27} /></span>
            <div><span>함께 살펴볼 질문</span><h3>{caseQuestion(region, month, metrics)}</h3>
              <p>주변 지역의 흐름과 생활 여건을 함께 살펴보고, 필요한 지원을 검토해요.</p></div>
            <button className="primary" onClick={() => onAsk(region.name, caseQuestionDraft(region, city, month, metrics))}>
              <Icon name="sparkle" size={17} />AI에게 질문하기<Icon name="arrow" size={17} />
            </button>
          </div>
          <footer className="case-document-footer"><p>지역 집계자료이며 개인의 고립 판정이 아닙니다. 원천 지표는 최근 3개월 평균 성격을 갖습니다.</p>
            <div><button className="text-button" onClick={() => onInspect(region.name)}>전체 근거 살펴보기 <Icon name="arrow" size={14} /></button>
              <button className="text-button" disabled={busy} onClick={onStart}>분석 확인·업무 시작 <Icon name="arrow" size={14} /></button></div>
          </footer>
        </div>
      </article>
      <aside className="case-directory" aria-label="이번 달 지역별 조사 파일">
        <header><span>조사 파일</span><small>후보 {ordered.filter((item) => item.count > 0).length} · 전체 {ordered.length}</small></header>
        <div className="case-directory-list" style={{ '--case-count': directory.items.length }}>{directory.items.map((item) => {
          const ordinal = ordered.indexOf(item) + 1;
          return <button key={item.name} className={`case-directory-item ${item.name === region.name ? 'active' : ''}`}
            aria-pressed={item.name === region.name} aria-label={`${item.name} 분석 브리핑 보기`} onClick={() => onSelect(item.name)}>
            <FolderIcon number={ordinal} status={item.status} /><span className="case-directory-label"><b>{item.name}<span className="case-help" title={item.count > 0 ? '분석 규칙을 통과한 지역의 변화 후보입니다.' : item.pending ? '비교 이력 확인이 필요합니다.' : '현재 탐지 기준에 해당하는 후보는 없습니다.'}><Icon name="help" size={14} /></span></b>
              <span><span className={`status-tag ${item.count || item.pending ? statusTone(item.status) : 'quiet'}`}>{item.count || item.pending ? item.status : '참고 지역'}</span>
                <small>{item.count ? `${item.count}개 지표` : item.pending ? '이력 확인' : '후보 없음'}</small></span>
            </span>
          </button>;
        })}</div>
        <nav className="case-pagination" aria-label="조사 파일 페이지">
          <button aria-label="이전 지역 목록" disabled={directory.page === 0} onClick={() => changePage(directory.page - 1)}>‹</button>
          <span aria-live="polite">{directory.start + 1}–{directory.start + directory.items.length} / {ordered.length}개 지역</span>
          <button aria-label="다음 지역 목록" disabled={directory.page + 1 === directory.totalPages} onClick={() => changePage(directory.page + 1)}>›</button>
        </nav>
        <label className="case-all-regions">다른 지역의 근거 보기<select aria-label="브리핑 지역 선택" value={region.name} onChange={(event) => selectFromDirectory(event.target.value)}>
          {ordered.map((item) => <option key={item.name} value={item.name}>{item.name} · {item.status}</option>)}
        </select></label>
        <p className="case-directory-note">후보·판단 보류 지역을 먼저 표시합니다. 참고 지역은 조사 후보로 판정된 지역이 아닙니다.</p>
      </aside>
    </section>
  </div>;
}
