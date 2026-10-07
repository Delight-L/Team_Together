// 2024–2025 원본 재집계의 행정동·월별 변화. 기존 시연 점수와 분리한다.
const DET = BOOT.detection || {rows:[],threshold:0,source:''};
const POLICY_PLANS = BOOT.policyPlans || [];
const VALID = BOOT.validation || {records:[],source:'',asOf:''};
const POLICY_AUDIT = BOOT.recommendationAudit || {decisions:[]};
const DET_MONTHS = [...new Set(DET.rows.map(r=>r.month))].sort();
const D = {month:DET_MONTHS.at(-1)||'',dong:'전체'};
const detNumber = (v,d=3) => Number.isFinite(v)?`${v>=0?'+':''}${v.toFixed(d)}`:'자료 없음';
const detStage = r => r.stage==='우선 검토'?0:r.stage==='전년 동월 변화'?1:2;
function detectionRows(){return DET.rows.filter(r=>r.month===D.month).sort((a,b)=>detStage(a)-detStage(b)||b.deltas.low_both-a.deltas.low_both)}
function policyDecisions(row){return row?POLICY_AUDIT.decisions.filter(d=>d.month===row.month&&d.dongCode===row.dongCode):[]}
function policyCandidates(row){
 return policyDecisions(row).filter(d=>d.matched).map(d=>{
  const p=POLICY_PLANS.find(plan=>plan.name===d.planName);
  return {...p,why:`${row.dong} ${row.month}의 소통 적음 비율 ${detNumber(row.deltas.low_comm)}%p${p.signal==='소통·외출'?`·평일 외출 적음 비율 ${detNumber(row.deltas.low_weekday)}%p` : ''} 변화와 사업 계획의 지역·기간을 대조했습니다.`};
 });
}
function viewResponseIntegrated(){
 if(D.dong==='전체')D.dong=detectionRows().find(r=>r.stage!=='조건 미충족')?.dong||'전체';
 return viewDetection(true);
}
function detectionAnswer(q=''){
 if(S.city!=='강남구')return '2024–2025년 동별 실측 자료는 현재 강남구만 연결되어 있습니다.';
 if(/2026\s*년|2026[-./]/.test(q))return '실측 탐지와 사업 계획의 비교 기간은 2025년입니다. 2026년 자료를 2025년 결과로 합치지 않습니다.';
 const namedDong=[...new Set(DET.rows.map(r=>r.dong))].sort((a,b)=>b.length-a.length).find(n=>q.includes(n));
 if(namedDong==='개포3동')return '개포3동은 원자료의 0값 확인 전까지 동별 탐지와 사업 후보 검토에서 제외했습니다. 행정동 명칭·코드와 집계 원본을 먼저 확인해야 합니다.';
 const monthMatch=q.match(/2025\s*년\s*(0?[1-9]|1[0-2])\s*월/)||q.match(/2025[-./](0?[1-9]|1[0-2])(?=\D|$)/);
 const shortMonth=q.match(/(?:^|\D)(0?[1-9]|1[0-2])\s*월/);
 const month=monthMatch?`2025-${monthMatch[1].padStart(2,'0')}`:shortMonth?`2025-${shortMonth[1].padStart(2,'0')}`:D.month;
 const dong=namedDong||D.dong;
 const row=DET.rows.find(r=>r.month===month&&r.dong===dong);
 if(!row)return `${month}에 확인할 행정동을 선택하거나 질문에 동 이름을 적어 주세요. 예: 세곡동 2025년 7월 지원사업 근거는?`;
 const decisions=policyDecisions(row), plans=policyCandidates(row), excluded=decisions.filter(d=>!d.matched);
 const actual=VALID.records.find(r=>r.month===row.month&&r.dongCode===row.dongCode);
 const lines=[
  `${row.dong} ${row.month} · 탐지 단계: ${row.stage}`,
  `전년 동월 대비 결합 비율 ${detNumber(row.deltas.low_both)}%p, 소통 적음 ${detNumber(row.deltas.low_comm)}%p, 평일 외출 적음 ${detNumber(row.deltas.low_weekday)}%p, 휴일 외출 적음 ${detNumber(row.deltas.low_holiday)}%p.`,
  `탐지 자료: ${DET.source}. 개인의 고립 여부를 판정한 결과는 아닙니다.`,
 ];
 if(row.month==='2025-12')lines.push('주의: 2025년 12월은 21개 동 모두에서 통화·이동 감소가 나타나 공통 원인을 확인해야 합니다.');
 lines.push(plans.length?'2025년 계획사업 검토 후보:':'2025년 계획사업 검토 후보 없음.');
 for(const p of plans)lines.push(`· ${p.name}: ${p.why}\n  문서: ${p.sourceFile} ${p.sourcePage}쪽.\n  현장 확인: ${p.check} 실제 운영·대상·접수 가능 여부는 ${p.agency}에 확인하세요.`);
 if(excluded.length){lines.push('사업 후보 제외 이유:');for(const d of excluded)lines.push(`· ${d.planName}: ${d.reasons.join('; ')}. 근거: ${d.sourceFile} ${d.sourcePage}쪽.`)}
 if(!actual)lines.push('결과보고 실적: 검증자료 대기. 같은 동·월의 발굴·상담·서비스 연계 실적이 없어 탐지 정확도나 사업 효과를 계산할 수 없습니다.');
 else lines.push(`결과보고 실적: 신규 발굴 ${actual.newlyFound??'미제공'}, 상담 완료 ${actual.counseling??'미제공'}, 서비스 연계 ${actual.serviceLinked??'미제공'} (${actual.unit}). 출처: ${actual.documentNumber}, 기준기간 ${actual.period}. 탐지 결과와 현장 실적을 나란히 확인하세요.`);
 return lines.join('\n');
}
function validationPanel(row){
 const actual=VALID.records.find(r=>row&&r.month===row.month&&r.dongCode===row.dongCode);
 const count=VALID.records.length;
 const intro=`<section class="card response-list detection-validation"><header><h2>2025년 결과보고 실적 대조</h2><span class="hint">동·월별 근거 ${count}/252건 확보</span></header><div class="cbody">`;
 if(!row)return intro+'<div class="response-notice">행정동을 선택하면 같은 월·동의 발굴·상담·지원 실적 확보 여부를 확인합니다.</div></div></section>';
 if(!actual)return intro+`<p><b>${esc(row.dong)} ${esc(row.month)}: 검증자료 대기</b></p><p class="hint">탐지 단계 ${esc(row.stage)}와 비교할 같은 월·동의 결과보고 실적이 아직 없습니다. 발굴·상담·서비스 연계 수치를 0으로 해석하거나 탐지 정확도를 계산하지 않습니다.</p><p class="hint">필요한 근거: 실적 문서번호, 실적 기준월, 단위(명/가구), 중복 처리 기준.</p></div></section>`;
 const fields=[['신규 발굴',actual.newlyFound],['상담 완료',actual.counseling],['서비스 연계',actual.serviceLinked],['방문 확인',actual.visits]];
 return intro+`<p><b>${esc(row.dong)} ${esc(row.month)}: 같은 동·월의 실적 확인</b></p><div class="response-metrics">${fields.map(([label,value])=>`<div class="card"><span>${label}</span><strong>${value===null?'미제공':value.toLocaleString()}</strong></div>`).join('')}</div><p class="hint">출처 ${esc(actual.documentNumber)} · 기준기간 ${esc(actual.period)} · 단위 ${esc(actual.unit)} · 중복 처리 ${esc(actual.dedupRule)}</p><p class="hint">탐지 단계와 현장 실적을 나란히 보여줍니다. 이 수치만으로 탐지 정확도나 사업 효과를 판정하지 않습니다.</p></div></section>`;
}
function viewDetection(responseMode=false){
 if(S.city!=='강남구')return '<div class="response-notice">실제 동별 변화 자료는 현재 강남구 2024–2025년만 연결되어 있습니다.</div>';
 const rows=detectionRows(), shown=responseMode?rows:rows.filter(r=>D.dong==='전체'||r.dong===D.dong);
 const count=s=>rows.filter(r=>r.stage===s).length;
 const select=`<div class="response-filters"><label>기준월<select data-detection-filter="month">${DET_MONTHS.slice().reverse().map(m=>`<option value="${esc(m)}" ${m===D.month?'selected':''}>${esc(m)}</option>`).join('')}</select></label><label>행정동<select data-detection-filter="dong"><option>전체</option>${rows.map(r=>r.dong).sort().map(n=>`<option ${n===D.dong?'selected':''}>${esc(n)}</option>`).join('')}</select></label></div>`;
 const summary=`<div class="response-metrics"><div class="card"><span>비교한 동</span><strong>${rows.length}개</strong></div><div class="card"><span>우선 검토</span><strong>${count('우선 검토')}개</strong></div><div class="card"><span>전년 동월 변화</span><strong>${count('전년 동월 변화')}개</strong></div><div class="card"><span>결합 비율 기준</span><strong>${DET.threshold.toFixed(3)}%p</strong></div></div>`;
 const notice=`<div class="response-notice">같은 동의 2025년과 2024년 같은 달을 비교했습니다. 소통·외출·결합 변화가 모두 악화하면 ‘전년 동월 변화’, 결합 비율 증가가 전체 비교의 절댓값 중앙값 이상이면 ‘우선 검토’입니다. 현장 확인 순서이며 개인 고립 판정이 아닙니다. 개포3동은 원본 0값 확인 전 제외했습니다.</div>`;
 const caution=D.month==='2025-12'?'<div class="response-notice">2025년 12월에는 21개 동 모두에서 통화대상자 수와 평일·휴일 이동 횟수가 감소했습니다. 공통 변화의 원인을 확인해야 합니다.</div>':'';
 const table=`<section class="card response-list"><header><h2>동별 탐지 결과</h2><span class="hint">결합 변화는 %p</span></header><div class="tblwrap"><table class="tbl"><thead><tr><th>행정동</th><th>탐지 단계</th><th>2024년 결합 비율</th><th>2025년 결합 비율</th><th>결합 변화</th><th>소통 적음 변화</th><th>평일 외출 적음 변화</th><th>휴일 외출 적음 변화</th></tr></thead><tbody>${shown.map(r=>`<tr><td><b>${esc(r.dong)}</b><br><button class="btn ghost sm" data-detection-open="${esc(r.dong)}">검토</button></td><td>${esc(r.stage)}</td><td class="num">${r.joint2024.toFixed(3)}%</td><td class="num">${r.joint2025.toFixed(3)}%</td><td class="num">${detNumber(r.deltas.low_both)}</td><td class="num">${detNumber(r.deltas.low_comm)}</td><td class="num">${detNumber(r.deltas.low_weekday)}</td><td class="num">${detNumber(r.deltas.low_holiday)}</td></tr>`).join('')}</tbody></table></div></section>`;
 const selected=rows.find(r=>r.dong===D.dong), candidates=policyCandidates(selected);
 const excluded=policyDecisions(selected).filter(d=>!d.matched);
 const exclusions=selected&&excluded.length?`<details class="card response-list" ${candidates.length?'':'open'}><summary>사업 후보 제외 근거 ${excluded.length}건</summary><div class="cbody">${excluded.map(d=>`<p><b>${esc(d.planName)}</b> · ${d.reasons.map(esc).join('; ')}<br><span class="hint">${esc(d.sourceFile)} · ${esc(d.sourcePage)}쪽</span></p>`).join('')}</div></details>`:'';
 const cards=D.dong==='전체'?'<div class="response-notice">동을 선택하거나 표의 ‘검토’를 누르면 해당 동의 관련 사업 계획을 자동으로 대조합니다.</div>':`<section class="card response-list detection-review"><header><h2>${esc(D.dong)} · 관련 지원사업 검토</h2><span class="hint">공식 문서의 2025년 계획 · 운영 여부 미확인</span></header><div class="cbody"><p class="hint">행정동·월·변화 지표로만 후보를 찾았습니다. 주민의 개인 자격이나 실제 접수 가능 여부는 판단하지 않습니다.</p>${candidates.length?candidates.map((p,i)=>`<article class="service-suggestion"><span class="service-index">0${i+1}</span><div><h4>${esc(p.name)}</h4><p>${esc(p.why)}</p><dl><dt>계획 대상</dt><dd>${esc(p.target)}</dd><dt>계획 기간</dt><dd>${esc(p.planPeriod)}</dd><dt>담당 기관</dt><dd>${esc(p.agency)}</dd><dt>지원 내용</dt><dd>${esc(p.support)}</dd><dt>확인 절차</dt><dd>${esc(p.check)}</dd><dt>문서 근거</dt><dd>${esc(p.sourceFile)} · ${esc(p.sourcePage)}쪽</dd></dl><span class="hint">${esc(p.status)} · 담당 기관에 실제 운영·대상·접수 가능 여부 확인 필요</span></div></article>`).join(''):'<div class="response-notice">이 동·월의 탐지 단계 또는 지역·기간 조건에 맞는 계획사업 후보가 없습니다.</div>'}</div></section>`;
 const trend=D.dong==='전체'?'':`<section class="card response-list"><header><h2>${esc(D.dong)} 월별 결합 비율 변화</h2></header><div class="tblwrap"><table class="tbl"><thead><tr><th>월</th><th>2024년</th><th>2025년</th><th>변화(%p)</th><th>단계</th></tr></thead><tbody>${DET.rows.filter(r=>r.dong===D.dong).sort((a,b)=>a.month.localeCompare(b.month)).map(r=>`<tr><td>${esc(r.month)}</td><td class="num">${r.joint2024.toFixed(3)}%</td><td class="num">${r.joint2025.toFixed(3)}%</td><td class="num">${detNumber(r.deltas.low_both)}</td><td>${esc(r.stage)}</td></tr>`).join('')}</tbody></table></div></section>`;
 return `<div class="response-heading"><div><div class="response-eyebrow">실측 자료 · 행정동 단위</div><h2>${responseMode?'현장 대응·지원사업 검토':'전년 동월 활동·소통 변화'}</h2><p>${esc(DET.source)}</p></div></div>${responseMode?'<div class="response-notice">이 화면은 2025년 실측 변화와 공식 계획문서를 사용합니다. 종합 현황·동별 분석의 2026년 시연용 점수와 합산하거나 같은 시점의 결과로 해석하지 마세요.</div>':''}${select}${summary}${notice}${caution}${table}${cards}${exclusions}${validationPanel(selected)}${trend}`;
}
listen('change',e=>{const t=e.target;if(!S.user||!t.matches('[data-detection-filter]'))return;D[t.dataset.detectionFilter]=t.value;if(t.dataset.detectionFilter==='month')D.dong='전체';renderTop();renderPage()});
listen('click',e=>{const button=e.target.closest('[data-detection-open]');if(!S.user||!button)return;D.dong=button.dataset.detectionOpen;renderPage();root.querySelector('.detection-review')?.scrollIntoView({block:'start',behavior:'smooth'});});
