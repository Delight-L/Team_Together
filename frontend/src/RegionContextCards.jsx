import React from 'react';
import ElderlyBackground from './ElderlyBackground';
import { householdParts, ratioPercent, comparisonRows, signedBar, areaUnit } from './regionalPresentation.mjs';

const percent = n => Number.isFinite(n) ? `${n > 0 ? '+' : ''}${n.toFixed(2)}%` : '자료 없음';
export default function RegionContextCards({ structure, detection, group, survey, backgroundOnly = false }) {
  const unit = areaUnit(group.city);
  const parts = householdParts(structure?.payload);
  const senior = ratioPercent(structure?.payload?.resident_ratio_65_plus);
  const period = (structure?.payload?.context_period || structure?.source_file)?.match(/(20\d{2})H([12])/);
  const rows = comparisonRows(detection?.payload);
  const extent = Math.max(1, ...rows.flatMap(r => [r.local, r.common]).filter(Number.isFinite).map(Math.abs));
  return <div className="gd-context-cards">
    <article><header><h3>{backgroundOnly ? `${group.district} 가구 구성 비율` : '어떤 지역인가요?'}</h3><span hidden={backgroundOnly} className="gd-badge">읍·면·동 전체{period ? ` · ${period[1]}년 ${period[2] === '1' ? '상' : '하'}반기` : ' · 기준기간 확인 필요'}</span></header>{!backgroundOnly && <p>가구 구성과 주민 특성을 살펴봅니다.</p>}
      <div className="gd-household-section">{!backgroundOnly && <h4>가구 구성 비율 <small>(읍·면·동 전체)</small></h4>}
      {parts.length ? <><div className="gd-households" role="img" aria-label={parts.map(p => `${p.label} 가구 ${p.value.toFixed(1)}%`).join(', ')}>{parts.map((p, i) => <span key={p.label} style={{ flex: p.value, background: ['#1769ff', '#5798ff', '#94c8ff', '#18b59c'][i] }}>{p.value.toFixed(1)}%</span>)}</div><div className="gd-household-legend">{parts.map((p, i) => <span key={p.label}><i style={{ background: ['#1769ff', '#5798ff', '#94c8ff', '#18b59c'][i] }}/>{p.label} {p.value.toFixed(1)}%</span>)}</div></> : <p className="gd-empty">비교 가능한 가구 구성 자료가 없습니다.</p>}
      </div><div className="gd-population-grid"><ElderlyBackground structure={structure} compact /><div className="gd-senior gd-survey-context"><span>힘들 때 이야기할 사람이 없는 비율</span><strong>{Number.isFinite(survey?.value) ? `${(survey.value*100).toFixed(1)}%` : '자료 없음'}</strong>{Number.isFinite(survey?.value) && <div className="gd-share-track"><i style={{width:`${survey.value*100}%`}}/></div>}<p className="hint">{survey ? `${group.city} ${group.age} · ${survey.year}년 서울서베이` : '해당 지역·연령의 조사자료 없음'}</p></div></div>
      <p className="gd-context-note">ⓘ 가구·독거노인 자료는 행정동, 관계망 조사는 {group.city} 기준입니다.</p>
    </article>
    {!backgroundOnly && <article><header><h3>이 연령대에도 변화가 있나요?</h3><span className="gd-badge">{group.age} · 성별 통합 · {group.month}</span></header><p>{detection ? `지난달 대비 변화 · ${group.city} 같은 연령대의 공통 흐름과 비교합니다.` : '이 지역의 통신·이동 변화 분석 자료는 아직 연결되지 않았습니다.'}</p>
      {detection && <><div className="gd-compare-legend"><span>● {group.district}</span><span>● {group.city} 공통 변화</span></div>
      {rows.map(r => <div className="gd-compare" key={r.label}><h4>{r.label}</h4>{[['local', group.district], ['common', group.city]].map(([key, label]) => <div className={`gd-compare-row ${key}`} key={key}><span>{label}</span><div className="gd-signed-track"><i style={signedBar(r[key], extent)}/></div><b>{percent(r[key])}</b></div>)}</div>)}
      <div className="gd-axis-label">← 감소 <span>0</span> 증가 →</div><p className="gd-context-note">ⓘ {group.city} 공통 변화는 같은 연령대 동별 로그 변화량의 중앙값입니다. 통신 판정은 성별 통합이며 개인의 고립 판정이 아닙니다.</p></>}
    </article>}
  </div>;
}
