"""시연용 데이터 처리·보고서 작성 창입니다."""

from pathlib import Path
import tempfile
import streamlit as st

from db.analysis_repository import ROOT_DIR, DETECTION_FILE, monthly_upload, structure_upload, publish
from shared.report import build_report


@st.dialog("데이터 업로드와 분석", width="large")
def upload_dialog(request):
    if request.get("user", {}).get("id") != "admin":
        st.info("시연 버전의 데이터 반영은 전체 관리자 계정에서 진행합니다.")
        return
    st.caption("검사 → 전처리·분석 → 미리보기 → DB1 반영. 기존 버전은 보관합니다.")
    kind = st.radio(
        "자료 종류",
        ["Analysis2 탐지 결과 CSV 또는 Excel", "지역 구조자료 원본 5종"],
        key="upload_kind",
    )
    source_files = st.file_uploader(
        "파일 선택",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        key="demo_uploads",
    )
    st.info(
        "월별 자료는 version11의 Analysis2/outputs 탐지 결과 파일을 사용합니다. 지역 구조자료는 기존 전처리 원본 5종을 함께 올립니다."
    )
    current_files = tuple(
        (file.name, file.size, file.getvalue()) for file in source_files
    )
    selection = (kind, current_files)
    if st.session_state.get("prepared_selection") != selection:
        st.session_state.pop("prepared_upload", None)
    if st.button("업로드 자료 검사 및 분석", type="primary"):
        try:
            if not source_files:
                raise ValueError("파일을 먼저 선택하세요.")
            if kind.startswith("Analysis2"):
                if len(source_files) != 1:
                    raise ValueError("월별 행동자료는 한 파일씩 올려 주세요.")
                file = source_files[0]
                prepared = monthly_upload(file.getvalue(), file.name)
            else:
                temp_root = ROOT_DIR / ".tmp"
                temp_root.mkdir(exist_ok=True)
                with tempfile.TemporaryDirectory(dir=temp_root) as folder:
                    for file in source_files:
                        (Path(folder) / Path(file.name).name).write_bytes(
                            file.getvalue()
                        )
                    prepared = structure_upload(folder)
            st.session_state.prepared_upload = prepared
            st.session_state.prepared_selection = selection
        except Exception as error:
            st.error(f"자료를 처리하지 못했습니다: {error}")
    if st.button("저장소 예제 월별 자료로 시연"):
        sample = (
            DETECTION_FILE
        )
        try:
            prepared = monthly_upload(sample.read_bytes(), "시연 예제 " + sample.name)
            st.session_state.prepared_upload = prepared
            st.session_state.prepared_selection = selection
        except (OSError, ValueError) as error:
            st.error(f"예제 자료를 읽지 못했습니다: {error}")
    prepared = st.session_state.get("prepared_upload")
    if prepared:
        st.success(f"검사 완료 · {prepared['period']} · {len(prepared['data'])}행")
        st.dataframe(prepared["data"].head(22), hide_index=True)
        if prepared["kind"] == "monthly":
            st.write(
                f"후보 {len(prepared['signals'])}건 / 동·월 요약 {len(prepared['alerts'])}건"
            )
            st.dataframe(prepared["signals"].head(20), hide_index=True)
            st.caption(
                "과거 이력이 부족한 초기 월은 후보를 판정하지 않습니다. 반영된 월별 분석은 대시보드의 DB1 보기에서 조회합니다."
            )
        else:
            st.caption(
                "지역 유형 분석 입력이며 PCA·군집화는 별도 단계입니다. 월별 위험분석을 자동 실행하지 않습니다."
            )
        if st.button("검사한 결과를 DB1에 반영", type="primary"):
            try:
                run_id = publish(prepared, request["user"]["id"])
                st.session_state.pop("prepared_upload", None)
                st.session_state.operation_notice = f"DB1 반영 완료 · 버전 {run_id[:8]}"
                st.rerun(scope="app")
            except Exception:
                st.error(
                    "DB1 반영에 실패했습니다. 연결·테이블 권한을 확인하세요. 기존 반영 자료는 유지됩니다."
                )


@st.dialog("사업 검토 결과 보고서", width="large")
def report_dialog(request, db_data):
    import hashlib
    from db.mission_store import load_all, identity, load_report, save_event, review_revision
    if not request.get("district"):
        st.info("보고할 지역을 먼저 선택하세요.")
        return
    item = load_all().get(identity(request), {})
    if 2 not in item.get("done", []):
        st.info("사업 검토 기록 저장 후 보고서를 작성할 수 있습니다.")
        return
    context = {"city":request["city"],"district":request["district"],"month":request["month"]}
    st.write(f"{context['city']} · {context['district']} · {context['month']}")
    if item.get("is_demo"):
        st.warning("시연 보고서입니다. 기관 제출용 문서가 아닙니다.")
    st.caption("내부 기본 양식: 분석 근거 · 질의 · 사업 조건 및 매칭 검토 · 사업 검토 내역 · 최종 의견. 기관 지정 양식은 제공 후 반영할 수 있습니다.")
    if item.get("workflow_complete"):
        st.success("보고서 저장 완료 · 업무 완료")
        document = load_report(request)
        if document:
            st.download_button("저장된 최종 보고서 내려받기",document,file_name=item["report"]["filename"],mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        return
    department = st.text_input("작성 부서", value=f"{context['city']} 복지정책과")
    author = st.text_input("작성자", value=request["user"]["id"])
    opinion = st.text_area("최종 보고 의견 및 후속 사항", height=130)
    fields = (identity(request),review_revision(item),department,author,opinion)
    ready = all(v.strip() for v in [department,author,opinion])
    if st.button("양식에 맞춰 보고서 생성", type="primary", disabled=not ready):
        document = build_report(context,item["analysis_evidence"],author,department,opinion,item.get("analysis_source","저장된 DB1 분석"),workflow=item)
        st.session_state.report_draft = {"fields":fields,"document":document}
    draft = st.session_state.get("report_draft")
    if draft and draft["fields"] == fields:
        document = draft["document"]
        filename = ("시연_" if item.get("is_demo") else "") + f"사업검토보고_{context['city']}_{context['district']}_{context['month']}.docx"
        st.download_button("생성된 Word 보고서 확인",document,file_name=filename,mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        confirmed = st.checkbox("생성된 보고서와 사업 검토 내역을 최종 확인했습니다")
        if st.button("최종 보고서 저장 및 업무 완료",type="primary",disabled=not confirmed):
            save_event(request,3,{"sha256":hashlib.sha256(document).hexdigest(),"filename":filename,"author":author,"department":department,"opinion":opinion,"confirmed":confirmed,"review_id":review_revision(item),"_document":document})
            st.session_state.operation_notice = "최종 보고서를 저장했습니다. 이 지역의 업무가 완료되었습니다."
            st.session_state.pop("report_draft",None)
            st.rerun(scope="app")


def handle_request(request, db_data):
    if not request:
        return
    request = dict(request, workflow_mode="demo" if db_data.get("isDemo") else "live")
    from db.mission_store import load_all, identity, save_event
    from legacy.streamlit_dashboard.common import selected_evidence, explain_question
    if request.get("action") == "candidates":
        candidates_dialog(request)
    elif request.get("action") == "open_analysis":
        rows = selected_evidence(request, db_data)
        try:
            if not rows or not db_data.get("runId"):
                raise ValueError("선택 지역의 실제 DB1 분석 결과가 없습니다.")
            run = next((r for r in db_data.get("runs",[]) if r.get("run_id") == db_data["runId"]),{})
            save_event(request,0,{"run_id":db_data["runId"],"evidence":rows,"source_note":f"{run.get('source_name','DB1')} / {run.get('period','')} / 분석 버전 {db_data['runId']}"})
        except ValueError as error:
            st.session_state.operation_notice = str(error)
        st.rerun()
    elif request.get("action") == "confirm_evidence":
        try:
            save_event(request,1,{"confirmed":True})
        except ValueError as error:
            st.session_state.operation_notice = str(error)
        st.rerun()
    elif request.get("action") == "question":
        question = str(request.get("question", "")).strip()
        item = load_all().get(identity(request),{}) if request.get("district") else {}
        if item.get("workflow_complete"):
            st.session_state.operation_notice = "완료된 업무의 질의 기록은 변경할 수 없습니다. 저장된 보고서를 확인하세요."
        elif not question or not item.get("analysis_evidence"):
            st.session_state.operation_notice = "분석 지역을 먼저 선택하고 질문을 입력하세요."
        else:
            answer, mode = explain_question(question,item["analysis_evidence"],item.get("questions"), allow_agent=request.get("agent_enabled") is True)
            save_event(request,1,{"question":question,"answer":answer,"mode":mode})
        st.rerun()
    elif request.get("action") == "upload":
        upload_dialog(request)
    elif request.get("action") == "report":
        report_dialog(request, db_data)

"""지역 분석 → 사업 매칭 검토 → 보고서 작성."""
from db.mission_store import service_key, load_all, identity, save_event
from legacy.streamlit_dashboard.common import match_services

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
            from db.demo import demo_services
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
