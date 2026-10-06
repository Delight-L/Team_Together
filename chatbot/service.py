"""Grounded chatbot replies. LLM calls require explicit opt-in."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

def explain_question(question, evidence, history=None, *, allow_agent=False):
    if not evidence:
        return "선택 지역·월의 실제 분석 결과가 없습니다. 분석 결과를 먼저 연결하세요.", "DB1 근거 설명"
    signals = [r for r in evidence if r.get("is_risk_signal")]
    parts = []
    if any(word in question.lower().replace(" ", "") for word in ["robust", "z-score", "z점수", "기준"]):
        parts.append("Robust Z-score는 이번 변화가 과거 변화의 중앙값·MAD에서 얼마나 벗어났는지를 나타냅니다. 현재 Analysis2는 전화·문자 또는 평일·휴일 이동 지표의 Robust Z가 모두 -2.0 이하인 묶음을 후보로 표시합니다. 과거 이력은 최소 12회이며 이력이 부족하면 판단을 보류합니다.")
    if "상대" in question or "중앙값" in question:
        parts.append("상대 변화 열은 해당 동의 로그 변화량에서 같은 달 전체 동의 공통 변화를 뺀 값에 100을 곱한 수치입니다. 퍼센트포인트와는 다른 단위입니다. 여러 지역에 동시에 나타난 계절 변화를 구분하는 데 사용합니다.")
    for row in signals:
        parts.append(row.get("explanation") or f"{row['metric_label']}: 상대 변화량 {row.get('relative_change_pp')} (상대 로그 변화 × 100), Robust Z {row.get('risk_robust_z')}")
    if not signals:
        parts.append("현재 기준을 통과한 변화 후보는 없습니다. 후보 없음과 이력 부족은 구분해야 합니다.")
    context = next((r for r in evidence if r.get("cluster_profile")), {})
    if context:
        parts.append(context.get("context_note", "") + " " + context.get("cluster_profile", ""))
        parts.append(context.get("cluster_check_point", ""))
    if any(word in question for word in ["사업", "복지", "지원", "연결"]):
        parts.append("사업 매칭 검토에서 이 지표·지역 유형과 DB2 사업 설명의 공통 키워드를 확인할 수 있습니다. 추천 이유와 거주·연령·소득·모집 조건을 함께 검토하세요.")
    parts.append("이 분석은 변화 탐지 근거이며 실제 원인을 확정하지 않습니다. 계절·지역 행사·집계 변화는 추가 확인이 필요합니다.")
    fallback = "\n\n".join(filter(None, parts))
    if allow_agent is not True or not (os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL")):
        return fallback, "DB1 근거 설명 (규칙 기반)"
    try:
        from google import genai
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        prompt = "저장된 분석 데이터만 사용해 공무원의 질문에 답하세요. 원인·개인 고립·사업 자격을 확정하거나 수치를 만들지 마세요. 조건을 모르면 확인 필요라고 하세요. 한국어로 답하세요.\n" + json.dumps({"question":question,"evidence":evidence,"history":(history or [])[-4:]},ensure_ascii=False,default=str)
        response = client.models.generate_content(model=os.environ["GEMINI_MODEL"], contents=prompt)
        return response.text or fallback, "AI · DB1 근거 기반"
    except Exception:
        return fallback, "DB1 근거 설명 (AI 연결 실패로 규칙 기반 설명)"
