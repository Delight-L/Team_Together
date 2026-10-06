"""Match saved signals to welfare resource descriptions."""
from dashboard.missions import service_candidates, service_key

MATCH_RULES = [
    ("사회참여·교류", ["유동", "외출", "활동", "집체류", "연락"], ["사회참여", "교류", "모임", "고립", "안부", "방문", "문화", "여가"]),
    ("생활·경제 지원", ["소비", "결제", "카드", "경제"], ["생활", "생계", "긴급", "경제", "상담", "지원금"]),
    ("고령·건강 지원", ["고령", "노인", "65세", "60대", "저외출"], ["노인", "고령", "돌봄", "건강", "방문", "안부"]),
    ("1인가구 지원", ["1인가구", "1인 가구", "청년"], ["1인가구", "1인 가구", "청년", "교류", "고립", "상담"]),
]

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
