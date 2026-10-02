"""시연용 데이터 처리·보고서 작성 창입니다."""

from pathlib import Path
import tempfile
import streamlit as st

from dashboard.pipeline import ROOT_DIR, monthly_upload, structure_upload, publish
from dashboard.report import build_report


@st.dialog("데이터 업로드와 분석", width="large")
def upload_dialog(request):
    if request.get("user", {}).get("id") != "admin":
        st.info("시연 버전의 데이터 반영은 전체 관리자 계정에서 진행합니다.")
        return
    st.caption("검사 → 전처리·분석 → 미리보기 → DB1 반영. 기존 버전은 보관합니다.")
    kind = st.radio(
        "자료 종류",
        ["월별 행동 CSV 또는 Excel", "지역 구조자료 원본 5종"],
        key="upload_kind",
    )
    source_files = st.file_uploader(
        "파일 선택",
        type=["csv", "xlsx"],
        accept_multiple_files=True,
        key="demo_uploads",
    )
    st.info(
        "월별 행동자료는 행정동코드·행정동명·기준연월(YYYY-MM)이 필요합니다. 지역 구조자료는 기존 전처리 원본 5종을 함께 올립니다."
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
            if kind.startswith("월별"):
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
            ROOT_DIR
            / "agent/risk_analysis_version1/data/gangnam_db1_dong_month_behavior_mart_2025_07_12(1).csv"
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


@st.dialog("Word 보고서 초안", width="large")
def report_dialog(request, db_data):
    context = {"city": request.get("city", "강남구"), "month": request.get("month", "")}
    rows = [row for row in db_data["signals"] if row["기준연월"] == context["month"]]
    # 현재 분석은 강남구 동별 자료입니다. 다른 지자체로 재사용하지 않습니다.
    if context["city"] != "강남구":
        rows = []
    if request.get("district"):
        rows = [row for row in rows if row["행정동명"] == request["district"]]
    st.write(f"{context['city']} · {context['month']} · 변화 후보 {len(rows)}건")
    st.caption(
        "DB1에 반영된 분석 근거로 작성합니다. 시연 화면의 0~100 점수를 실제 분석값으로 사용하지 않습니다."
    )
    department = st.text_input("작성 부서", value=f"{context['city']} 복지정책과")
    author = st.text_input("작성자", value="담당자")
    opinion = st.text_area("담당자 검토 의견 및 후속 조치", height=130)
    source = next((run for run in db_data["runs"] if run["kind"] == "monthly"), None)
    source_note = "DB1에 반영된 월별 자료 없음 · 분석 근거 없는 초안"
    if source:
        source_note = f"{source['source_name']} / {source['period']} / {source['rule_version']} / 버전 {source['run_id']}"
    if st.button("Word 초안 생성", type="primary"):
        try:
            data = build_report(context, rows, author, department, opinion, source_note)
            st.session_state.report_download = (data, context.copy())
        except ImportError:
            st.error(
                "Word 생성 패키지가 없습니다. setup_team.bat를 실행하거나 python-docx를 설치하세요."
            )
    if "report_download" in st.session_state:
        data, saved_context = st.session_state.report_download
        st.download_button(
            "편집 가능한 Word 내려받기",
            data,
            file_name=f"지역변화검토_{saved_context['city']}_{saved_context['month']}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


def handle_request(request, db_data):
    if not request:
        return
    if request.get("action") == "upload":
        upload_dialog(request)
    elif request.get("action") == "report":
        st.session_state.pop("report_download", None)
        report_dialog(request, db_data)
