export const TRACKING_AGES=['20대','30대','40대','50대','60대 이상'];
export const DOMAINS=[
 {key:'communication',label:'통신',metrics:[['call_contacts','전화 연락','#2878ef'],['text_contacts','문자 연락','#09a4ac']]},
 {key:'mobility',label:'이동',metrics:[['weekday_move_count','평일 이동','#2878ef'],['weekend_move_count','휴일 이동','#f18143']]},
];
export function pathState(signal={}) {return signal.absolute&&signal.local?'both':signal.absolute?'absolute':signal.local?'local':'none';}
export function eventsFor(tracking,district,age,endMonth) {
 return (tracking?.events||[]).filter(e=>e.district===district&&(!age||e.age===age)&&e.signalMonth<=endMonth)
  .sort((a,b)=>a.signalMonth.localeCompare(b.signalMonth));
}
export function trackingSeries(event,endMonth,scope='raw') {
 if(!event||event.signalMonth>endMonth)return [];
 const points=event.points.filter(p=>p.month<=endMonth);
 const keys=DOMAINS.flatMap(d=>d.metrics.map(m=>m[0]));
 const reference=Object.fromEntries(keys.map(k=>[k,points.some(p=>Number.isFinite(p[scope]?.[k]))?100:null]));
 return [{month:event.referenceMonth,values:reference},...points.map(p=>({month:p.month,values:Object.fromEntries(keys.map(k=>[k,Number.isFinite(p[scope]?.[k])?100+p[scope][k]:null]))}))];
}
export function latestObservation(event,endMonth) {return event?.points.filter(p=>p.month<=endMonth).at(-1)||null;}
export const stateText={both_below_reference:'두 지표 모두 기준 미달',recovered_to_reference:'두 지표 모두 기준 이상',mixed_recovery:'두 지표 흐름이 다름',unavailable:'비교 자료 부족'};
export function stateLabel(value) {return stateText[value]||'비교 자료 부족';}
