import React from 'react';
import { useChartProgress } from './ChartMotion';
import ElderlyBackground from './ElderlyBackground';
import { householdParts } from './regionalPresentation.mjs';

const colors = ['#1769ff', '#5798ff', '#94c8ff', '#18b59c'];
export default function RegionContextCards({ structure, group, survey }) {
  const parts = householdParts(structure?.payload);
  const progress = useChartProgress();
  return (
    <div className="gd-context-cards">
      <article>
        <header>
          <h3>{group.district} 가구 구성 비율</h3>
          <div className="gd-household-legend">
            {parts.map((p, i) => (
              <span key={p.label}>
                <i style={{ background: colors[i] }} />
                {p.label}
              </span>
            ))}
          </div>
        </header>
        <div className="gd-household-section">
          {parts.length ? (
            <div
              className="gd-households"
              style={{ clipPath: `inset(0 ${100 * (1 - progress)}% 0 0)` }}
              role="img"
              aria-label={parts.map((p) => `${p.label} 가구 ${p.value.toFixed(1)}%`).join(', ')}
            >
              {parts.map((p, i) => (
                <span key={p.label} style={{ flex: p.value, background: colors[i] }}>
                  {p.value.toFixed(1)}%
                </span>
              ))}
            </div>
          ) : (
            <p className="gd-empty">비교 가능한 가구 구성 자료가 없습니다.</p>
          )}
        </div>
        <div className="gd-population-grid">
          <ElderlyBackground structure={structure} compact />
          <div className="gd-senior gd-survey-context">
            <span>힘들 때 이야기할 사람이 없는 비율</span>
            <strong>
              {Number.isFinite(survey?.value) ? `${(survey.value * 100).toFixed(1)}%` : '자료 없음'}
            </strong>
            {Number.isFinite(survey?.value) && (
              <div className="gd-share-track">
                <i style={{ width: `${survey.value * 100 * progress}%` }} />
              </div>
            )}
            <p className="hint">
              {survey
                ? `${group.city} ${group.age} · ${survey.year}년 서울서베이`
                : '해당 지역·연령의 조사자료 없음'}
            </p>
          </div>
        </div>
        <p className="gd-context-note">
          ⓘ 가구·독거노인 자료는 행정동, 관계망 조사는 {group.city} 기준입니다.
        </p>
      </article>
    </div>
  );
}
