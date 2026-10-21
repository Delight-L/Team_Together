import DetectionCaseSelector from './DetectionCaseSelector';
import React from 'react';
import { useChartProgress } from './ChartMotion';
import { Icon } from './components';
const fmt = (v) =>
  Number.isFinite(v) ? v.toLocaleString('ko-KR', { maximumFractionDigits: 2 }) : '자료 없음';
export const signalState = (absolute, local) =>
  absolute && local ? 'both' : absolute ? 'absolute' : local ? 'local' : 'none';
const signalLabel = {
  absolute: '평소보다 큰 감소',
  local: '공통 흐름을 고려해도 두드러진 감소',
  both: '두 비교 모두에서 감소',
  none: '탐지 기준 미해당',
};
export function signalExplanation(absolute, local, city) {
  return absolute && local
    ? '평소보다 크게 감소했고, 공통 흐름을 고려해도 감소가 두드러집니다.'
    : local
      ? `${city} 같은 연령대의 공통 흐름을 고려해도 이 지역의 감소가 두드러집니다.`
      : '이 지역·연령대의 감소가 평소보다 크게 나타났습니다.';
}
export function SignalBadges({ absolute, local }) {
  const state = signalState(absolute, local);
  return (
    <span className="ev-badges">
      <span className={`ev-badge ${state}`}>{signalLabel[state]}</span>
    </span>
  );
}
function ScorePlot({ row, path, state }) {
  const progress = useChartProgress();
  const z = row[path + '_rz'],
    threshold = row[path + '_threshold'];
  if (!Number.isFinite(z) || !Number.isFinite(threshold))
    return <p className="ev-missing">탐지 점수·기준값 자료 없음</p>;
  const min = Math.min(z, threshold, 0) - Math.max(1, Math.abs(Math.min(z, threshold)) * 0.15),
    max = Math.max(0, z, threshold) + 0.5;
  const x = (v) => 35 + ((v - min) / (max - min)) * 430,
    color = state === 'both' ? '#c53d55' : path === 'local' ? '#0f766e' : '#946200',
    distance = z - threshold;
  return (
    <>
      <div
        className="ev-chart-space"
        role="img"
        aria-label={`${row.metric_label}: 탐지 점수 ${z}, 기준 ${threshold}, 차이 ${distance}`}
        style={{ '--ev-signal-color': color }}
      >
        <span className="ev-chart-threshold" style={{ left: `${x(threshold) / 5}%`, color }}>
          탐지 기준 {fmt(threshold)}
        </span>
        <span className="ev-chart-zero" style={{ left: `${x(0) / 5}%` }}>
          평소 수준 0
        </span>
        <span className="ev-chart-observation" style={{ left: `${x(z) / 5}%`, color }}>
          이번 관측 {fmt(z)}
        </span>
        <i className="ev-shape-track" />
        <i className="ev-shape-threshold" style={{ left: `${x(threshold) / 5}%` }} />
        <i
          className="ev-shape-distance"
          style={{
            left: `${Math.min(x(threshold) + (x(z) - x(threshold)) * progress, x(threshold)) / 5}%`,
            width: `${(Math.abs(x(z) - x(threshold)) * progress) / 5}%`,
          }}
        />
        <i className="ev-shape-zero" style={{ left: `${x(0) / 5}%` }} />
        <i className="ev-shape-observation" style={{ left: `${x(z) / 5}%`, opacity: progress }} />
      </div>
      <p className="ev-score-detail">
        기준과의 차이 <b style={{ color }}>{fmt(distance)}</b> ·{' '}
        {z <= threshold ? '기준선보다 낮음' : '기준선보다 높음'}
      </p>
    </>
  );
}
export default function DetectionEvidence({
  rows,
  group,
  detection,
  onBack,
  caseOptions,
  onCaseChange,
}) {
  const payload = detection?.payload || {};
  const domains = [
    ['communication', '통신', ['call_contacts', 'text_contacts']],
    ['mobility', '이동', ['weekday_move_count', 'weekend_move_count']],
  ]
    .map(([key, label, metrics]) => {
      const domainRows = rows.filter((r) => metrics.includes(r.metric));
      const absolute =
        payload[key + '_absolute_signal'] ?? domainRows.some((r) => r.absolute_signal);
      const local = payload[key + '_local_signal'] ?? domainRows.some((r) => r.local_signal);
      return { key, label, rows: domainRows, absolute, local, state: signalState(absolute, local) };
    })
    .filter((d) => d.state !== 'none' && d.rows.length);
  const single = domains.length === 1;
  return (
    <article
      className={`ev-screen ${single ? 'ev-single signal-' + domains[0].state : 'ev-multiple'}`}
    >
      <div className="ev-case-header">
        <header className="ev-heading gd-case-title">
          <h2>
            {group.district} · {group.age}
          </h2>
          {domains.map((d) => (
            <span key={d.key} className={`gd-domain-chip signal-${d.state}`}>
              <Icon name={d.key === 'communication' ? 'chat' : 'chart'} size={20} />
              {d.key === 'communication' ? '전화·문자 연락' : '평일·휴일 이동'} 감소 탐지
            </span>
          ))}
          <div className="gd-case-actions">
            {caseOptions && (
              <DetectionCaseSelector items={caseOptions} selected={group} onSelect={onCaseChange} />
            )}
            {onBack && (
              <button className="gd-evidence-back" onClick={onBack}>
                ← 탐지 현황 보기
              </button>
            )}
          </div>
        </header>
        {single && (
          <div className="gd-path-explanation">
            <SignalBadges absolute={domains[0].absolute} local={domains[0].local} />
            <p>{signalExplanation(domains[0].absolute, domains[0].local, group.city)}</p>
          </div>
        )}
      </div>
      {!single && domains.length > 1 && <h3>통신과 이동의 탐지 근거</h3>}
      <p className="ev-intro">변화율(%)은 실제 변화, 탐지 점수는 평소 대비 이례적인 정도입니다.</p>
      {!domains.length && <p>탐지 신호가 성립하지 않았습니다.</p>}
      {domains.map((d) => (
        <section key={d.key} className={`ev-domain signal-${d.state}`} data-domain={d.key}>
          {!single && (
            <header className="ev-domain-heading">
              <h3>{d.label}</h3>
              <SignalBadges absolute={d.absolute} local={d.local} />
            </header>
          )}
          <section className="ev-actual">
            <div>
              <h4>
                <b>1</b> 실제 변화
              </h4>
              <p>탐지 현황에서 본 수치입니다.</p>
            </div>
            <div className="ev-actual-cards">
              {d.rows.map((r) => {
                const log = payload[r.metric + '_log_change'];
                const value = Number.isFinite(log) ? Math.expm1(log) * 100 : r.change_pct;
                return (
                  <article key={r.metric}>
                    <h4>{r.metric_label.replace(group.age + ' ', '')}</h4>
                    <strong>
                      {Number.isFinite(value)
                        ? `${fmt(Math.abs(value))}% ${value < 0 ? '감소' : value > 0 ? '증가' : '변화 없음'}`
                        : '자료 없음'}
                    </strong>
                  </article>
                );
              })}
            </div>
          </section>
          <div className={`ev-comparisons ${d.absolute && d.local ? 'ev-two-paths' : ''}`}>
            {[d.absolute && 'absolute', d.local && 'local'].filter(Boolean).map((path) => (
              <section key={path} className={`ev-comparison ${path}`}>
                <h4>
                  <b>2</b> {path === 'local' ? '공통 흐름을 고려한 비교' : '평소와 비교'}
                </h4>
                <p>
                  {path === 'local'
                    ? `${group.city} 같은 연령대의 공통 변화를 뺀 뒤, 이 동·연령대의 과거 조정된 변화와 비교합니다.`
                    : '같은 동·연령대에서 평소 나타나던 변화보다 얼마나 크게 감소했는지 확인합니다.'}
                </p>
                {path === 'local' && (
                  <div className="ev-bridge">
                    <span>우리 동의 변화</span>
                    <i>→</i>
                    <span>{group.city} 공통 변화 반영</span>
                    <i>→</i>
                    <span>조정 후 탐지 점수</span>
                  </div>
                )}
                <div className="ev-plots">
                  {d.rows.map((r) => (
                    <article key={r.metric}>
                      <h4>{r.metric_label.replace(group.age + ' ', '')}</h4>
                      <ScorePlot row={r} path={path} state={d.state} />
                    </article>
                  ))}
                </div>
              </section>
            ))}
          </div>
          <section className="ev-interpretation">
            <h4>
              <b>3</b> 해석 결과
            </h4>
            <strong>
              {d.state === 'both'
                ? `${d.label}은 평소보다 크게 감소했고, ${group.city}의 공통 흐름을 고려해도 감소가 두드러집니다.`
                : d.local
                  ? `${group.city}의 공통 흐름을 고려해도 ${d.label}의 감소가 평소보다 두드러집니다.`
                  : `${d.label}의 두 지표 모두 평소 변화 범위를 벗어나 감소했습니다.`}
            </strong>
          </section>
        </section>
      ))}
    </article>
  );
}
