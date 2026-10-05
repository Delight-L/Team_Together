// 메인 대시보드: 지역 지도, 월별 변화, 담당자의 현재 세션 미션.
const MISSION = { done: new Set(), reviewed: new Set(), sort: "risk", zoom: 1 };
const reviewKey = (name) => JSON.stringify([S.city, S.month, name]);
function puzzleIcon() {
  return '<svg viewBox="0 0 32 32" aria-hidden="true"><path fill="currentColor" d="M12 4a4 4 0 1 1 8 0v3h5a3 3 0 0 1 3 3v4h-3a4 4 0 1 0 0 8h3v5a3 3 0 0 1-3 3h-5v-3a4 4 0 1 0-8 0v3H7a3 3 0 0 1-3-3v-5H1a4 4 0 0 1 0-8h3v-4a3 3 0 0 1 3-3h5z"/></svg>';
}
function detectiveSVG() {
  return `<svg viewBox="0 0 170 150" role="img" aria-label="복지탐정 AI 로봇"><defs><linearGradient id="robot-shell" x2="1" y2="1"><stop stop-color="#fff"/><stop offset="1" stop-color="#a6c6ed"/></linearGradient><linearGradient id="robot-face" x2="0" y2="1"><stop stop-color="#122c51"/><stop offset="1" stop-color="#07182f"/></linearGradient></defs><ellipse cx="84" cy="141" rx="54" ry="6" fill="#a4c4ed" opacity=".3"/><path d="M48 140q3-43 35-44t38 44" fill="#537cb5"/><path d="M64 109l20 15 18-15-6 31H70z" fill="#e7f1ff"/><rect x="28" y="51" width="111" height="64" rx="30" fill="url(#robot-shell)" stroke="#8fadd4" stroke-width="2"/><rect x="22" y="70" width="15" height="27" rx="7" fill="#809fcc"/><rect x="130" y="70" width="15" height="27" rx="7" fill="#809fcc"/><rect x="41" y="61" width="87" height="43" rx="20" fill="url(#robot-face)"/><ellipse cx="63" cy="80" rx="6" ry="9" fill="#4ddcff"/><ellipse cx="105" cy="80" rx="6" ry="9" fill="#4ddcff"/><path d="M76 91q8 7 16 0" fill="none" stroke="#8deaff" stroke-width="3" stroke-linecap="round"/><path d="M42 53Q46 16 83 14q37 2 43 39" fill="#b8875b" stroke="#84542f" stroke-width="2"/><path d="M79 16L65 51M88 16l16 35" fill="none" stroke="#e3bd91" stroke-width="4"/><path d="M33 54q50-16 102 0l-6 7q-43-7-88 1z" fill="#805336"/><circle cx="85" cy="13" r="6" fill="#8d5b33"/><circle cx="131" cy="111" r="18" fill="#b8e5ff" fill-opacity=".65" stroke="#d8ad71" stroke-width="7"/><path d="M143 126l12 18" stroke="#94683e" stroke-width="10" stroke-linecap="round"/><path d="M122 104l12-6" stroke="white" stroke-width="3" stroke-linecap="round"/></svg>`;
}
function missionRows() {
  return snap()
    .slice()
    .sort((a, b) =>
      MISSION.sort === "delta"
        ? (b.delta ?? -Infinity) - (a.delta ?? -Infinity)
        : b.s - a.s,
    );
}
function missionSummary(rows) {
  const result = { fresh: 0, persistent: 0, pending: 0 };
  const previousMonth = prevMonth(S.month);
  const twoMonthsAgo = prevMonth(previousMonth);
  for (const row of rows) {
    const olderScore = scoreAt(S.city, row.n, "month", twoMonthsAgo, S.W);
    const previousScore = scoreAt(S.city, row.n, "month", previousMonth, S.W);
    if (
      row.delta > 0 &&
      Number.isFinite(olderScore) &&
      Number.isFinite(previousScore)
    ) {
      if (previousScore > olderScore) result.persistent++;
      else result.fresh++;
    }
    if (row.b >= 2 && !MISSION.reviewed.has(reviewKey(row.n))) result.pending++;
  }
  return result;
}
function missionMap(rows) {
  const g = GEO[S.city],
    top = rows.slice(0, 3),
    colors = ["#ff496a", "#ff9638", "#16a9df"];
  const view =
    MISSION.zoom === 1
      ? `-55 -30 ${g.w + 220} ${g.h + 100}`
      : `${g.w * 0.16} ${g.h * 0.16} ${g.w * 0.75} ${g.h * 0.75}`;
  return `<svg class="mission-map-svg" viewBox="${view}" role="group" aria-label="${S.city} 행정동별 우선 확인 지도"><defs><pattern id="city-blocks" width="62" height="60" patternUnits="userSpaceOnUse"><path d="M0 60L62 0M-31 30L31-30M31 90L93 30" stroke="#fff" stroke-width="7"/><path d="M8 17l13-7 12 7-13 7z" fill="#fff"/><path d="M8 17v19l12 8V24z" fill="#c4c9d0"/><path d="M20 24l13-7v20l-13 7z" fill="#e1e3e6"/><circle cx="47" cy="42" r="7" fill="#c1d5b6"/><path d="M47 40v12" stroke="#a7b398" stroke-width="2"/></pattern><filter id="map-lift" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="9" stdDeviation="6" flood-color="#8091a4" flood-opacity=".23"/></filter></defs><g filter="url(#map-lift)">${rows
    .map((r) => {
      const rank = top.findIndex((t) => t.n === r.n);
      return `<path class="mission-district ${r.n === S.sel ? "is-selected" : ""}" d="${r.d}" fill="${rank < 0 ? "#e7f0ff" : colors[rank]}" data-u="${esc(r.n)}" tabindex="0" role="button" aria-label="${esc(r.n)} 위험도 ${f1(r.s)} ${BN[r.b]}"/><path d="${r.d}" fill="url(#city-blocks)" opacity="0.10" pointer-events="none"/>`;
    })
    .join("")}</g>${rows
    .filter((r) => !top.some((t) => t.n === r.n) && r.a > 6000)
    .map(
      (r) =>
        `<text class="quiet-map-label" x="${r.cx}" y="${r.cy}" text-anchor="middle">${esc(r.n)}</text>`,
    )
    .join("")}${top
    .map((r, i) => {
      const y = 40 + (i * (g.h - 70)) / 3,
        x = g.w - 20;
      return `<g><path pointer-events="none" d="M${r.cx} ${r.cy}L${x - 20} ${y + 27}" stroke="${colors[i]}" stroke-width="2" stroke-dasharray="4 4" opacity=".6"/><circle cx="${r.cx}" cy="${r.cy}" r="10" fill="${colors[i]}" stroke="white" stroke-width="4"/><g class="map-callout" data-u="${esc(r.n)}" tabindex="0" role="button" aria-label="${i + 1}순위 ${esc(r.n)} 상세" transform="translate(${x - 18} ${y})"><rect width="166" height="59" rx="12" fill="white" stroke="#e3e8ef"/><path d="M-20 1c-17 0-26 23-14 38l14 19 14-19C6 24-3 1-20 1" fill="${colors[i]}" stroke="white" stroke-width="3"/><text x="-20" y="29" text-anchor="middle" fill="white" font-size="21" font-weight="700">${i + 1}</text><text x="17" y="25" fill="#14203f" font-size="18" font-weight="700">${esc(r.n)}</text><text x="17" y="45" fill="${colors[i]}" font-size="13">${BN[r.b]} · ${f1(r.s)}점</text></g></g>`;
    })
    .join("")}</svg>`;
}
function viewMissionDash() {
  const rows = missionRows();
  if (!rows.length)
    return '<div class="empty">선택한 월의 자료가 없습니다.</div>';
  if (!rows.some((r) => r.n === S.sel)) S.sel = rows[0].n;
  const counts = missionSummary(rows),
    selected = rows.find((r) => r.n === S.sel),
    p = prevMonth(S.month);
  const changes = [0, 1, 2].map((i) => {
    const current = rows.map((r) => r.f[i]).filter(Number.isFinite),
      past = rows
        .map((r) => factorsAt(S.city, r.n, "month", p)[i])
        .filter(Number.isFinite);
    return {
      name: FS[i],
      value:
        current.length && past.length
          ? current.reduce((a, b) => a + b, 0) / current.length -
            past.reduce((a, b) => a + b, 0) / past.length
          : null,
    };
  });
  return `<div class="mission-kpis">${[
    ["신규 상승 지역", counts.fresh, "전월 하락·보합 → 상승", "trend"],
    ["지속 상승 지역", counts.persistent, "2개월 연속 점수 상승", "bar"],
    [
      "검토 대기 지역",
      counts.pending,
      "위험·심각 중 이번 세션 미확인",
      "check",
    ],
  ]
    .map(
      ([name, count, note, icon], i) =>
        `<button class="card mission-kpi tone-${i}" data-view="${i === 2 ? "actions" : "analysis"}"><span class="kpi-icon">${ic(icon === "trend" ? "bar" : icon, 30)}</span><span><b>${name}</b><strong>${count}<small>곳</small></strong><em>${note}</em></span></button>`,
    )
    .join(
      "",
    )}</div><section class="card mission-map-card"><header><h2><span class="folder-symbol"></span>우선 확인할 지역 ${Math.min(3, rows.length)}곳</h2><select data-map-sort aria-label="지도 우선순위 정렬"><option value="risk" ${MISSION.sort === "risk" ? "selected" : ""}>위험도순</option><option value="delta" ${MISSION.sort === "delta" ? "selected" : ""}>상승폭순</option></select></header><div class="mission-map-stage"><div class="map-tools"><button data-map-zoom="in" aria-label="지도 확대">+</button><button data-map-zoom="out" aria-label="지도 축소">−</button><button data-map-zoom="reset" aria-label="지도 전체 보기">⌖</button></div><span class="map-city-badge">${esc(S.city)} <small>행정동 지도</small></span>${missionMap(rows)}<div class="map-caption">행정동 경계 기반 도식 · 건물 패턴은 장식 · 지도 클릭으로 지역 선택</div></div><div class="selected-strip"><div><b>${esc(selected.n)}</b><span>${BN[selected.b]} · ${f1(selected.s)}점</span><small>전월 대비 ${selected.delta === null ? "자료 없음" : (selected.delta > 0 ? "+" : "") + f1(selected.delta) + "점"}</small></div><button class="btn ghost sm" data-goto-users="${esc(selected.n)}">복지 자원 검토 ${ic("next", 14)}</button></div></section><section class="card month-changes"><header><h2>${ic("bar", 21)} 이번 달 주요 변화</h2><span class="hint">${esc(S.city)} 평균 · 위험 요인 점수의 전월 차이</span></header><div class="change-tiles">${changes.map((c, i) => `<div class="change-tile tone-${i}"><span class="change-icon">${ic(["users", "bar", "dash"][i], 26)}</span><div><span>${c.name}</span><strong>${c.value === null ? "—" : (c.value > 0 ? "+" : "") + f1(c.value)}<small>점</small></strong></div><svg viewBox="0 0 60 30" aria-hidden="true"><path d="M2 25L12 18 22 22 33 8 44 13 58 3" fill="none" stroke="currentColor" stroke-width="3"/></svg></div>`).join("")}</div></section><p class="mission-footnote">시연용 데이터 · ${S.month === fmtD(END).slice(0, 7) ? fmtD(END) + "까지의 자료로 월평균 산출" : "월별 평균 기준"} · 최종 판단은 담당자가 수행합니다.</p>`;
}
function reportText() {
  if (S.source === "db1") return actualAnswer('보고서') + '\n\nWord 초안 작성에서 담당자 의견을 추가하고 편집 가능한 문서로 내려받으세요.';
  const rows = missionRows().slice(0, 3);
  return (
    `[복지탐정 AI · 지역 검토 보고서 초안]\n${S.city} / ${S.month}\n시연용 데이터 · 담당자 확인 필요\n\n` +
    rows
      .map(
        (r, i) =>
          `${i + 1}. ${r.n}: ${BN[r.b]}, ${f1(r.s)}점 / 전월 대비 ${Number.isFinite(r.delta) ? f1(r.delta) + "점" : "자료 없음"}\n주요 요인: ${topFac(r).join(", ")}`,
      )
      .join("\n\n") +
    "\n\n검토 항목: 성별·연령대 변화 확인, 계절 및 집계 영향 확인, 복지 자원 이용 조건 확인.\n실제 사업·기관 DB 연결 전이며 서비스 연계 결과를 의미하지 않습니다."
  );
}
function viewReports() {
  return `<section class="card report-card"><header><h2>지역 검토 보고서</h2><button class="btn sm" data-operation="report">Word 초안 작성</button></header><div class="cbody"><p class="hint">선택한 지역·월의 데이터를 바탕으로 작성한 검토용 초안입니다.</p><pre>${esc(reportText())}</pre></div></section>`;
}
function updateAssistant() {
  if (!S.user) return;
  const item = currentMission();
  const evidence = item.analysis_evidence || [];
  $("#assistant-context").innerHTML = `<div class="assistant-answer"><b>${esc(S.sel || "지역을 먼저 선택하세요")}</b><p>${esc(S.month)} · 저장된 분석 근거로 설명합니다.</p>${evidence.filter(r=>r.is_risk_signal).slice(0,3).map(r=>`<p>${esc(r.explanation || r.metric_label)}</p>`).join("")}${S.sel?'<button class="btn sm wide" data-question="왜 이 지역이 우선 확인 후보인가요?">왜 이 결과가 나왔나요?</button>':'<p>대시보드의 우선 확인 지역을 누르면 분석 결과가 열립니다.</p>'}</div>`;
  $("#msgs").innerHTML = (item.questions || []).map(q=>`<div class="m me">${esc(q.question)}</div><div class="m bot">${esc(q.answer)}<small>${esc(q.mode || "근거 설명")}</small></div>`).join("");
  $("#mission-progress").innerHTML = workflowProgress(item);
}
function workflowProgress(item) {
  const labels = ["분석·질의", "사업 검토", "보고서 완료"];
  const completed = [1,2,3].filter(step=>item.done.includes(step)).length;
  return `<div class="progress-title"><b>${puzzleIcon()} ${item.workflow_complete?"업무 완료":item.done.includes(2)?"사업 검토 완료 · 보고 대기":"지역별 업무 진행"}</b><span>${completed} / 3</span></div><div class="puzzle-track">${labels.map((label,i)=>`<span class="${item.done.includes(i+1)?"earned":""}">${puzzleIcon()}<small>${label}</small></span>`).join("")}</div><small>${esc(S.sel || "지역 선택 대기")} · ${esc(S.month)}</small>`;
  const target = $("#assistant-context");
  if (!target || !S.user) return;
  const rows = snap(),
    r =
      rows.find((x) => x.n === S.sel) ||
      rows.slice().sort((a, b) => b.s - a.s)[0];
  target.innerHTML = r
    ? `<div class="assistant-question">${esc(r.n)}의 주요 변화와 검토할 자원을 알려줘.</div><div class="assistant-answer"><b>${esc(r.n)}에서 확인할 변화입니다.</b><div class="assistant-factors">${r.f
        .slice(0, 3)
        .map(
          (v, i) =>
            `<div><span>${ic(["users", "bar", "dash"][i], 16)}${FS[i]}</span><strong>${f1(v)}<small> / 100</small></strong></div>`,
        )
        .join(
          "",
        )}</div><p>위험 요인 점수 · 예시 데이터<br>성별·연령대 변화를 확인한 뒤 자원을 검토하세요.</p><button class="btn sm wide" data-goto-users="${esc(r.n)}">복지 자원 후보 확인 ${ic("next", 16)}</button></div>`
    : '<div class="empty">조회할 지역 자료가 없습니다.</div>';
  if(S.source==='db1' && !['users','actions'].includes(S.view)) {
    target.innerHTML=`<div class="assistant-answer"><b>DB1 분석 근거</b><p style="white-space:pre-wrap;font-size:12px">${esc(actualAnswer('선택 지역'))}</p><button class="btn sm" data-operation="report">Word 초안 작성</button></div>`;
  }
  if (["users", "actions"].includes(S.view)) {
    const groups = filteredResponses(),
      group = groups.find((x) => x.key === R.selected) || groups[0];
    target.innerHTML = group
      ? `<div class="assistant-question">${esc(group.district)} ${esc(group.gender)} ${esc(group.age)}의 변화를 확인해 줘.</div><div class="assistant-answer"><b>${esc(group.district)} · ${group.priority}</b><div class="assistant-factors"><div><span>유동인구 변화율</span><strong>${rateText(group.flowRate)}</strong></div><div><span>카드 이용 변화율</span><strong>${rateText(group.cardRate)}</strong></div></div><p>${esc(group.reason || "전월 대비 일평균 변화 · 서비스 이용 조건을 확인하세요.")}</p><button class="btn sm wide" data-view="users">복지 자원 검토</button></div>`
      : '<div class="empty">이 조건에 해당하는 집단 자료가 없습니다.</div>';
  }
  $("#mission-progress").innerHTML =
    `<div class="progress-title"><b>${puzzleIcon()} 분석 단서 모으기</b><span>${MISSION.done.size} / 3</span></div><div class="puzzle-track">${["지역 확인", "자원 검토", "보고서 작성"].map((t, i) => `<span class="${MISSION.done.has(i) ? "earned" : ""}" title="${t}">${puzzleIcon()}<small>${t}</small></span>`).join("")}</div><small>현재 세션에서 완료한 탐색 단계</small>`;
}
listen("click", (e) => {
  if (!S.user) return;
  const t = e.target.closest("[data-map-zoom]");
  if (!t) return;
  MISSION.zoom = t.dataset.mapZoom === "in" ? 1.7 : 1;
  renderPage();
});
listen("change", (e) => {
  if (!S.user) return;
  if (e.target.matches("[data-map-sort]")) {
    MISSION.sort = e.target.value;
    renderPage();
  }
  if (e.target.matches("[data-global-month]")) {
    S.month = e.target.value;
    R.month = e.target.value;
    R.district = R.gender = R.age = R.priority = "전체";
    R.selected = null;
    S.sel = null;
    MISSION.zoom = 1;
    render();
  }
  if (
    e.target.matches("[data-global-city]") &&
    S.user.admin &&
    GEO[e.target.value]
  ) {
    S.city = e.target.value;
    S.sel = null;
    R.district = "전체";
    R.selected = null;
    MISSION.zoom = 1;
    render();
  }
});

function currentMission() {
  const key = JSON.stringify([(BOOT.db1?.isDemo ? "demo:" : "") + S.user?.id, S.city, S.sel, S.month]);
  return BOOT.missions?.[key] || {done:[], reviews:[], connections:[], questions:[]};
}
function missionRecordsView() {
  const item = currentMission();
  if (!S.sel) return `<section class="card"><header><h2>사업 매칭 검토</h2></header><div class="cbody"><p>먼저 대시보드에서 우선 확인 지역을 선택하세요.</p><button class="btn" data-view="dash">우선 확인할 지역 보기</button></div></section>`;
  return `<section class="card"><header><h2>${esc(S.sel)} · 사업 매칭 검토</h2></header><div class="cbody">${workflowProgress(item)}<p>저장된 분석 결과와 실제 DB2 사업의 연관 근거를 확인하고, 사업 이용 조건과 적합성을 검토하고 결과를 기록합니다.</p><button class="btn" data-candidates="${esc(S.sel)}" ${item.done.includes(1)?"":"disabled"}>분석 결과에 맞는 DB2 사업 검토</button> <button class="btn ghost" data-view="analysis">분석 근거 다시 보기</button>${!item.done.includes(1)?'<p class="hint">분석 화면에서 근거 확인을 먼저 완료하세요.</p>':""}<h3>사업 매칭 검토 기록</h3>${item.reviews.map(r=>`<div class="workflow-record"><b>${esc(r.name)}</b> · ${esc(r.decision)}<p>${esc(r.note)}</p></div>`).join("") || '<p class="hint">아직 검토 기록이 없습니다.</p>'}${item.done.includes(2)?`<div class="note">${item.workflow_complete?"보고서 저장까지 업무 완료":"사업 검토 완료 · 최종 보고서를 작성하세요"}</div><button class="btn" data-operation="report">${item.workflow_complete?"최종 보고서 조회":"사업 검토 보고서 작성"}</button>`:""}</div></section>`;
}
function workflowReportView() {
  const item=currentMission();
  return `<section class="card"><header><h2>사업 검토 결과 보고서</h2></header><div class="cbody"><p>${esc(S.sel || "지역 선택 필요")} · ${esc(S.month)}</p>${workflowProgress(item)}<p>분석 근거, 추가 질의, 사업 매칭 판단, 사업 검토 결과와 판단 근거를 Word 보고서에 담습니다.</p><p class="hint">기관 지정 양식 확정 전 내부 기본 양식을 사용합니다. 최종 확인 후 파일을 저장해야 업무가 완료됩니다.</p><button class="btn" data-operation="report" ${item.done.includes(2)?"":"disabled"}>${item.workflow_complete?"저장된 보고서 내려받기":"양식에 맞춰 보고서 작성"}</button>${!item.done.includes(2)?'<p class="hint">사업 검토 기록을 먼저 저장하세요.</p>':""}</div></section>`;
}
function workflowBoard() {
  const items=Object.entries(BOOT.missions || {}).filter(([key])=>{const [user,city,,month]=JSON.parse(key);return user===(BOOT.db1?.isDemo?"demo:":"")+S.user.id && city===S.city && month===S.month;});
  return `<section class="card"><header><h2>지역별 업무 현황</h2></header><div class="cbody"><table class="tbl"><thead><tr><th>지역</th><th>진행</th><th>상태</th><th>다음 작업</th></tr></thead><tbody>${items.map(([key,item])=>`<tr><td>${esc(JSON.parse(key)[2])}</td><td>${[1,2,3].filter(step=>item.done.includes(step)).length}/3</td><td>${item.workflow_complete?"업무 완료":item.done.includes(2)?"보고서 대기":"분석·검토 중"}</td><td><button class="btn sm" data-resume-region="${esc(JSON.parse(key)[2])}">이어서 진행</button></td></tr>`).join("") || '<tr><td colspan="4">진행 중인 업무가 없습니다. 대시보드에서 지역을 선택하세요.</td></tr>'}</tbody></table></div></section>`;
}
function openRegionAnalysis(district) {
  S.sel=district;
  S.view="analysis";
  S.chat=true;
  const item=currentMission();
  if (S.source === "db1" && !item.done.includes(0)) requestOperation("open_analysis");
  else render();
}
listen("click", (event) => {
  if (!S.user) return;
  const candidate=event.target.closest("[data-candidates]");
  if(candidate){S.sel=candidate.dataset.candidates || S.sel;requestOperation("candidates");}
  const confirm=event.target.closest("[data-confirm-evidence]");
  if(confirm) requestOperation("confirm_evidence");
  const question=event.target.closest("[data-question]");
  if(question) send(question.dataset.question);
  const resume=event.target.closest("[data-resume-region]");
  if(resume){S.sel=resume.dataset.resumeRegion;const item=currentMission();S.view=item.done.includes(2)?"reports":item.done.includes(1)?"users":"analysis";render();}
});
