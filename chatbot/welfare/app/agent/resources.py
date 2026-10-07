"""팀 자료의 복지사업 검색. 외부 서비스나 DB 연결 없이 실행할 수 있습니다."""
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
def load_resources():
    candidates = json.loads((DATA / "policy_candidates.json").read_text(encoding="utf-8"))["records"]
    records = [{"id": r["id"], "name": r["name"], "description": r["description"], "category": r["category"], "region": r["reference_region"], "target": "자료에 상세 자격 없음", "agency": "자료에 담당 기관 없음", "source": r["source_file"], "pages": str(r["source_pdf_pages"]), "status": "계획·검토 자료 / 현재 운영 및 자격 미확인", "url": r.get("official_application_url")} for r in candidates]
    plans = json.loads((DATA / "gangnam_policy_plans_2025.json").read_text(encoding="utf-8"))
    records += [{"id": f"plan-{i}", "name": r["사업명"], "description": r["지원내용"], "category": "지역 복지", "region": "강남구", "target": r["대상"], "agency": r["기관"], "source": r["출처파일"], "pages": r["PDF페이지"], "status": r["상태"], "url": None} for i, r in enumerate(plans)]
    # 같은 사업이 두 자료에 있으면 상세 대상·기관을 가진 계획 자료를 사용합니다.
    # 원문별 출처를 임의로 섞지 않고 마지막 계획 레코드 전체를 유지합니다.
    return list({record['name']: record for record in records}.values())

RESOURCES = load_resources()
GROUPS = [("외로", "고립", "관계", "모임", "친구", "소통"), ("병원", "건강", "의료", "동행"), ("식사", "밥", "식생활", "요리", "식비"), ("청년", "취업", "자립"), ("어르신", "노인", "고령", "돌봄"), ("주거", "집", "월세", "주택")]
def search(query, limit=5, *, city="", district=""):
    # 서울·강남 자료를 춘천 등 다른 지역의 이용 가능한 사업으로 안내하지 않습니다.
    if city and city not in {"강남구", "서울시", "서울"}:
        return []
    terms = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", query))
    for group in GROUPS:
        if any(word in query for word in group):
            terms.update(group)
    ranked = []
    for r in RESOURCES:
        body = " ".join(str(r[k]) for k in ("name", "description", "category", "region", "target", "agency"))
        score = sum((4 if term in r["name"] else 1) for term in terms if term in body)
        # 지역만 맞는 사업을 반환하지 않고 지원 필요와도 일치하는 후보를 우선합니다.
        if score and district and district in body:
            score += 2
        if score:
            ranked.append((score, r))
    ranked.sort(key=lambda item: item[0], reverse=True)
    unique = []
    for _, r in ranked:
        if r["name"] not in {item["name"] for item in unique}:
            unique.append(r)
    return unique[:limit]

def local_answer(records):
    if not records:
        return "팀 자료에서 질문에 맞는 사업을 찾지 못했어요. 거주 지역과 필요한 지원(식사, 병원 동행, 주거, 관계 모임 등)을 알려주시면 다시 찾아볼게요. 현재 자료는 서울시·강남구 중심이며 다른 지역에 대한 안내는 제한됩니다. 주민등록번호나 정확한 주소는 보내지 마세요."
    blocks = ["팀 자료에서 관련 복지사업을 찾았어요. 아래 내용은 계획·검토 자료이며 현재 모집, 이용 자격, 지원금은 담당 기관에 확인해야 합니다."]
    for i, r in enumerate(records, 1):
        blocks.append(f'{i}. {r["name"]}\n지원 내용: {r["description"]}\n자료상 대상: {r["target"]}\n기관: {r["agency"]}\n확인 상태: {r["status"]}\n출처: {r["source"]} (p. {r["pages"]})')
    blocks.append("다음 단계: 거주 지역 담당 주민센터 또는 자료에 나온 기관에 현재 운영 여부, 대상 조건, 신청 방법과 필요 서류를 확인해 주세요. 어떤 지역에서 어떤 지원을 찾고 계신가요?")
    return "\n\n".join(blocks)
