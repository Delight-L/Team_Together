import React from 'react';
const fmt=v=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:2}):'자료 없음';
export function SignalBadges({absolute,local}) {return <span className="ev-badges">{absolute&&<span className="ev-badge absolute">평소보다 큰 감소</span>}{local&&<span className="ev-badge local">공통 흐름을 고려해도 두드러진 감소</span>}{!absolute&&!local&&<span className="ev-badge">탐지 기준 미해당</span>}</span>;}
function ScorePlot({row,path}) {
 const z=row[path+'_rz'], threshold=row[path+'_threshold'];
 if(!Number.isFinite(z)||!Number.isFinite(threshold))return <p className="ev-missing">탐지 점수·기준값 자료 없음</p>;
 const min=Math.min(z,threshold,0)-Math.max(1,Math.abs(Math.min(z,threshold))*.15),max=Math.max(0,z,threshold)+.5;
 const x=v=>35+(v-min)/(max-min)*430, color=path==='local'?'#7c3aed':'#e45d70',distance=z-threshold;
 return <><div className="ev-chart-space" role="img" aria-label={`${row.metric_label}: 탐지 점수 ${z}, 기준 ${threshold}, 차이 ${distance}`} style={{'--ev-signal-color':color}}>
 <span className="ev-chart-threshold" style={{left:`${x(threshold)/5}%`,color}}>탐지 기준 {fmt(threshold)}</span>
 <span className="ev-chart-zero" style={{left:`${x(0)/5}%`}}>평소 수준 0</span>
 <span className="ev-chart-observation" style={{left:`${x(z)/5}%`,color}}>이번 관측 {fmt(z)}</span>
 <i className="ev-shape-track"/>
 <i className="ev-shape-threshold" style={{left:`${x(threshold)/5}%`}}/>
 <i className="ev-shape-distance" style={{left:`${Math.min(x(z),x(threshold))/5}%`,width:`${Math.abs(x(z)-x(threshold))/5}%`}}/>
 <i className="ev-shape-zero" style={{left:`${x(0)/5}%`}}/>
 <i className="ev-shape-observation" style={{left:`${x(z)/5}%`}}/>
 </div><p className="ev-score-detail">기준과의 차이 <b style={{color}}>{fmt(distance)}</b> · {z<=threshold?'기준선보다 낮음':'기준선보다 높음'}</p></>;

}
export default function DetectionEvidence({rows,group,detection,onBack}) {
 const absolute=rows.some(r=>r.absolute_signal), local=rows.some(r=>r.local_signal);
 const selected=rows.some(r=>r.is_risk_signal)?rows.filter(r=>r.is_risk_signal):rows;
 const paths=[absolute&&'absolute',local&&'local'].filter(Boolean);
 if(!paths.length)paths.push('absolute');
 const payload=detection?.payload||{};
 return <article className="ev-screen"><header className="ev-heading"><div><h2>{group.district} · {group.age} <small>{group.month}</small></h2><SignalBadges absolute={absolute} local={local}/></div>{onBack&&<button className="gd-evidence-back" onClick={onBack}>← 변화 요약으로</button>}</header>
 <h3>{local?'강남구의 공통 흐름을 고려해도 감소가 탐지됐어요':'평소보다 큰 감소가 탐지됐어요'}</h3>
 <p className="ev-intro">변화율(%)은 실제 변화, 탐지 점수는 {local?'공통 흐름을 조정한 뒤의 ':''}평소 대비 이례적인 정도입니다.</p>
 <section className="ev-actual"><div><h4><b>1</b> 실제 변화</h4><p>변화 요약에서 본 수치입니다.</p></div><div className="ev-actual-cards">{selected.map(r=>{const log=payload[r.metric+'_log_change'];const value=Number.isFinite(log)?Math.expm1(log)*100:r.change_pct;return <article key={r.metric} className={r.local_signal?'ev-actual-local':'ev-actual-absolute'}><h4>{r.metric_label.replace(group.age+' ','')}</h4><strong>{Number.isFinite(value)?`${fmt(Math.abs(value))}% ${value<0?'감소':value>0?'증가':'변화 없음'}`:'자료 없음'}</strong></article>;})}</div></section>
 {paths.map(path=><section key={path} className={`ev-comparison ${path}`}><h4><b>2</b> {path==='local'?'공통 흐름을 고려한 비교':'평소와 비교'}</h4><p>{path==='local'?`${group.city} 같은 연령대의 공통 변화를 뺀 뒤, 이 동·연령대의 평소 변화와 비교합니다.`:'같은 동·연령대에서 평소 나타나던 변화보다 얼마나 크게 감소했는지 확인합니다.'}</p>
 {path==='local'&&<div className="ev-bridge"><span>우리 동의 변화</span><i>→</i><span>{group.city} 공통 변화 반영</span><i>→</i><span>조정 후 탐지 점수</span></div>}
 <div className="ev-plots">{selected.filter(r=>paths.length===1||r[path+'_signal']).map(r=><article key={r.metric}><h4>{r.metric_label.replace(group.age+' ','')}</h4><ScorePlot row={r} path={path}/></article>)}</div><p className="ev-axis">{path==='local'?'공통 흐름 조정 후 ':''}평소 대비 이례적인 정도(robust Z) · 감소율(%)과 다른 척도입니다.</p>
 </section>)}
 <section className={`ev-interpretation ${local?'local':'absolute'}`}><h4><b>3</b> 해석 결과</h4><strong>{local?`${group.city}의 공통 흐름을 고려해도 이 지역의 감소가 평소보다 두드러집니다.`:absolute?'이번 감소는 평소 변화 범위를 벗어나 탐지됐습니다.':'탐지 신호가 성립하지 않았습니다.'}</strong></section>
 <p className="ev-footnote">전화·문자 또는 평일·휴일 이동의 두 지표를 함께 판정합니다. 개인의 고립 여부를 뜻하지 않습니다.</p>
 </article>;
}
