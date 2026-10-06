// 버튼 요청만 Python으로 보냅니다. 무거운 계산과 DB 반영은 서버가 담당합니다.
function requestOperation(action, extra = {}) {
  const snapshot = {
    state: { ...S, user: S.user ? { id: S.user.id } : null },
    responses: R,
    logs: LOGS,
    mission: { done: [...MISSION.done], reviewed: [...MISSION.reviewed] },
  };
  setStateValue("ui_state", snapshot);
  setTriggerValue("request", {
    action,
    ...extra,
    user: S.user ? { id: S.user.id, org: S.user.org } : null,
    city: S.city,
    month: S.month,
    district: S.sel,
  });
}

function restoreUI() {
  const saved = BOOT.savedUI;
  if (!saved?.state?.user) return;
  Object.assign(S, saved.state);
  if (BOOT.db1?.isDemo) {S.source="db1";if(!analysisMonths().includes(S.month)){S.month=analysisMonths().at(-1);S.sel=null;S.view="dash";}}
  S.user = ACC.find((account) => account.id === saved.state.user.id);
  if (!S.user) return;
  Object.assign(R, saved.responses || {});
  LOGS.push(...(saved.logs || []));
  MISSION.done = new Set(saved.mission?.done || []);
  MISSION.reviewed = new Set(saved.mission?.reviewed || []);
  $("#login").hidden = true;
  $("#app").hidden = false;
  render();
}

function analysisMonths() {
  return [
    ...new Set((BOOT.db1?.assessment || []).map((row) => row["기준연월"])),
  ].sort();
}

function actualAnswer(question) {
  if (S.city !== "강남구")
    return "현재 DB1에 연결된 월별 분석은 강남구 자료입니다.";
  let rows = (BOOT.db1?.assessment || []).filter(
    (row) => row["기준연월"] === S.month,
  );
  const named = rows.find((row) => question.includes(row["행정동명"]));
  const district = named?.["행정동명"] || S.sel;
  if (district) rows = rows.filter((row) => row["행정동명"] === district);
  if (!rows.length) return "선택한 지역·월의 반영된 분석 자료가 없습니다.";
  const signals = rows.filter((row) => row.is_risk_signal);
  if (!signals.length)
    return `${S.month} ${district || S.city}: 탐지 기준을 통과한 변화 후보가 없습니다. 비교 이력 부족 ${rows.filter((row) => !row.has_enough_history).length}건은 판단 보류입니다. 개인의 고립 없음 판정이 아닙니다.`;
  return (
    `${S.month} ${district || S.city} · 저장된 분석 결과\n` +
    signals
      .slice(0, 4)
      .map((row) => row.explanation + " " + (row.context_note || ""))
      .join("\n") +
    "\n서비스 유형은 검토 제안이며 실제 기관·이용 조건을 확인해야 합니다."
  );
}

function viewActualOverview() {
  if ((!BOOT.db1?.connected && !BOOT.db1?.isDemo) || !BOOT.db1?.assessment?.length || S.city !== "강남구") return `<section class="card"><header><h2>에이전트 분석 결과 확인</h2></header><div class="cbody"><div class="note">${!BOOT.db1?.connected?"DB1 분석 저장소에 연결되지 않았습니다.":"선택 지자체의 저장된 분석 결과가 없습니다."}</div><p>분석 에이전트가 저장한 결과가 연결되면 우선 확인할 지역 최대 3곳과 근거가 표시됩니다.</p><p class="hint">현재는 분석 결과 미연결 상태입니다. 확인 후보 없음 판정과 구분합니다. 실제 분석 결과를 연결한 뒤 사업 검토·승인을 진행하세요.</p>${S.user.admin?'<button class="btn" data-view="data">분석 데이터 연결 관리</button>':""}<button class="btn ghost" data-view="actions">저장된 업무 현황 확인</button></div></section>`;
  const all = S.city === "강남구" ? BOOT.db1?.assessment || [] : [];
  const rows = all.filter((row) => row["기준연월"] === S.month);
  const signals = rows.filter((row) => row.is_risk_signal);
  const names = [...new Set(rows.map((row) => row["행정동명"]))];
  const candidates = [...new Set(signals.map((row) => row["행정동명"]))];
  const previousMonth = analysisMonths()
    .filter((month) => month < S.month)
    .at(-1);
  const previous = all.filter((row) => row["기준연월"] === previousMonth);
  const comparable =
    previous.some((row) => row.has_enough_history) &&
    rows.some((row) => row.has_enough_history);
  const previousCount = new Set(
    previous.filter((row) => row.is_risk_signal).map((row) => row["행정동명"]),
  ).size;
  const difference = candidates.length - previousCount;
  const pending = new Set(
    rows.filter((row) => !row.has_enough_history).map((row) => row["행정동명"]),
  ).size;
  const ranking = candidates
    .map((name) => ({
      name,
      evidence: signals.filter((row) => row["행정동명"] === name),
    }))
    .sort(
      (a, b) =>
        b.evidence.length - a.evidence.length ||
        a.name.localeCompare(b.name, "ko"),
    )
    .slice(0, 3);
  const geometry = GEO[S.city];
  const map = geometry.units
    .map((unit) => {
      const count = signals.filter((row) => row["행정동명"] === unit.n).length;
      const color = !names.includes(unit.n)
        ? "#E2E8F0"
        : count > 1
          ? "#61BDB8"
          : count
            ? "#F7C65D"
            : "#D5DDE6";
      return districtTile(unit, color, `data-overview-district="${esc(unit.n)}"`, `${unit.n} · ${names.includes(unit.n) ? "확인 후보 " + count + "개" : "자료 없음"}`);
    })
    .join("");
  const latest = (BOOT.db1?.runs || []).find((run) => run.kind === "monthly");
  return (BOOT.db1?.isDemo ? `<div class="note">시연 모드 · DB 미연결 상태에서 저장소 예제 분석과 가상 사업으로 전체 흐름을 테스트합니다. 승인·보고서는 실제 업무와 별도로 저장됩니다.</div>` : "") + `<div class="overview-intro"><h2>지역 현황</h2><span class="hint">${esc(S.month)} · 최근 월별 자료 반영 ${esc(latest?.created_at?.slice(0, 10) || "없음")}</span></div>
  <div class="overview-metrics region-summary">${[
    ["확인 후보 지역", `${candidates.length}곳`, `${names.length}개 동 분석`],
    [
      "전월 대비 후보 지역",
      comparable ? `${difference > 0 ? "+" : ""}${difference}곳` : "비교 보류",
      comparable ? `${previousMonth} 대비` : "이전 월 비교 이력 부족",
    ],
    ["포착된 변화 지표", `${signals.length}건`, "담당자 확인이 필요한 변화"],
    ["자료·이력 확인 필요", `${pending}곳`, "일부 지표의 판단 보류"],
  ]
    .map(
      ([title, value, note]) =>
        `<section class="card overview-metric"><span>${title}</span><strong>${value}</strong><small>${note}</small></section>`,
    )
    .join("")}</div>
  <div class="overview-grid"><section class="card"><header><h2>확인 후보 지역 분포</h2><span class="pill">DB1 분석</span></header><div class="cbody"><div class="actual-map overview-map">${reliefMap(geometry, map, "전체 지역 요약 지도")}</div><p class="hint">회청색: 후보 없음 · 노랑: 1개 · 청록: 2개 이상 · 밝은 회색: 자료 없음<br>지역 위에 마우스를 올리면 입체적으로 강조됩니다. 클릭하거나 Enter를 누르면 지역 상세 팝업이 열립니다. 높이는 시각적 강조이며 분석 수치를 뜻하지 않습니다.</p></div></section>
  <section class="card"><header><h2>우선 확인할 지역 ${Math.min(3, ranking.length)}곳</h2></header><div class="cbody overview-priorities">${
    ranking
      .map(
        (item, index) =>
          `<button class="overview-region" data-overview-district="${esc(item.name)}"><span>${index + 1}</span><div><b>${esc(item.name)}</b><p>${esc(
            item.evidence
              .slice(0, 2)
              .map((row) => row.metric_label)
              .join(" · "),
          )}</p><small>변화 후보 ${item.evidence.length}개 · 상세 근거 확인 →</small></div></button>`,
      )
      .join("") || "<p>현재 기준을 통과한 변화 후보가 없습니다.</p>"
  }<p class="hint">후보 지표 수를 기준으로 정렬했습니다. 개인의 위험도 순위와 구분합니다.</p><div class="overview-next"><b>다음 업무</b><button class="btn ghost" data-view="analysis">지역별 근거 확인</button><button class="btn ghost" data-view="actions">진행 중인 업무 보기</button></div></div></section></div>`;
}

listen("click", (event) => {
  const target = event.target.closest("[data-overview-district]");
  if (!target) return;
  showRegionPreview(target.dataset.overviewDistrict);
});
function viewActualAnalysis() {
  const frozen = currentMission().analysis_evidence;
  const all = (BOOT.db1?.assessment || []).filter(
    (row) => row["기준연월"] === S.month,
  );
  const rows = S.city === "강남구" ? all : [];
  const signals = rows.filter((row) => row.is_risk_signal);
  const names = [...new Set(rows.map((row) => row["행정동명"]))];
  const counts = new Map(
    names.map((name) => [
      name,
      signals.filter((row) => row["행정동명"] === name).length,
    ]),
  );
  const enough = rows.filter((row) => row.has_enough_history).length;
  const geometry = GEO[S.city];
  const map = geometry.units
    .map((unit) => {
      const count = counts.get(unit.n);
      const color =
        count === undefined
          ? "#E2E8F0"
          : count > 1
            ? "#61BDB8"
            : count === 1
              ? "#F7C65D"
              : "#D5DDE6";
      return districtTile(unit, color, `data-u="${esc(unit.n)}"`, `${unit.n} · ${count === undefined ? "자료 없음" : "확인 후보 " + count + "개"}`);
    })
    .join("");
  const selected = S.sel
    ? (frozen || rows.filter((row) => row["행정동명"] === S.sel))
    : rows.filter((row) => row.is_risk_signal || !row.has_enough_history);
  const detail = selected
    .map(
      (row) =>
        `<tr><td>${esc(row["행정동명"])}</td><td>${esc(row.metric_label)}</td><td>${row.change_pct === null ? "자료 없음" : row.change_pct.toFixed(1) + "%"}</td><td>${row.relative_change_pp === null ? "자료 없음" : row.relative_change_pp.toFixed(1)}</td><td>${row.risk_robust_z === null ? "산출 불가" : row.risk_robust_z.toFixed(2)}</td><td>${!row.has_enough_history ? "판단 보류" : row.is_risk_signal ? "확인 후보" : "기준 미해당"}</td></tr>`,
    )
    .join("");
  const item=currentMission();
  const next = S.sel ? `<section class="card workflow-next"><header><h2>${esc(S.sel)} · 다음 업무</h2></header><div class="cbody">${workflowProgress(item)}${BOOT.notice?`<div class="note">${esc(BOOT.notice)}</div>`:""}<p class="hint">업무에 저장된 분석 버전: ${esc(item.analysis_run_id || BOOT.db1?.runId || "없음")}</p><p>추가 질문은 오른쪽 도우미에서 할 수 있습니다. 질문 없이도 근거를 확인한 뒤 사업 검토로 진행할 수 있습니다.</p>${item.done.includes(0) && !item.done.includes(1)?'<button class="btn" data-confirm-evidence>분석 근거 확인 완료</button>':""}${item.done.includes(1)?'<button class="btn" data-view="users">분석 결과에 맞는 사업 검토 →</button>':""}${!item.done.includes(0) && selected.length?'<button class="btn" data-start-current>이 분석 결과로 업무 시작</button>':""}</div></section>` : '<div class="note">우선 확인 지역 또는 지도에서 행정동을 선택하면 상세 근거와 다음 업무가 표시됩니다.</div>';
  return next + `<section class="card"><header><h2>반영된 월별 변화 분석</h2><span class="pill">DB1 · ${esc(S.month)}</span></header><div class="cbody"><p>변화 후보 <b>${signals.length}건</b> · 후보 지역 <b>${[...counts.values()].filter((count) => count > 0).length}곳</b> · 과거 비교 가능한 지표 <b>${enough}/${rows.length}</b></p><p class="hint">0~100 시연 점수와 구분한 분석 결과입니다. 밝은 회색: 자료 없음 · 회청색: 후보 없음 · 노랑: 1개 지표 후보 · 청록: 2개 이상. 이력 부족은 아래 표에서 판단 보류로 표시합니다.</p><div class="actual-map">${reliefMap(geometry, map, "DB1 변화 후보 지도")}</div><label>상세 지역 <select data-actual-district><option value="">전체 지역</option>${names.map((name) => `<option ${name === S.sel ? "selected" : ""}>${esc(name)}</option>`).join("")}</select></label><div class="tblwrap"><table class="tbl"><thead><tr><th>동</th><th>지표</th><th>전월 변화</th><th>상대 로그 변화 × 100</th><th>Robust Z</th><th>판정</th></tr></thead><tbody>${detail || '<tr><td colspan="6">선택 지역·월의 반영 자료가 없습니다.</td></tr>'}</tbody></table></div><details><summary>적용 분석 기준</summary><p>version11 Analysis2 결과를 표시합니다. 전화·문자 또는 평일·휴일 이동 지표의 Robust Z가 모두 -2.0 이하이면 해당 묶음을 후보로 표시합니다. 과거 이력은 최소 12회이며, 상대 변화 열은 공통 변화를 뺀 로그 변화량 × 100입니다. 후보 없음은 개인의 고립 없음 판정이 아닙니다.</p></details></div></section>`;
}

listen("click", (event) => {
  const button = event.target.closest("[data-operation]");
  if (button && S.user) requestOperation(button.dataset.operation);
});
listen("change", (event) => {
  if (event.target.matches("[data-source]")) {
    S.source = event.target.value;
    if(S.view === "regions" && S.source !== "db1") S.view="dash";
    const months = S.source === "db1" ? analysisMonths() : MONTHS;
    S.month = months.at(-1) || MONTHS.at(-1);
    S.sel = null;
    render();
  }
  if (event.target.matches("[data-actual-district]")) {
    if (event.target.value) openRegionAnalysis(event.target.value);
    else {S.sel=null;renderPage();}
  }
});

listen("click", event=>{if(event.target.closest("[data-start-current]")) requestOperation("open_analysis");});
