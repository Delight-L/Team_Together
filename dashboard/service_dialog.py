"""지역 분석 → 사업 매칭 검토 → 보고서 작성."""
import streamlit as st
from dashboard.missions import service_key, load_all, identity, save_event
from dashboard.workflow import match_services

@st.dialog("분석 결과와 복지사업 매칭 검토", width="large")
def candidates_dialog(request):
    if not request.get("district"):
        st.info("우선 확인할 지역을 먼저 선택하세요.")
        return
    item = load_all().get(identity(request), {})
    evidence = item.get("analysis_evidence", [])
    if not evidence:
        st.info("선택 지역의 실제 분석 결과를 확인한 후 사업을 검토하세요.")
        return
    st.caption(f"{request['city']} · {request['district']} · {request['month']} / 분석 버전 {item.get('analysis_run_id', '')}")
    with st.expander("이 지역을 확인하는 분석 근거", expanded=True):
        for row in evidence:
            if row.get("is_risk_signal"):
                st.write(row.get("explanation") or row["metric_label"])
        st.caption("지역별 변화 지표와 사업 설명의 키워드 연관성으로 정렬합니다. 자동 자격 판정이나 효과 예측 점수가 아닙니다.")
    try:
        if request.get("workflow_mode") == "demo":
            from dashboard.demo import demo_services
            st.warning("시연용 가상 사업입니다. 조건 확인·매칭·보고서 기능을 테스트하며 실제 기관에 연결하지 않습니다.")
            matches = match_services(request["city"], evidence, services=demo_services(request["city"]))
        else:
            matches = match_services(request["city"], evidence)
    except Exception:
        st.error("DB2 사업 목록을 조회하지 못했습니다. 실제 DB 연결 및 검토된 이용 범위 자료가 필요합니다.")
        return
    if not matches:
        st.info("선택 지역의 이용 범위가 확인된 실제 지원사업이 없습니다.")
        return
    selected = st.selectbox("매칭 후보 사업", range(len(matches)), format_func=lambda i: ("근거 연관 · " if matches[i]["reasons"] else "연관 근거 없음 · ") + matches[i]["service"]["name"])
    match = matches[selected]
    service, key = match["service"], match["key"]
    st.subheader(service["name"])
    st.write("**이 사업을 보여주는 이유**")
    for reason in match["reasons"]:
        st.write(f"{', '.join(reason['metrics'])} → {reason['category']} 검토 → 사업 설명의 {', '.join(reason['service_terms'])}와 연관")
    if not match["reasons"]:
        st.warning("분석 결과와 직접 연결할 추천 근거가 없습니다. 담당자가 별도 적합성 근거를 입력해야 합니다.")
    for label, field in [("지원 대상", "target_text"), ("자격 조건", "eligibility_text"), ("거주 조건", "residency_text"), ("지원 내용", "support_text"), ("신청 방법", "application_text"), ("비용", "cost_text"), ("시작일", "start_date"), ("종료일", "end_date")]:
        st.write(f"**{label}**: {service.get(field) or '원문 확인 필요'}")
    url = service.get("source_url")
    if url and str(url).startswith(("https://", "http://")):
        st.link_button("공식 사업 원문 확인", str(url))
    with st.expander("사업 원본 상세 정보"):
        st.json({k: str(v) if v is not None else None for k, v in service.items()})
    ready = 1 in item.get("done", []) and not item.get("workflow_complete")
    if not ready and not item.get("workflow_complete"):
        st.info("분석 화면에서 근거 확인을 완료하세요. 추가 질문은 선택 사항입니다.")
    with st.form("matching_review"):
        confirmed = st.checkbox("원문·거주·대상·모집 조건을 확인했습니다")
        decision = st.selectbox("매칭 적합성 판단", ["적합", "보류", "부적합"])
        note = st.text_area("분석 결과와 이 사업을 연결하는 검토 근거")
        submitted = st.form_submit_button("사업 매칭 검토 저장", disabled=not ready)
    if submitted:
        try:
            if not confirmed:
                raise ValueError("사업 조건 확인이 필요합니다.")
            save_event(request, 2, {"service_key":key,"name":service["name"],"decision":decision,"note":note,"source_url":url,"matching_reasons":match["reasons"],"service_snapshot":{k:str(v) if v is not None else None for k,v in service.items()}})
            st.session_state.operation_notice = "매칭 검토를 저장했습니다. 바로 보고서를 작성할 수 있습니다."
            st.rerun(scope="app")
        except ValueError as error:
            st.error(str(error))
    relevant = [r for r in item.get("reviews", []) if r["service_key"] == key]
    if relevant:
        st.write("사업별 검토 이력")
        st.dataframe(relevant, hide_index=True)
    if item.get("reviews"):
        st.success("사업 검토 완료 · 보고서 작성 대기" if not item.get("workflow_complete") else "보고서 저장까지 업무 완료")
        if st.button("사업 검토 결과 보고서 작성"):
            st.session_state.next_workflow_report = request
            st.rerun(scope="app")
