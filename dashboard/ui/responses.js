// 지역·성별·연령대별 월간 변화와 서비스 유형 제안. 개인을 추정하지 않습니다.
const GROUP_DATA = BOOT.groupSignals || {isDemo:true, rows:[]};
const GROUP_ROWS = GROUP_DATA.rows;
const RESPONSE_STATUSES = ['미확인','검토 중','지역 현황 확인','프로그램 연계 검토'];
const RESPONSE_PRIORITIES = ['우선 확인','확인 필요','관찰','판단 보류'];
const daysInMonth = month => {const [y,m]=month.split('-').map(Number);return new Date(Date.UTC(y,m,0)).getUTCDate()};
const groupKey = r => encodeURIComponent(JSON.stringify([r.city,r.district,r.gender,r.age,r.month]));
const groupMonths = [...new Set(GROUP_ROWS.map(r=>r.month))].sort();
const completeMonths = groupMonths.filter(m=>GROUP_ROWS.filter(r=>r.month===m).every(r=>r.observedDays===daysInMonth(m)));
const R = {month:completeMonths.at(-1)||groupMonths.at(-1)||'',district:'전체',gender:'전체',age:'전체',priority:'전체',selected:null,statuses:{}};
function changeRate(current, previous){return Number.isFinite(current)&&current>=0&&Number.isFinite(previous)&&previous>0?(current-previous)/previous*100:null}
function assessGroup(row, previous){
    const flow=changeRate(row.flow,previous?.flow), card=changeRate(row.card,previous?.card);
    let reason='';
    if(!previous)reason='전월 자료 없음';
    else if(row.observedDays!==daysInMonth(row.month)||previous.observedDays!==daysInMonth(previous.month))reason='월 집계 미완료';
    else if(!Number.isFinite(row.sampleCount)||!Number.isFinite(previous.sampleCount)||Math.min(row.sampleCount,previous.sampleCount)<30)reason='관측 규모 부족 (30 미만)';
    else if(flow===null||card===null)reason='지표 누락 또는 전월 값 0';
    const priority=reason?'판단 보류':flow<=-15&&card<=-15?'우선 확인':flow<=-10||card<=-10?'확인 필요':'관찰';
    return {...row,previous,flowRate:flow,cardRate:card,priority,reason,key:groupKey(row)};
}
function responseRows(){
    return GROUP_ROWS.filter(r=>r.city===S.city&&r.month===R.month).map(r=>assessGroup(r,GROUP_ROWS.find(p=>p.city===r.city&&p.district===r.district&&p.gender===r.gender&&p.age===r.age&&p.month===prevMonth(r.month))));
}
function filteredResponses(){return responseRows().filter(r=>(R.district==='전체'||r.district===R.district)&&(R.gender==='전체'||r.gender===R.gender)&&(R.age==='전체'||r.age===R.age)&&(R.priority==='전체'||r.priority===R.priority)).sort((a,b)=>RESPONSE_PRIORITIES.indexOf(a.priority)-RESPONSE_PRIORITIES.indexOf(b.priority))}
function responseStatus(r){return R.statuses[r.key]||RESPONSE_STATUSES[0]}
function rateText(value){return value===null?'산출 불가':`${value>0?'+':''}${value.toFixed(1)}%`}
function priorityChip(r){return `<span class="signal-tag p${RESPONSE_PRIORITIES.indexOf(r.priority)}">${r.priority}</span>`}
function recommendations(r){
    if(r.priority==='판단 보류'||r.priority==='관찰')return [];
    const result=[];
    if(r.flowRate<=-10)result.push({title:'사회참여·교류 프로그램',why:'유동인구 감소 신호에 따라 지역 활동과 교류 수요를 확인합니다.',provider:'지역 복지관·주민센터',check:'해당 연령대 참여 가능 여부, 거주지, 운영 일정'});
    if(r.cardRate<=-10)result.push({title:'생활·복지 상담',why:'카드 이용 감소의 원인을 확인하고 생활지원 상담 수요를 검토합니다.',provider:'행정복지센터 복지 상담 창구',check:'상담 후 소득·가구·지원 요건 확인'});
    return result;
}
function responseFilters(){
    const cityRows=GROUP_ROWS.filter(r=>r.city===S.city&&r.month===R.month);
    const select=(name,label,values,value)=>`<label>${label}<select data-response-filter="${name}" aria-label="${label}">${values.map(v=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
    return `<div class="response-filters">${select('month','기준월',groupMonths.slice().reverse(),R.month)}${select('district','행정동',['전체',...new Set(cityRows.map(r=>r.district))],R.district)}${select('gender','성별',['전체',...new Set(cityRows.map(r=>r.gender))],R.gender)}${select('age','연령대',['전체',...[...new Set(cityRows.map(r=>r.age))].sort()],R.age)}${select('priority','확인 우선순위',['전체',...RESPONSE_PRIORITIES],R.priority)}<button class="btn ghost sm" data-response-reset>필터 초기화</button></div>`;
}
function responseIntro(){return `<div class="response-heading"><div><div class="response-eyebrow">지역 변화 모니터링</div><h2>변화를 확인하고, 지역에 필요한 지원을 검토하세요.</h2><p>${R.month?`${esc(prevMonth(R.month))} → ${esc(R.month)} · 전월 대비 일평균 변화율`:'월별 자료 없음'} · 지역 × 성별 × 연령대</p></div><span class="pill warn">${GROUP_DATA.isDemo?'화면 시연용 가상 집계':'월별 집계'}</span></div><div class="response-notice">${GROUP_DATA.isDemo?'수치와 판단 기준은 화면 설계를 위한 예시입니다. 실제 성별·연령대 집계 및 복지사업 정보는 아직 연결되지 않았습니다.':'집단의 변화 신호이며 개인의 고립 여부를 판단하지 않습니다.'}</div>`}
function responseDetail(r){
    if(!r)return '<div class="empty">조건에 맞는 집단이 없습니다. 필터를 조정해 주세요.</div>';
    const recs=recommendations(r);
    const summary=r.reason?`${r.reason}으로 변화에 대한 판단을 보류합니다.`:r.priority==='관찰'?'설정한 감소 기준에 해당하지 않습니다. 월별 변화를 계속 관찰합니다.':`${r.district} ${r.gender} ${r.age} 집단에서 ${[r.flowRate<=-10?`유동인구 ${rateText(r.flowRate)}`:'',r.cardRate<=-10?`카드 이용 ${rateText(r.cardRate)}`:''].filter(Boolean).join(', ')} 변화가 감지되었습니다.`;
    const number=v=>Number.isFinite(v)?v.toLocaleString('ko-KR',{maximumFractionDigits:1}):'자료 없음';
    return `<section class="card response-detail"><header><div><div class="response-eyebrow">선택 집단 상세</div><h2>${esc(r.district)} · ${esc(r.gender)} · ${esc(r.age)}</h2></div>${priorityChip(r)}</header><div class="cbody"><p class="response-summary">${esc(summary)}</p><div class="tblwrap"><table class="tbl"><thead><tr><th>지표</th><th>전월 일평균</th><th>당월 일평균</th><th>변화율</th></tr></thead><tbody>${[['유동인구 (명/일)','flow',r.flowRate],['카드 이용 (건/일)','card',r.cardRate]].map(([name,k,rate])=>`<tr><td>${name}</td><td class="num">${number(r.previous?.[k])}</td><td class="num">${number(r[k])}</td><td class="num">${rateText(rate)}</td></tr>`).join('')}</tbody></table></div><p class="hint">당월 관측 규모 ${number(r.sampleCount)} · 집계 ${r.observedDays}/${daysInMonth(r.month)}일${r.reason?' · 표시 변화율은 참고값이며 우선순위 판정에서 제외':''}</p>
    <div class="response-section-title"><h3>추천 서비스 유형</h3><span class="hint">이용 자격 확인 전 · 검토 제안</span></div>${recs.length?recs.map((s,i)=>`<article class="service-suggestion"><span class="service-index">0${i+1}</span><div><h4>${s.title}</h4><p>${s.why}</p><dl><dt>확인할 기관 유형</dt><dd>${s.provider}</dd><dt>확인 조건</dt><dd>${s.check}</dd></dl><span class="hint">실제 사업명·연락처·신청 경로 연결 예정</span></div></article>`).join(''):`<div class="response-notice">${r.reason?'집계 품질을 확인한 뒤 서비스 추천을 검토하세요.':'현재는 정기 모니터링을 유지합니다.'}</div>`}
    <details class="response-rules"><summary>판단 기준과 함께 확인할 사항</summary><p>시연 기준: 두 지표 모두 15% 이상 감소하면 우선 확인, 하나라도 10% 이상 감소하면 확인 필요입니다. 그 외는 관찰입니다. 관측 규모 30 미만·누락·전월 값 0·미완료 월은 판단 보류합니다.</p><p>변화율 = (당월 일평균 − 전월 일평균) ÷ 전월 일평균 × 100. 계절·명절, 지역 인구 변화, 수집 범위 변경을 함께 확인하세요. 지역 전체 대비 변화와 장기 지속성은 아직 판단에 반영하지 않습니다.</p></details>
    <div class="response-status"><label>담당자 조치 상태<select data-response-status="${r.key}" aria-label="담당자 조치 상태">${RESPONSE_STATUSES.map(s=>`<option ${s===responseStatus(r)?'selected':''}>${s}</option>`).join('')}</select></label><span class="hint">현재 화면에서만 유지 · 새로고침/로그아웃 시 초기화</span></div></div></section>`;
}
function viewUsers(){
    const rows=filteredResponses();if(!rows.some(r=>r.key===R.selected))R.selected=rows[0]?.key||null;
    return responseIntro()+responseFilters()+`<div class="response-metrics">${RESPONSE_PRIORITIES.map((p,i)=>`<div class="card"><span>${p}</span><strong class="num">${rows.filter(r=>r.priority===p).length}<small>개 집단</small></strong><span class="hint">${['두 지표 동반 감소','주요 지표 감소','추이 모니터링','집계 확인 필요'][i]}</span></div>`).join('')}</div><section class="card response-list"><header><h2>집단별 변화 신호</h2><span class="hint">필터 결과 ${rows.length}개 · 우선순위순</span></header><div class="tblwrap"><table class="tbl"><thead><tr><th>지역·대상 집단</th><th>유동인구</th><th>카드 이용</th><th>확인 우선순위</th><th>추천 서비스</th><th>조치 상태</th><th>상세</th></tr></thead><tbody>${rows.map(r=>`<tr class="${r.key===R.selected?'response-selected':''}"><td><b>${esc(r.district)}</b><small class="response-sub">${esc(r.gender)} · ${esc(r.age)}</small></td><td class="num">${rateText(r.flowRate)}</td><td class="num">${rateText(r.cardRate)}</td><td>${priorityChip(r)}</td><td>${recommendations(r).map(s=>s.title).join(' · ')|| (r.reason?'판단 후 검토':'정기 모니터링')}</td><td>${responseStatus(r)}</td><td><button class="btn ghost sm" data-response-select="${r.key}" aria-pressed="${r.key===R.selected}" aria-label="${esc(r.district)} ${esc(r.gender)} ${esc(r.age)} 상세">보기</button></td></tr>`).join('')||'<tr><td colspan="7" class="empty">조건에 맞는 집단이 없습니다.</td></tr>'}</tbody></table></div></section>${responseDetail(rows.find(r=>r.key===R.selected))}`;
}
function viewActions(){const rows=filteredResponses();return responseIntro()+responseFilters()+`<p class="hint">지역·집단 단위의 검토 현황입니다. 상태 변경은 현재 화면에서만 유지됩니다.</p><div class="cols response-board">${RESPONSE_STATUSES.map(status=>{const items=rows.filter(r=>responseStatus(r)===status);return `<section class="col"><h3>${status}<span>${items.length}개</span></h3>${items.map(r=>`<button class="tk response-task" data-response-open="${r.key}"><b>${esc(r.district)}</b><small>${esc(r.gender)} · ${esc(r.age)}</small>${priorityChip(r)}<small>유동 ${rateText(r.flowRate)} · 카드 ${rateText(r.cardRate)}</small></button>`).join('')||'<div class="empty">해당 집단 없음</div>'}</section>`}).join('')}</div>`}
function responseAnswer(){const rows=filteredResponses(),r=rows.find(r=>r.key===R.selected)||rows[0];if(!r)return '현재 조건에 맞는 집단별 자료가 없습니다.';return `${GROUP_DATA.isDemo?'시연용 가상 집계입니다.\n':''}${r.district} ${r.gender} ${r.age}: ${r.priority}.\n유동인구 ${rateText(r.flowRate)}, 카드 이용 ${rateText(r.cardRate)} (전월 대비).\n${r.reason||recommendations(r).map(s=>s.title).join(', ')||'정기 모니터링을 유지합니다.'}`}
listen('click',e=>{if(!S.user)return;const select=e.target.closest('[data-response-select],[data-response-open]');if(select){R.selected=select.dataset.responseSelect||select.dataset.responseOpen;S.view='users';log('조회','집단별 변화 상세');render();root.querySelector('.response-detail')?.scrollIntoView({block:'start',behavior:'smooth'});}if(e.target.closest('[data-response-reset]')){R.district=R.gender=R.age=R.priority='전체';R.selected=null;renderPage();}});
listen('change',e=>{if(!S.user)return;const t=e.target;if(t.matches('[data-response-filter]')){const key=t.dataset.responseFilter;if(!['month','district','gender','age','priority'].includes(key))return;R[key]=t.value;if(key==='month')R.district=R.gender=R.age=R.priority='전체';R.selected=null;renderTop();renderPage();}if(t.matches('[data-response-status]')&&RESPONSE_STATUSES.includes(t.value)&&responseRows().some(r=>r.key===t.dataset.responseStatus)){R.statuses[t.dataset.responseStatus]=t.value;log('설정',`집단 조치 상태: ${t.value}`);renderPage();}});
