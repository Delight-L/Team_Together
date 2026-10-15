export const REGION_AGES=['20대','30대','40대','50대','60대 이상'];
export const CLUSTER_COLORS={0:'#5890ec',1:'#54c7b6',2:'#f3c768'};
export const CONSUMPTION_DOMAINS=[['A_외식카페','외식·카페'],['B_여가운동','여가·운동'],['C_대면생활서비스','대면 생활서비스'],['D_생활필수','생활필수'],['E_의료건강','의료·건강']];
export const SURVEY_METRICS=[['no_support_emotion','힘들 때 이야기할 사람 없음'],['no_support_sick','아플 때 도움받을 사람 없음'],['loneliness_outside_agree','가족 외 관계에서 외로움을 느낌']];
const AGE_CODES={'20대':'20s','30대':'30s','40대':'40s','50대':'50s','60대 이상':'60plus'};
export const contextPeriods=data=>[...new Set((data?.typologies||[]).map(r=>r.period))].sort();
export const consumptionPeriods=data=>[...new Set((data?.consumption||[]).map(r=>r.period))].sort();
export const periodLabel=p=>/^\d{4}H[12]$/.test(p||'')?`${p.slice(0,4)}년 ${p.endsWith('1')?'상':'하'}반기`:/^\d{4}Q[1-4]$/.test(p||'')?`${p.slice(0,4)}년 ${p.slice(-1)}분기`:p;
export function consumptionRows(data,code,age,period){
 const rows=(data?.consumption||[]).filter(r=>r.code===code&&r.period===period&&r.age.replace(/\s/g,'')===age.replace(/\s/g,''));
 return CONSUMPTION_DOMAINS.map(([domain,label])=>({domain,label,...rows.find(r=>r.domain===domain)}));
}
export function surveyRows(data,age,year){
 const rows=(data?.surveys||[]).filter(r=>r.year===year&&r.age_band===AGE_CODES[age]);
 return SURVEY_METRICS.map(([metric,label])=>({metric,label,gangnam:rows.find(r=>r.metric===metric&&r.district==='gangnam')?.value??null,seoul:rows.find(r=>r.metric===metric&&r.district==='seoul')?.value??null}));
}
export function boundaryCenter(feature){
 const polygons=feature.geometry.type==='MultiPolygon'?feature.geometry.coordinates:[feature.geometry.coordinates];
 const centers=polygons.map(p=>{const ring=p[0];let area=0,x=0,y=0;ring.forEach(([px,py],i)=>{const [qx,qy]=ring[(i+1)%ring.length];const k=px*qy-qx*py;area+=k;x+=(px+qx)*k;y+=(py+qy)*k;});return {area:Math.abs(area),center:[x/(3*area),y/(3*area)]};});
 return centers.sort((a,b)=>b.area-a.area)[0].center;
}
