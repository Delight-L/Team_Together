"""저장된 지역 분석과 DB2 사업 사이의 근거를 보여주는 업무 로직."""
import json
import os
from dashboard.missions import service_candidates, service_key

MATCH_RULES = [
    ("사회참여·교류", ["유동", "외출", "활동", "집체류", "연락"], ["사회참여", "교류", "모임", "고립", "안부", "방문", "문화", "여가"]),
    ("생활·경제 지원", ["소비", "결제", "카드", "경제"], ["생활", "생계", "긴급", "경제", "상담", "지원금"]),
    ("고령·건강 지원", ["고령", "노인", "65세", "60대", "저외출"], ["노인", "고령", "돌봄", "건강", "방문", "안부"]),
    ("1인가구 지원", ["1인가구", "1인 가구", "청년"], ["1인가구", "1인 가구", "청년", "교류", "고립", "상담"]),
]

def selected_evidence(request, db_data):
    if request.get("city") != "강남구":
        return []
    return [r for r in db_data.get("assessment", []) if r["기준연월"] == request["month"] and r["행정동명"] == request.get("district")]

def match_services(city, evidence, services=None):
    services = service_candidates(city) if services is None else services
    matched = []
    for service in services:
        corpus = " ".join(str(service.get(k) or "") for k in ["name", "target_text", "eligibility_text", "support_text", "description", "content", "summary"])
        reasons = []
        for category, signals, terms in MATCH_RULES:
            source = [r for r in evidence if r.get("is_risk_signal") and any(t in " ".join(str(r.get(k) or "") for k in ["metric_label", "meaning", "context_note", "cluster_profile"]) for t in signals)]
            words = [t for t in terms if t in corpus]
            if source and words:
                reasons.append({"category": category, "metrics": list(dict.fromkeys(r["metric_label"] for r in source)), "service_terms": words})
        matched.append({"service": service, "key": service_key(service), "reasons": reasons, "score": len(reasons)})
    return sorted(matched, key=lambda m: (-m["score"], m["service"]["name"]))

def explain_question(question, evidence, history=None):
    if not evidence:
        return "선택 지역·월의 실제 분석 결과가 없습니다. 분석 결과를 먼저 연결하세요.", "DB1 근거 설명"
    signals = [r for r in evidence if r.get("is_risk_signal")]
    parts = []
    if any(word in question.lower().replace(" ", "") for word in ["robust", "z-score", "z점수", "기준"]):
        parts.append("Robust Z-score는 이번 변화가 과거 변화의 중앙값·MAD에서 얼마나 벗어났는지를 나타냅니다. 위험 방향 상대 변화량과 Z 기준을 모두 통과해야 확인 후보이며, MAD가 0이거나 과거 이력이 부족하면 판단을 보류합니다.")
    if "상대" in question or "중앙값" in question:
        parts.append("상대 변화량은 해당 동의 전월 변화율에서 같은 달 전체 동의 변화율 중앙값을 뺀 값입니다. 여러 지역에 동시에 나타난 계절 변화를 구분하는 데 사용합니다.")
    for row in signals:
        parts.append(row.get("explanation") or f"{row['metric_label']}: 상대 변화량 {row.get('relative_change_pp')}%p, Robust Z {row.get('risk_robust_z')}")
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
    if not (os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL")):
        return fallback, "DB1 근거 설명 (규칙 기반)"
    try:
        from google import genai
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        prompt = "저장된 분석 데이터만 사용해 공무원의 질문에 답하세요. 원인·개인 고립·사업 자격을 확정하거나 수치를 만들지 마세요. 조건을 모르면 확인 필요라고 하세요. 한국어로 답하세요.\n" + json.dumps({"question":question,"evidence":evidence,"history":(history or [])[-4:]},ensure_ascii=False,default=str)
        response = client.models.generate_content(model=os.environ["GEMINI_MODEL"], contents=prompt)
        return response.text or fallback, "AI · DB1 근거 기반"
    except Exception:
        return fallback, "DB1 근거 설명 (AI 연결 실패로 규칙 기반 설명)"
