// Shared decorative relief; the original administrative boundaries are preserved.
function districtTile(unit, color, attribute, label) {
  const selected = unit.n === S.sel;
  const count=regionRows(unit.n).filter(r=>r.is_risk_signal).length;
  const callout=count ? `<g class="region-map-callout"><line x1="${unit.cx}" y1="${unit.cy-10}" x2="${unit.cx+42}" y2="${unit.cy-40}"/><rect x="${unit.cx+40}" y="${unit.cy-67}" width="115" height="43" rx="9"/><text x="${unit.cx+50}" y="${unit.cy-49}">${esc(unit.n)}</text><text x="${unit.cx+50}" y="${unit.cy-32}">확인 후보 ${count}개</text></g>` : "";
  return `<g class="district-tile ${selected ? 'is-selected' : ''}" ${attribute} tabindex="0" role="button" aria-label="${esc(label)}"><title>${esc(label)}</title><path class="district-hit" d="${unit.d}"/><path class="district-base" d="${unit.d}" transform="translate(0 12)"/><g class="district-top"><defs><linearGradient id="face-${unit.n}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${color}"/><stop offset="1" stop-color="${color}" stop-opacity=".8"/></linearGradient></defs><path class="mission-district" d="${unit.d}" fill="url(#face-${unit.n})"/><text class="actual-map-label" x="${unit.cx}" y="${unit.cy}" text-anchor="middle">${esc(unit.n)}</text>${callout}</g></g>`;
}
function reliefMap(geometry, tiles, label) {
  return `<svg viewBox="-35 -35 ${geometry.w + 70} ${geometry.h + 70}" role="group" aria-label="${esc(label)}"><g transform="skewX(-4) scale(1 .94)">${tiles}</g></svg>`;
}
listen('keydown', event => {
  const tile = event.target.closest?.('[data-overview-district]');
  if (tile && S.user && ['Enter', ' '].includes(event.key)) {
    event.preventDefault();
    showRegionPreview(tile.dataset.overviewDistrict);
  }
});

listen('pointerover',event=>{
  const tile=event.target.closest?.('.district-tile');
  if(tile && tile.parentElement.lastElementChild!==tile) tile.parentElement.appendChild(tile);
});

function regionRows(name) {
 return S.city==='강남구'?(BOOT.db1?.assessment||[]).filter(r=>r['기준연월']===S.month&&r['행정동명']===name):[];
}
function showRegionPreview(name) {
 if(!S.user)return;
 const rows=regionRows(name),signals=rows.filter(r=>r.is_risk_signal),dialog=$('#region-dialog');
 $('#region-dialog-content').innerHTML=`<header class="region-modal-head"><div><span class="login-eyebrow">${esc(S.city)} · ${esc(S.month)}</span><h2 id="region-dialog-title">${esc(name)}</h2></div><button class="iconbtn" data-close-region aria-label="지역 상세 닫기">×</button></header><div class="region-modal-body"><div class="region-modal-summary"><b>${signals.length?'확인 후보 '+signals.length+'개':rows.length?'탐지 기준에 해당하는 후보 없음':'선택 지역의 자료 없음'}</b><p>저장된 분석 결과를 살펴보고 필요한 지역의 업무를 시작하세요.</p></div>${rows.length?`<div class="tblwrap"><table class="tbl"><thead><tr><th>변화 지표</th><th>전월 변화</th><th>상대 로그 변화 ×100</th><th>Robust Z</th><th>상태</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.metric_label)}</td><td>${Number.isFinite(r.change_pct)?r.change_pct.toFixed(1)+'%':'자료 없음'}</td><td>${Number.isFinite(r.relative_change_pp)?r.relative_change_pp.toFixed(1):'산출 불가'}</td><td>${Number.isFinite(r.risk_robust_z)?r.risk_robust_z.toFixed(2):'산출 불가'}</td><td>${!r.has_enough_history?'이력 부족 · 판단 보류':r.is_risk_signal?'확인 후보':'기준 미해당'}</td></tr>`).join('')}</tbody></table></div>`:''}<p class="hint">판정은 전월 변화율 하나가 아닌 공통 변화 제거 후의 Robust Z와 지표 묶음을 사용합니다. 지역 집계자료의 변화이며 개인의 고립 여부를 판정하지 않습니다. 후보가 없어도 일부 지표는 이력 부족으로 판단을 보류할 수 있습니다.</p><div class="region-modal-actions"><button class="btn ghost" data-close-region>닫기</button>${rows.length?`<button class="btn" data-start-region="${esc(name)}">상세 분석·업무 시작 →</button>`:''}</div></div>`;
 if(!dialog.open)dialog.showModal();
}
listen('click',event=>{
 if(event.target.closest?.('[data-close-region]'))$('#region-dialog').close();
 const start=event.target.closest?.('[data-start-region]');
 if(start){$('#region-dialog').close();openRegionAnalysis(start.dataset.startRegion);}
 if(event.target===$('#region-dialog'))$('#region-dialog').close();
});
function viewBriefing() {
 const overview=viewActualOverview();if(!overview.includes('overview-grid'))return overview;
 const all=BOOT.db1.assessment.filter(r=>r['기준연월']===S.month),priorMonth=analysisMonths().filter(m=>m<S.month).at(-1),prior=BOOT.db1.assessment.filter(r=>r['기준연월']===priorMonth);
 const names=[...new Set(all.filter(r=>r.is_risk_signal).map(r=>r['행정동명']))],old=new Set(prior.filter(r=>r.is_risk_signal).map(r=>r['행정동명']));
 const comparable=prior.some(r=>r.has_enough_history)&&all.some(r=>r.has_enough_history);
 const kpis=[['신규 확인 후보',comparable?names.filter(n=>!old.has(n)).length+'곳':'비교 보류','이전 분석월 대비 신규 후보'],['연속 확인 후보',comparable?names.filter(n=>old.has(n)).length+'곳':'비교 보류','이전·현재 분석월 모두 후보'],['이력 확인 필요',new Set(all.filter(r=>!r.has_enough_history).map(r=>r['행정동명'])).size+'곳','일부 지표의 판단 보류']];
 return `<div class="briefing-kpis">${kpis.map(([t,v,n],i)=>`<section class="card briefing-kpi tone-${i}"><span class="briefing-symbol">${['↗','▥','⌛'][i]}</span><div><span>${t}</span><strong>${v}</strong><small>${n}</small></div></section>`).join('')}</div><div class="briefing-map">${overview}</div><section class="card monthly-changes"><header><h2>이번 달 주요 변화</h2><button class="btn ghost sm" data-view="regions">지역 현황 펼쳐 보기 →</button></header><div class="monthly-change-grid">${all.filter(r=>r.is_risk_signal).slice(0,3).map(r=>`<button class="monthly-change" data-overview-district="${esc(r['행정동명'])}"><small>${esc(r['행정동명'])}</small><b>${esc(r.metric_label)}</b><strong>${Number.isFinite(r.change_pct)?r.change_pct.toFixed(1)+'%':'산출 불가'}</strong><span>전월 대비 · 근거 확인 →</span></button>`).join('')||'<p class="hint">현재 기준을 통과한 변화 후보가 없습니다.</p>'}</div></section>`;
}
