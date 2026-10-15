import React from 'react';
import { ratioPercent, areaUnit } from './regionalPresentation.mjs';

export default function ElderlyBackground({ structure, compact = false, city }) {
  if (!structure) return null;
  const p = structure.payload || {};
  const rate = ratioPercent(p.elderly_living_alone_rate_65plus);
  const populationPeriod = p.denominator_reference?.replace(/^(\d{4})Q([1-4])$/, '$1년 $2분기') || '자료 없음';
  return <div className={`gd-senior${compact ? ' gd-senior-compact' : ''}`}><span>{compact ? '65세 이상 등록인구 중 독거노인 비율' : `65세 이상 등록인구 중 독거노인 비율 · ${areaUnit(city)} 전체`}</span>
    <strong>{rate === null ? '자료 없음' : `${rate.toFixed(1)}%`}</strong>
    <p className="hint gd-stat-period"><span>독거노인 통계: {p.elder_year ? `${p.elder_year}년 연간` : '자료 없음'}</span><span>인구 기준: {populationPeriod}</span></p>
    <p className="hint" hidden={compact}>연간 독거노인 수 ÷ 같은 해 4분기 65세 이상 등록인구. 월별 변화나 개인의 고립 판정이 아닙니다.</p>
  </div>;
}
