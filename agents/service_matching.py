"""저장된 분석 신호와 복지사업 설명을 비교해 연계 후보를 고릅니다(사업 매칭 검토 화면)."""
from db.mission_store import service_candidates, service_key

# (분류, 분석 지표에 있으면 관련 있다고 볼 말, 사업 설명에 있으면 관련 있다고 볼 말)
MATCH_RULES = [
    ("사회참여·교류", ["이동", "유동", "외출", "활동", "집체류", "연락"],
     ["사회참여", "교류", "모임", "고립", "안부", "방문", "문화", "여가"]),
    ("생활·경제 지원", ["소비", "결제", "카드", "경제"],
     ["생활", "생계", "긴급", "경제", "상담", "지원금"]),
    ("고령·건강 지원", ["고령", "노인", "65세", "60대", "저외출"],
     ["노인", "고령", "돌봄", "건강", "방문", "안부"]),
    ("1인가구 지원", ["1인가구", "1인 가구", "청년"],
     ["1인가구", "1인 가구", "청년", "교류", "고립", "상담"]),
]
SERVICE_FIELDS = ["name", "target_text", "eligibility_text", "benefit_text", "support_text",
                  "description", "content", "summary"]
EVIDENCE_FIELDS = ["metric_label", "meaning", "context_note", "cluster_profile"]


def joined_text(item, fields):
    """여러 항목의 글을 한 문자열로 이어 붙입니다. 비어 있는 항목은 건너뜁니다."""
    return " ".join(str(item.get(field) or "") for field in fields)


def match_services(city, evidence, services=None):
    """사업마다 관련 분류(reasons)를 찾아, 관련 분류가 많은 순서로 돌려줍니다."""
    if services is None:
        services = service_candidates(city)
    signals = [row for row in evidence if row.get("is_risk_signal")]

    matched = []
    for service in services:
        service_text = joined_text(service, SERVICE_FIELDS)
        reasons = []
        for category, signal_words, service_words in MATCH_RULES:
            related_signals = [row for row in signals
                               if any(word in joined_text(row, EVIDENCE_FIELDS) for word in signal_words)]
            found_words = [word for word in service_words if word in service_text]
            if related_signals and found_words:
                metrics = []
                for row in related_signals:
                    if row["metric_label"] not in metrics:
                        metrics.append(row["metric_label"])
                reasons.append({"category": category, "metrics": metrics, "service_terms": found_words})
        matched.append({"service": service, "key": service_key(service), "reasons": reasons, "score": len(reasons)})

    matched.sort(key=lambda item: (-item["score"], item["service"]["name"]))
    return matched
