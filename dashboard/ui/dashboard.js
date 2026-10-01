// 파트 4~10. 대시보드의 화면 생성 및 사용자 동작

const $=s=>root.querySelector(s);
const ACC=BOOT.accounts;
const S={user:null,city:Object.keys(GEO)[0],view:'dash',mode:'month',date:fmtD(END),month:MONTHS[MONTHS.length-1],sel:null,band:null,
 side:root.clientWidth>=860,chat:root.clientWidth>=1180,W:DEFW.slice(),logTab:'전체',zoom:false};
const LOGS=[];
function stamp(d){const p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`}
function log(type,detail,ok=true,who){const u=who||S.user;LOGS.unshift({t:stamp(new Date()),id:u?u.id:'-',org:u?u.org:'-',type,detail,ok})}
(function seed(){const rows=[['gangnam01','강남구','접속','로그인',1],['gangnam01','강남구','조회','강남구 · 일 · 2026-09-19 위험 지도',1],['gangnam01','강남구','질의','가장 위험한 동은?',1],
 ['chuncheon01','춘천시','접속','로그인',1],['chuncheon01','춘천시','조회','집단별 위험 신호 목록',1],['gangnam01','강남구','접속','로그인 실패 (비밀번호 불일치)',0],
 ['admin','전체 관리자','접속','로그인',1],['admin','전체 관리자','설정','위험도 가중치 열람',1],['chuncheon01','춘천시','질의','신북읍 위험 요인 알려줘',1],['gangnam01','강남구','접속','로그아웃',1]];
 const base=new Date('2026-09-20T09:00:00');rows.forEach((r,i)=>{const d=new Date(base.getTime()+i*37*60000);LOGS.push({t:stamp(d),id:r[0],org:r[1],type:r[2],detail:r[3],ok:!!r[4]})});LOGS.reverse()})();

const IC={
 dash:'<rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/>',
 bar:'<path d="M5 20V11M12 20V4M19 20v-6"/>',
 users:'<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c2 .7 3.3 2.4 3.6 5.2"/>',
 check:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/>',
 db:'<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
 sliders:'<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
 log:'<path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z"/><path d="M9 12h6M9 15h4"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h16"/>',
 chat:'<path d="M4 5h16v11H9l-5 4z"/>',
 out:'<path d="M9 4H5v16h4M16 8l4 4-4 4M20 12H9"/>',
 send:'<path d="M4 12l16-8-6 16-3-6.5z"/>',
 prev:'<path d="M15 5l-7 7 7 7"/>',next:'<path d="M9 5l7 7-7 7"/>',x:'<path d="M6 6l12 12M18 6L6 18"/>'};
const ic=(n,s=20)=>`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n]}</svg>`;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const f1=v=>Number.isFinite(v)?v.toFixed(1):'—';
const dl=d=>!Number.isFinite(d)?'<span class="flat">비교 자료 없음</span>':Math.abs(d)<0.05?'<span class="flat">― 0.0</span>':d>0?`<span class="up">▲ ${f1(d)}</span>`:`<span class="down">▼ ${f1(-d)}</span>`;
const dtxt=d=>!Number.isFinite(d)?'비교 자료 없음':Math.abs(d)<0.05?'변화 없음':d>0?`▲ ${f1(d)} 상승`:`▼ ${f1(-d)} 하락`;
const perLabel=()=>S.mode==='day'?'7일 전':'전월';
const periodLabel=()=>S.mode==='day'?S.date:S.month.replace('-','년 ')+'월';
const modeLabel=()=>S.mode==='day'?'일':'월';

/* ---- 스냅샷 ---- */

// ---------- 데이터 조회: 선택 기간의 5개 요인 → 가중 점수 → 이전 대비 변화 ----------
function snap(city){city=city||S.city;const key=S.mode==='day'?S.date:S.month;
 const rows=GEO[city].units.map(x=>{const f=factorsAt(city,x.n,S.mode,key);const s=scoreOf(f,S.W);const p=prevScore(city,x.n,S.mode,key,S.W);
  return {n:x.n,d:x.d,cx:x.cx,cy:x.cy,a:x.a,f,s,p,delta:Number.isFinite(s)&&Number.isFinite(p)?s-p:null,b:bandOf(s)}}).filter(r=>Number.isFinite(r.s));
 return rows}
function topFac(r,k=2){const c=r.f.map((v,i)=>[i,v*S.W[i]]).sort((a,b)=>b[1]-a[1]).slice(0,k);return c.map(x=>FN[x[0]])}
function hints(r){const h=[],f=r.f;
 if(f[0]>=60&&f[1]>=60)h.push('유동인구와 카드 결제가 함께 줄었어요. 해당 지역의 성별·연령대별 변화와 집계 조건을 확인하세요.');
 if(f[3]>=60&&f[4]>=55)h.push('고령 비율이 높고 복지 서비스 연계가 비어 있어요. 복지관·통장 연계를 검토하세요.');
 if(f[2]>=60)h.push('1인 가구 비율이 높아요. 비대면 안부 확인 채널을 함께 열어 두세요.');
 if(r.delta>=4)h.push(`${perLabel()}보다 빠르게 올랐어요. 원인 지표부터 확인하세요.`);
 if(!h.length)h.push('특이 요인이 두드러지지 않아요. 정기 모니터링을 유지하세요.');
 return h.slice(0,2)}

/* ---- 화면 조각 ---- */

// ---------- 왼쪽 메뉴: 그룹·아이콘·표시 이름을 변경할 위치 ----------
function menuDef(){return [
 {g:'',items:[['dash','dash','대시보드'],['actions','check','위기 관리 보드'],['analysis','bar','지역 탐색'],['users','users','복지 자원 연계'],['reports','log','보고서 작성'],['data','db','데이터 연계 관리']]},
 {g:'설정·운영',items:[['settings','sliders','위험도 기준'],...(S.user.admin?[['logs','log','접속·조회 로그']]:[])]}]}
const TITLES={dash:'대시보드',analysis:'지역 탐색',users:'복지 자원 연계',actions:'위기 관리 보드',reports:'보고서 작성',data:'데이터 연계 관리',settings:'위험도 기준',logs:'접속·조회 로그'};

// ---------- 사이드바: 236px 너비, 접으면 64px ----------
function renderSide(){
 let h=`<div class="sidehead"><button class="iconbtn" data-act="side" aria-label="메뉴 접기/펴기" aria-expanded="${S.side}">${puzzleIcon()}</button><span class="brand">복지탐정 AI<small>지역의 이야기를 찾아<br>필요한 자원으로 연결합니다.</small></span></div><div class="sidenav">`;
 menuDef().forEach(g=>{h+=`<div class="glabel">${g.g}</div>`;g.items.forEach(m=>{h+=`<button class="mi" data-view="${m[0]}" ${S.view===m[0]?'aria-current="page"':''} title="${m[2]}">${ic(m[1])}<span class="mlabel">${m[2]}</span>${m[3]?`<span class="mtag">${m[3]}</span>`:''}</button>`})});
 h+=`</div><div class="sidefoot">${esc(S.user.org)} · ${esc(S.user.id)}</div>`;$('#side').innerHTML=h;
 $('#app').classList.toggle('collapsed',!S.side)}

// ---------- 상단: 페이지 제목, 지자체 탭, 집계 기준, 챗봇 버튼 ----------
function renderTop(){const u=S.user;
 const month=['users','actions'].includes(S.view)?R.month:S.month;
 $('#top').innerHTML=`<div class="welcome"><h1>${S.view==='dash'?`${u.admin?'담당자':esc(S.city)+' 담당자'}님,<br>이번 달 <em>복지 미션</em>을 확인하세요.`:TITLES[S.view]}</h1>${S.view!=='dash'?'<small>지역의 변화를 살피고 필요한 지원을 연결합니다.</small>':''}</div><div class="global-controls"><label class="global-select">${ic('log',19)}<select data-global-month aria-label="분석 기준월">${MONTHS.slice().reverse().map(m=>`<option value="${m}" ${m===month?'selected':''}>${m.replace('-','년 ')}월</option>`).join('')}</select></label><label class="global-select">${ic('dash',19)}<select data-global-city aria-label="대상 지자체" ${u.admin?'':'disabled'}>${Object.keys(GEO).map(c=>`<option ${c===S.city?'selected':''}>${c}</option>`).join('')}</select></label><button class="iconbtn mobile-assistant" data-act="chat" aria-label="AI 도우미 열기">${ic('chat')}</button></div>`;
 $('#assistant-user').innerHTML=`<span class="pill warn">시연 데이터</span><span class="user-avatar">${u.admin?'관':esc(S.city[0])}</span><b>${u.admin?'전체 관리자':esc(S.city)+' 담당자'}</b><button class="iconbtn" data-act="logout" aria-label="로그아웃">${ic('out',18)}</button>`;
}

// ---------- 조회 조건: 일/월 탭, 기준일, 앞뒤 날짜 이동 ----------
function ctrlBar(){
 let h=`<div class="ctrl"><div class="tabs" role="group" aria-label="집계 단위"><button data-mode="day" aria-pressed="${S.mode==='day'}">일</button><button data-mode="month" aria-pressed="${S.mode==='month'}">월</button></div>`;
 if(S.mode==='day')h+=`<div class="period"><button class="iconbtn" data-step="-1" aria-label="전날">${ic('prev',16)}</button><input type="date" data-date value="${S.date}" min="${fmtD(MIN_DAY)}" max="${fmtD(END)}" aria-label="기준일"><button class="iconbtn" data-step="1" aria-label="다음날" ${toD(S.date)>=END?'disabled':''}>${ic('next',16)}</button></div>`;
 else h+=`<div class="period"><select data-month aria-label="기준월">${MONTHS.slice().reverse().map(m=>`<option value="${m}" ${m===S.month?'selected':''}>${m.replace('-','년 ')}월${m===MONTHS[11]?' (진행 중)':''}</option>`).join('')}</select></div>`;
 return h+`</div>`}
function legendFactors(){return `<div class="legend">${FS.map((n,i)=>`<span><i style="background:${FC[i]}"></i>${n} ${Math.round(S.W[i]/S.W.reduce((a,b)=>a+b,0)*100)}%</span>`).join('')}</div>`}

function zoomBox(){const g=GEO[S.city];const sm=g.units.filter(x=>x.a<3300);if(sm.length<6)return null;
 const xs=sm.map(x=>x.cx),ys=sm.map(x=>x.cy);const pad=34;let x0=Math.min(...xs)-pad,x1=Math.max(...xs)+pad,y0=Math.min(...ys)-pad,y1=Math.max(...ys)+pad;
 const ar=g.w/g.h;let w=x1-x0,h=y1-y0;if(w/h>ar){const nh=w/ar;y0-=(nh-h)/2;h=nh}else{const nw=h*ar;x0-=(nw-w)/2;w=nw}return {x:x0,y:y0,w,h,z:g.w/w}}

// ---------- 지도: 행정동 SVG 경계, 위험 단계 색, 선택 강조, 숫자 라벨 ----------
function mapSVG(rows){const g=GEO[S.city];const zb=S.zoom?zoomBox():null;const z=zb?zb.z:1;const vb=zb?`${zb.x.toFixed(1)} ${zb.y.toFixed(1)} ${zb.w.toFixed(1)} ${zb.h.toFixed(1)}`:`0 0 ${g.w} ${g.h}`;
 const sorted=rows.slice().sort((a,b)=>(a.n===S.sel)-(b.n===S.sel));
 let h=`<svg viewBox="${vb}" role="group" aria-label="${S.city} 행정동별 위험도 지도">`;
 sorted.forEach(r=>{const dim=S.band!==null&&r.b!==S.band;h+=`<path class="u b${r.b}${dim?' dim':''}${r.n===S.sel?' sel':''}" d="${r.d}" data-u="${r.n}" tabindex="0" role="button" aria-label="${r.n} 위험도 ${f1(r.s)} ${BN[r.b]}"/>`});
 rows.forEach(r=>{const dim=S.band!==null&&r.b!==S.band;const A=r.a*z*z;if(A<3300)return;if(zb&&(r.cx<zb.x||r.cx>zb.x+zb.w||r.cy<zb.y||r.cy>zb.y+zb.h))return;
  h+=`<text class="ulab t${r.b}${dim?' dim':''}" x="${r.cx}" y="${r.cy}" style="font-size:${(13/z).toFixed(2)}px;stroke-width:${(2.5/z).toFixed(2)}px">${r.n}${A>=6500?`<tspan class="s" x="${r.cx}" dy="${(12/z).toFixed(1)}" style="font-size:${(12/z).toFixed(2)}px">${Math.round(r.s)}</tspan>`:''}</text>`});
 return h+`</svg>`}
function bandBar(rows){const c=[0,0,0,0];rows.forEach(r=>c[r.b]++);
 return `<div class="bands" role="group" aria-label="위험 단계 필터">${[3,2,1,0].map(b=>`<button class="bandbtn" data-band="${b}" aria-pressed="${S.band===b}"><i style="background:var(--b${b})"></i>${BN[b]} <b class="num">${c[b]}</b></button>`).join('')}</div>`}

// ---------- 선택 지역 카드: 위험 점수, 요인 막대, 안내 문장 ----------
function detailHTML(r){if(!r)return '<div class="empty">지도에서 동을 선택하세요.</div>';
 const tot=S.W.reduce((a,b)=>a+b,0);
 let h=`<div class="dhead"><h3>${r.n}</h3><span class="chip b${r.b}">${BN[r.b]}</span></div><div class="big num">${f1(r.s)}<small> / 100</small></div><div class="delta num">${perLabel()} 대비 ${dl(r.delta)}</div><div style="margin-top:12px">`;
 r.f.forEach((v,i)=>{h+=`<div class="frow"><span>${FS[i]}<br><span class="w">가중 ${Math.round(S.W[i]/tot*100)}%</span></span><div class="bar"><i style="width:${v}%;background:${FC[i]}"></i></div><span class="v num">${Math.round(v)}</span></div>`});
 h+=`</div><div class="note">${hints(r).map(t=>`<p>${t}</p>`).join('')}</div><div style="margin-top:12px"><button class="btn ghost sm" data-goto-users="${r.n}">이 동의 집단별 변화 보기</button></div>`;return h}

// ---------- 추이 카드: 지역 평균·선택 동의 시계열을 charts.js에 전달 ----------
function trendCard(rows){const city=S.city,units=GEO[city].units.map(x=>x.n);let labels=[],keys=[];
 if(S.mode==='day'){const e=toD(S.date);for(let i=29;i>=0;i--){keys.push(fmtD(e-i));}labels=keys.map(k=>+k.slice(5,7)+'/'+ +k.slice(8))}
 else{keys=MONTHS.filter(k=>k<=S.month).slice(-12);labels=keys.map(k=>+k.slice(5)+'월')}
 const avg=keys.map(k=>{const values=units.map(u=>scoreAt(city,u,S.mode,k,S.W)).filter(Number.isFinite);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null});
 const series=[{name:`${city} 평균`,c:'#7D8FA0',w:2,v:avg}];
 if(S.sel)series.push({name:S.sel,c:'var(--accent)',w:3,v:keys.map(k=>scoreAt(city,S.sel,S.mode,k,S.W))});
 const acc=getComputedStyle(root).getPropertyValue('--accent').trim()||'#1F6F8B';series.forEach(s=>{if(s.c==='var(--accent)')s.c=acc});
 return `<section class="card"><header><h2>위험도 추이</h2><span class="hint">${S.mode==='day'?'최근 30일':'최근 12개월'}</span></header><div class="cbody">${chartSVG(series,labels,'위험도 추이')}<div class="legend" style="margin-top:6px"><span><i style="background:#7D8FA0"></i>${city} 평균</span>${S.sel?`<span><i style="background:${acc}"></i>${S.sel}</span>`:''}</div></div></section>`}

// ---------- 순위 카드: 현재 위험 단계 필터를 적용한 상위 8개 동 ----------
function rankCard(rows){const list=rows.filter(r=>S.band===null||r.b===S.band).sort((a,b)=>b.s-a.s).slice(0,8);
 return `<section class="card"><header><h2>우선 확인 순위</h2><span class="hint">${S.band===null?'전체':BN[S.band]} 상위 ${list.length}곳</span></header><div class="cbody"><ol class="rank">${list.map((r,i)=>`<li data-u="${r.n}" ${r.n===S.sel?'aria-current="true"':''} tabindex="0"><span class="n num">${i+1}</span><span>${r.n}</span><span class="chip b${r.b}">${BN[r.b]}</span><span class="dl num">${dl(r.delta)}</span></li>`).join('')||'<div class="empty">해당 단계의 동이 없어요.</div>'}</ol></div></section>`}


// ---------- 화면 1. 종합 현황: 지도 + 상세 / 아래 추이 + 우선 확인 순위 ----------
function viewDash(){S.mode='month';return viewMissionDash()}

// ---------- 화면 2. 동별 분석: 위험도·요인 기여 누적 막대 표 ----------
function viewAnalysis(){const rows=snap().sort((a,b)=>b.s-a.s);const tot=S.W.reduce((a,b)=>a+b,0);
 return ctrlBar()+`<section class="card"><header><h2>${S.city} 동별 요인 분해</h2><span class="hint">${modeLabel()} 기준 · ${periodLabel()}</span></header><div class="cbody"><div style="margin-bottom:12px">${legendFactors()}</div><div class="tblwrap"><table class="tbl"><thead><tr><th>동</th><th>단계</th><th>위험도</th><th>${perLabel()} 대비</th><th>요인별 기여</th><th>주요 요인</th></tr></thead><tbody>${rows.map(r=>`<tr><td><b>${r.n}</b></td><td><span class="chip b${r.b}">${BN[r.b]}</span></td><td class="num">${f1(r.s)}</td><td class="num">${dl(r.delta)}</td><td><div class="stack" title="요인별 기여">${r.f.map((v,i)=>`<i style="width:${(S.W[i]*v/tot/Math.max(r.s,1))*100}%;background:${FC[i]}" title="${FS[i]}"></i>`).join('')}</div></td><td>${topFac(r).join(', ')}</td></tr>`).join('')}</tbody></table></div></div></section>`}

// ---------- 화면 5. 데이터 연계: 자료 출처와 반영 지표 ----------
function viewData(){const rows=[['이동전화 유동인구','대회 제공',FS[0],'활동량 변화'],['카드 결제','대회 제공',FS[1],'소비 활동 변화'],['주민등록 인구·세대','외부 공공데이터',FS[2],'1인 가구 비율'],['주민등록 인구·세대','외부 공공데이터',FS[3],'고령 인구 비율'],['복지 서비스 이용 현황','외부 공공데이터',FS[4],'서비스 미연계 비율']];
 return `<section class="card"><header><h2>데이터 연계 관리</h2><span class="hint">현재 화면은 모두 샘플 값으로 계산돼요</span></header><div class="cbody tblwrap"><table class="tbl"><thead><tr><th>데이터</th><th>구분</th><th>반영 지표</th><th>산출 내용</th><th>상태</th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td><b>${r[0]}</b></td><td>${r[1]}</td><td><span class="legend"><span><i style="background:${FC[i]}"></i>${r[2]}</span></span></td><td>${r[3]}</td><td><span class="st">샘플 사용 중</span></td></tr>`).join('')}</tbody></table></div></section>`}

// ---------- 화면 6. 위험도 기준: 가중치 슬라이더와 초기화 ----------
function viewSettings(){const tot=S.W.reduce((a,b)=>a+b,0);
 return `<section class="card"><header><h2>위험도 가중치</h2><button class="btn ghost sm" data-act="resetW">기본값으로</button></header><div class="cbody"><p class="hint" style="margin-top:0">위험도 = 5개 요인 값(0~100)의 가중 평균이에요. 값을 바꾸면 대시보드의 지도·순위·변화에 바로 반영돼요.</p>
 ${FS.map((n,i)=>`<div class="sl"><label for="w${i}"><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${FC[i]};margin-right:6px"></span>${n}</label><input id="w${i}" type="range" min="0" max="40" step="1" value="${S.W[i]}" data-w="${i}"><span class="num" id="wv${i}">${S.W[i]} (${Math.round(S.W[i]/tot*100)}%)</span></div>`).join('')}
 <div class="note"><p><b>위험 단계 기준</b> (위험도 점수)</p><p>양호 ${TH[0]} 미만 · 주의 ${TH[0]}~${TH[1]-0.1} · 위험 ${TH[1]}~${TH[2]-0.1} · 심각 ${TH[2]} 이상</p></div></div></section>`}

// ---------- 화면 7. 관리자 로그: 현재 화면 세션의 접속·조회·질의·설정 ----------
function viewLogs(){if(!S.user.admin)return '<div class="empty">관리자만 볼 수 있어요.</div>';
 const tabs=['전체','접속','조회','질의','설정'];const list=LOGS.filter(l=>S.logTab==='전체'||l.type===S.logTab);
 return `<section class="card"><header><h2>접속·조회 로그</h2><span class="hint">모든 지자체 담당자의 이력 · 최신순</span></header><div class="cbody"><div class="row"><div class="tabs" role="group" aria-label="로그 종류">${tabs.map(t=>`<button data-logtab="${t}" aria-pressed="${S.logTab===t}">${t}</button>`).join('')}</div><span class="hint">${list.length}건</span></div>
 <div class="tblwrap"><table class="tbl"><thead><tr><th>일시</th><th>계정</th><th>소속</th><th>구분</th><th>내용</th><th>결과</th></tr></thead><tbody>${list.map(l=>`<tr><td class="num">${l.t}</td><td>${esc(l.id)}</td><td>${esc(l.org)}</td><td>${l.type}</td><td>${esc(l.detail)}</td><td>${l.ok?'성공':'<span class="up">실패</span>'}</td></tr>`).join('')}</tbody></table></div></div></section>`}
function renderPage(){if(S.view==='dash'||S.view==='reports')S.mode='month';if(S.view==='users')MISSION.done.add(1);const v={dash:viewDash,analysis:viewAnalysis,users:viewUsers,actions:viewActions,data:viewData,settings:viewSettings,logs:viewLogs,reports:viewReports}[S.view];$('#page').innerHTML=['dash','analysis'].includes(S.view)&&!snap().length?ctrlBar()+'<div class="empty">선택한 기간의 자료가 없어요. 다른 날짜를 선택해 주세요.</div>':v();updateCtx();updateAssistant()}
function render(){if(S.view==='dash'||S.view==='reports')S.mode='month';renderSide();renderTop();renderPage();$('#app').classList.toggle('nochat',!S.chat);$('#chat').classList.toggle('open',S.chat)}
function updateCtx(){if(['users','actions'].includes(S.view)){$('#ctx').textContent=`보는 중: ${S.city} · ${R.month} · 지역·성별·연령대`;return;}$('#ctx').textContent=`보는 중: ${S.city} · ${modeLabel()} · ${periodLabel()}${S.view==='dash'&&S.sel?' · '+S.sel:''}`}

/* ---- 챗봇 (시연용 규칙 기반) ---- */
function addMsg(t,who){const m=document.createElement('div');m.className='m '+who;m.textContent=t;const b=$('#msgs');b.appendChild(m);b.scrollTop=b.scrollHeight}

// ---------- 오른쪽 챗봇: 현재 지역·기간·선택 동에 따른 규칙 기반 답변 ----------
function answer(q){if(['users','actions'].includes(S.view))return responseAnswer();const rows=snap().sort((a,b)=>b.s-a.s);const t=q.replace(/\s/g,'');const per=perLabel();
 if(!rows.length)return '선택한 기간에 조회할 자료가 없어요.';
 const desc=r=>`${r.n}: 위험도 ${f1(r.s)}(${BN[r.b]}), ${per}보다 ${dtxt(r.delta)}. 주요 요인은 ${topFac(r).join(', ')}이에요.`;
 const base=n=>/[0-9]동$|본동$/.test(n)?n.replace(/(본|[0-9])동$/,''):n;
 const hit=rows.filter(r=>base(r.n).length>=2&&t.includes(base(r.n)));
 if(hit.length){return hit.slice(0,3).map(r=>desc(r)+'\n→ '+hints(r)[0]).join('\n\n')}
 if(/요인|이유|왜|원인/.test(t)){const r=rows.find(x=>x.n===S.sel);if(!r)return '지도에서 동을 먼저 선택해 주세요.';return desc(r)+'\n→ '+hints(r).join('\n→ ')}
 if(/상승|오른|급|증가|악화/.test(t)){const l=rows.slice().sort((a,b)=>b.delta-a.delta).slice(0,3);return `${per}보다 가장 많이 오른 곳이에요.\n`+l.map(r=>`· ${r.n} ${dtxt(r.delta)} (현재 ${f1(r.s)})`).join('\n')}
 if(/위험|순위|높은|심각|우선|방문|어디/.test(t)){const l=rows.slice(0,3);return `${S.city} ${periodLabel()} 기준 우선 확인할 곳이에요.\n`+l.map((r,i)=>`${i+1}. ${desc(r)}`).join('\n')}
 if(/로그|이력/.test(t))return S.user.admin?'좌측 메뉴의 "접속·조회 로그"에서 전체 이력을 볼 수 있어요.':'로그는 전체 관리자 계정에서만 볼 수 있어요.';
 return '이렇게 물어볼 수 있어요.\n· 가장 위험한 동은?\n· 지난주보다 오른 동은?\n· 선택한 동 위험 요인은?\n· 역삼동 상태 알려줘\n\n(시연용 응답이라 정해진 질문 유형만 이해해요.)'}
function send(q){q=q.trim();if(!q)return;addMsg(q,'me');log('질의',q);const inp=$('#cin');inp.value='';setTimeout(()=>{addMsg(answer(q),'bot');},380)}

/* ---- 로그인/이벤트 ---- */

// ---------- 로그인: 시연 계정과 소속 일치 확인 ----------
function login(e){e.preventDefault();const org=$('#lorg').value,id=$('#lid').value.trim(),pw=$('#lpw').value;const err=$('#lerr');
 if(!org){err.textContent='소속을 선택해 주세요.';return}
 const a=ACC.find(x=>x.id===id&&x.pw===pw);
 if(!a){err.textContent='아이디 또는 비밀번호가 맞지 않아요.';log('접속','로그인 실패 (아이디/비밀번호 불일치)',false,{id:id||'-',org});return}
 if(a.org!==org){err.textContent='선택한 소속과 계정이 맞지 않아요.';log('접속','로그인 실패 (소속 불일치)',false,{id:a.id,org});return}
 S.user=a;S.city=a.admin?Object.keys(GEO)[0]:a.org;S.view='dash';S.mode='month';S.sel=null;log('접속','로그인');
 $('#login').hidden=true;$('#app').hidden=false;render();if(!$('#msgs').children.length)addMsg(`${a.name}님, 안녕하세요. 동별 위험도, 상승 지역, 위험 요인을 물어보세요.`,'bot')}

// ---------- 로그아웃: 앱을 숨기고 로그인 화면으로 돌아가기 ----------
function logout(){log('접속','로그아웃');S.user=null;MISSION.done.clear();MISSION.reviewed.clear();MISSION.zoom=1;R.statuses={};R.selected=null;R.district='전체';R.gender='전체';R.age='전체';R.priority='전체';$('#app').hidden=true;$('#login').hidden=false;$('#lpw').value='';$('#lerr').textContent='';$('#msgs').innerHTML=''}

// ---------- 지도·순위 클릭: 선택 동을 기억한 뒤 상세·추이를 다시 그리기 ----------
function pick(u){S.sel=u;MISSION.done.add(0);MISSION.reviewed.add(reviewKey(u));log('조회',`${S.city} ${u} 상세`);renderPage()}
// 파트 8. 클릭 동작: 메뉴·지도·필터·로그아웃을 한곳에서 처리합니다.
listen('click',e=>{const t=e.target;let el;
 if(el=t.closest('[data-demo]')){const [o,i,p]=el.dataset.demo.split('|');$('#lorg').value=o;$('#lid').value=i;$('#lpw').value=p;return}
 if(!S.user)return;
 if(el=t.closest('[data-view]')){if(el.dataset.view==='logs'&&!S.user.admin)return;S.view=el.dataset.view;log('조회',TITLES[S.view]+' 화면');render();return}
 if(el=t.closest('[data-act]')){const a=el.dataset.act;
  if(a==='side'){S.side=!S.side;renderSide();return}
  if(a==='chat'){S.chat=!S.chat;$('#app').classList.toggle('nochat',!S.chat);$('#chat').classList.toggle('open',S.chat);renderTop();return}
  if(a==='chatclose'){S.chat=false;$('#app').classList.add('nochat');$('#chat').classList.remove('open');renderTop();return}
  if(a==='logout'){logout();return}
  if(a==='zoom'){S.zoom=!S.zoom;renderPage();return}
  if(a==='resetW'){S.W=DEFW.slice();log('설정','위험도 가중치 초기화');renderPage();return}}
 if(el=t.closest('[data-city]')){S.city=el.dataset.city;S.sel=null;S.band=null;S.zoom=false;R.district='전체';R.selected=null;log('조회',`${S.city}로 전환`);render();return}
 if(el=t.closest('[data-mode]')){S.mode=el.dataset.mode;log('조회',`${S.city} · ${modeLabel()} 단위 전환`);renderPage();return}
 if(el=t.closest('[data-step]')){const d=Math.max(MIN_DAY,Math.min(END,toD(S.date)+ +el.dataset.step));S.date=fmtD(d);renderPage();return}
 if(el=t.closest('[data-band]')){const b=+el.dataset.band;S.band=S.band===b?null:b;renderPage();return}
 if(el=t.closest('[data-u]')){pick(el.dataset.u);return}
 if(el=t.closest('[data-goto-users]')){R.district=el.dataset.gotoUsers;R.selected=null;S.view='users';render();return}
 if(el=t.closest('[data-logtab]')){S.logTab=el.dataset.logtab;renderPage();return}
 if(el=t.closest('[data-chip]')){send(el.dataset.chip);return}});
listen('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches&&e.target.matches('[data-u]')){e.preventDefault();pick(e.target.dataset.u)}});
// 파트 9. 입력 변경: 날짜·월
listen('change',e=>{const t=e.target;if(!S.user)return;
 if(t.matches('[data-date]')){let d=toD(t.value);if(isNaN(d))return;d=Math.max(MIN_DAY,Math.min(END,d));S.date=fmtD(d);log('조회',`${S.city} · 일 · ${S.date}`);renderPage()}
 else if(t.matches('[data-month]')){S.month=t.value;log('조회',`${S.city} · 월 · ${S.month}`);renderPage()}});
// 파트 10. 슬라이더: 가중치 변경 후 다른 화면에서 새 점수 반영
listen('input',e=>{const t=e.target;if(S.user&&t.matches('[data-w]')){S.W[+t.dataset.w]=+t.value;if(S.W.reduce((a,b)=>a+b,0)===0){S.W[+t.dataset.w]=1;t.value=1}
 const tot=S.W.reduce((a,b)=>a+b,0);S.W.forEach((w,i)=>{$('#wv'+i).textContent=`${w} (${Math.round(w/tot*100)}%)`});clearTimeout(weightTimer);weightTimer=setTimeout(()=>log('설정','위험도 가중치 변경: '+S.W.join('/')),700)}});
/* 지도 툴팁 */
const tip=$('#tip');
listen('mousemove',e=>{const el=e.target.closest&&e.target.closest('path[data-u]');if(!el||!S.user){tip.hidden=true;return}
 const r=snap().find(x=>x.n===el.dataset.u);if(!r){tip.hidden=true;return}
 tip.textContent=`${r.n} · ${BN[r.b]} ${f1(r.s)} (${perLabel()} 대비 ${dtxt(r.delta)})`;tip.hidden=false;
 const w=tip.offsetWidth;tip.style.left=Math.min(root.clientWidth-w-8,e.clientX+14)+'px';tip.style.top=(e.clientY+16)+'px'});
listen('mouseleave',()=>{tip.hidden=true});
$('#lform').addEventListener('submit',login);
$('#csend').addEventListener('submit',e=>{e.preventDefault();send($('#cin').value)});

/* 로그인 화면 배경: 실제 경계 실루엣 */
$('#lmaps').innerHTML=Object.keys(GEO).map(c=>{const g=GEO[c];return `<svg viewBox="0 0 ${g.w} ${g.h}" aria-hidden="true">${g.units.map(u=>`<path d="${u.d}"/>`).join('')}</svg>`}).join('');

$('#assistant-mascot').innerHTML=detectiveSVG();
