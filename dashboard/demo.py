"""DB 없이 전체 흐름을 검증하는 명시적인 시연 자료. 실제 업무 자료가 아닙니다."""
import hashlib
from pathlib import Path
import streamlit as st

@st.cache_data(show_spinner=False)
def load_demo_analysis():
    from dashboard.pipeline import monthly_upload, records
    source = Path(__file__).resolve().parents[1] / "agent/risk_analysis_version1/data/gangnam_db1_dong_month_behavior_mart_2025_07_12(1).csv"
    content = source.read_bytes()
    prepared = monthly_upload(content, source.name)
    run = "demo-" + hashlib.sha256(content).hexdigest()[:12]
    return {"connected":False,"isDemo":True,"runId":run,"assessment":records(prepared["assessment"]),"signals":records(prepared["signals"]),"alerts":records(prepared["alerts"]),"activity":[],"runs":[{"run_id":run,"kind":"monthly","source_name":"[시연] 저장소 예제 행동자료 분석","period":prepared["period"],"created_at":"예제 자료","rule_version":"risk-analysis-v1"}]}

def demo_services(city):
    if city != "강남구":
        return []
    base = {"source_id":"demo","region_id":"gangnam","coverage_scope":"specified_regions","residency_text":"[시연 조건] 강남구 거주 주민","eligibility_text":"[시연 조건] 상담 후 참여 의사 확인","cost_text":"[시연 조건] 무료","source_url":None,"start_date":None,"end_date":None,"application_text":"시연 화면에서 적합성 검토 및 승인 처리"}
    return [dict(base,external_id="demo-social",name="[시연 사업] 사회참여·교류 및 안부 확인",target_text="[시연 대상] 사회참여 기회가 필요한 주민·1인가구",support_text="[시연 내용] 교류 모임·사회참여 활동·안부 상담"),dict(base,external_id="demo-care",name="[시연 사업] 고령 주민 방문·돌봄 상담",target_text="[시연 대상] 고령·노인 주민",support_text="[시연 내용] 방문 상담·건강 확인·생활 돌봄"),dict(base,external_id="demo-life",name="[시연 사업] 생활·경제 지원 상담",target_text="[시연 대상] 생활·경제 상담이 필요한 주민",support_text="[시연 내용] 생활·생계·경제 상담 및 지원 정보 안내")]
