import React from 'react';
import RegionalFollowup from './RegionalFollowup';
import { signalCount, relevantScores } from './ageSignals.mjs';

// 종합 현황과 지역 현황은 같은 원자료를 사용하지만 다른 업무를 돕습니다.
// 종합 현황은 탐지 사례를 확인하고, 지역 현황은 지도에서 선택한 사례의 이후 흐름을 추적합니다.
export function summarizeRegions(assessment, geometry, city, month, months, structures = []) {
  const current = city === '강남구' ? assessment.filter((r) => r['기준연월'] === month) : [];
  const previous = months.filter((m) => m < month).at(-1);
  const old = city === '강남구' ? assessment.filter((r) => r['기준연월'] === previous) : [];
  return (geometry?.units || []).map((unit) => {
    const rows = current.filter((r) => r['행정동명'] === unit.n);
    const earlier = old.filter((r) => r['행정동명'] === unit.n);
    const count = signalCount(rows);
    const comparable =
      rows.some((r) => r.has_enough_history) && earlier.some((r) => r.has_enough_history);
    const pending = rows.length > 0 && rows.some((r) => !r.has_enough_history);
    const status = !rows.length
      ? '자료 없음'
      : count > 0
        ? comparable
          ? earlier.some((r) => r.is_risk_signal && rows.some(c => c.is_risk_signal && (!c.age_band || c.age_band === r.age_band)))
            ? '연속 후보'
            : '신규 후보'
          : '변화 후보'
        : pending
          ? '판단 보류'
          : '기준 미해당';
    const zValues = relevantScores(rows);
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

export function RegionalOverview(props) {
  return <RegionalFollowup {...props} summarize={summarizeRegions}/>;
}
