"""공유 DB2의 복지사업 검색. JSON은 명시한 오프라인 검증 모드에서만 읽습니다."""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from backend.db.welfare_chatbot_repository import load_dataset_rows

DATA = Path(__file__).resolve().parents[2] / "data"
load_dotenv(Path(__file__).resolve().parents[5] / ".env")
UNCHECKED = "계획·검토 자료 / 현재 운영 및 자격 미확인"
# 질문에 한 단어라도 있으면 같은 묶음의 다른 단어로도 찾습니다(예: '외로워' → 고립·관계·모임).
SYNONYM_GROUPS = [
    ("외로", "고립", "관계", "모임", "친구", "소통"),
    ("병원", "건강", "의료", "동행"),
    ("식사", "밥", "식생활", "요리", "식비"),
    ("청년", "취업", "자립"),
    ("어르신", "노인", "고령", "돌봄"),
    ("주거", "집", "월세", "주택"),
]
SEARCH_FIELDS = ("name", "description", "category", "region", "target", "agency")
HOUSING_TERMS = ("주거", "주택", "월세", "임대", "보증금", "집수리")
# 서울·강남 자료이므로 다른 지역(춘천 등)에는 이용 가능한 사업으로 안내하지 않습니다.
COVERED_CITIES = {"강남구", "서울시", "서울"}


def candidate_record(row):
    """policy_candidates.json 한 줄 → 검색용 사업 정보."""
    return {
        "id": row["id"], "name": row["name"], "description": row["description"], "category": row["category"],
        "region": row["reference_region"], "target": "자료에 상세 자격 없음", "agency": "자료에 담당 기관 없음",
        "source": row["source_file"], "pages": str(row["source_pdf_pages"]), "status": UNCHECKED,
        "url": row.get("official_application_url"),
        "record_kind": "검토자료 추출항목", "notes": row.get("notes", ""),
        "information_kind": row.get("information_kind", "계획·검토 자료"),
        "current_operation_verified": bool(row.get("current_operation_verified")),
        "eligibility_reviewed": bool(row.get("eligibility_reviewed")),
        "application_details_verified": bool(row.get("application_details_verified")),
    }


def plan_record(index, row):
    """gangnam_policy_plans_2025.json 한 줄 → 검색용 사업 정보."""
    return {
        "id": f"plan-{index}", "name": row["사업명"], "description": row["지원내용"], "category": "지역 복지",
        "region": "강남구", "target": row["대상"], "agency": row["기관"], "source": row["출처파일"],
        "pages": row["PDF페이지"], "status": row["상태"], "url": None,
        "procedure": row.get("확인절차", ""), "plan_period": row.get("계획기간", ""),
        "record_kind": "사업계획", "information_kind": "2025년 사업계획",
        "current_operation_verified": False, "eligibility_reviewed": False,
        "application_details_verified": False,
    }


def resource_source():
    source = (os.getenv("WELFIND_WELFARE_SOURCE") or "db").strip().lower()
    if source not in {"db", "json"}:
        raise ValueError("WELFIND_WELFARE_SOURCE는 db 또는 json이어야 합니다.")
    return source


def load_resources():
    """요청할 때 DB를 조회하므로 DB 자료 수정은 서버 재시작 없이 반영됩니다."""
    if resource_source() == "json":
        candidates = json.loads((DATA / "policy_candidates.json").read_text(encoding="utf-8"))["records"]
        plans = list(enumerate(json.loads((DATA / "gangnam_policy_plans_2025.json").read_text(encoding="utf-8"))))
    else:
        candidates, plans = load_dataset_rows()
    records = [candidate_record(row) for row in candidates]
    records += [plan_record(index, row) for index, row in plans]
    # 같은 이름의 사업이 두 자료에 있으면, 대상·기관이 자세한 계획 자료(나중 것)를 씁니다.
    by_name = {}
    for record in records:
        by_name[record["name"]] = record
    return list(by_name.values())


def compact(text):
    """띄어쓰기·문장부호를 지운 비교용 문자열입니다(예: '세곡 동행의' → '세곡동행의')."""
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", text).lower()


def source_footer(records):
    """AI 답변 끝에 붙이는 출처·확인 상태 목록입니다. AI가 출처를 빠뜨려도 항상 보이게 합니다."""
    lines = []
    for record in records:
        line = f'- {record["name"]}: {record["source"]} (p. {record["pages"]}) · {record["status"]}'
        if line not in lines:
            lines.append(line)
    return "\n\n검토 자료와 확인 상태:\n" + "\n".join(lines) if lines else ""


def search(query, limit=5, *, city="", district=""):
    """질문과 관련 있는 사업을 점수 순으로 limit개까지 돌려줍니다."""
    if city and city not in COVERED_CITIES:
        return []
    if limit < 1:
        return []
    # 사업명 자체를 문장에서 찾습니다. 조사('세곡동행의/에')와 띄어쓰기를 허용합니다.
    # 사업을 콕 집어 물으면 일반 동의어로 찾은 다른 사업을 섞지 않습니다.
    resources = load_resources()
    named = [r for r in resources if len(compact(r["name"])) >= 3 and compact(r["name"]) in compact(query)]
    if named:
        named.sort(key=lambda r: (r["record_kind"] == "사업계획", len(compact(r["name"]))), reverse=True)
        return named[:limit]
    # 지원 분야는 실제 사업명·지원 내용으로 확인합니다. '청년/자립' 관련성만으로
    # 경제 지원을 주거 지원으로 추천하지 않습니다.
    if any(term in query for term in HOUSING_TERMS):
        resources = [r for r in resources if any(term in r["name"] + " " + r["description"] for term in HOUSING_TERMS)]
    if "자립준비청년" in compact(query):
        resources = [r for r in resources
                     if "자립준비청년" in compact(" ".join(str(r[f] or "") for f in ("name", "description", "category", "target")))]
    terms = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", query))
    for group in SYNONYM_GROUPS:
        if any(word in query for word in group):
            terms.update(group)

    ranked = []
    for resource in resources:
        body = " ".join(str(resource[field]) for field in SEARCH_FIELDS)
        score = 0
        for term in terms:
            if term in body:
                score += 4 if term in resource["name"] else 1  # 사업 이름에 있으면 더 크게 봅니다.
        # 지원 필요가 맞는 사업 중에서 선택한 동이 적힌 사업을 조금 더 앞에 둡니다.
        if score and district and district in body:
            score += 2
        if score:
            ranked.append((score, resource))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [resource for score, resource in ranked[:limit]]


def local_answer(records):
    """AI 없이 검색 결과만으로 만드는 안내문입니다."""
    if not records:
        return ("팀 자료에서 질문에 맞는 사업을 찾지 못했어요. 거주 지역과 필요한 지원(식사, 병원 동행, 주거, 관계 모임 등)을 "
                "알려주시면 다시 찾아볼게요. 현재 자료는 서울시·강남구 중심이며 다른 지역에 대한 안내는 제한됩니다. "
                "주민등록번호나 정확한 주소는 보내지 마세요.")
    blocks = ["팀 자료에서 관련 복지사업을 찾았어요. 아래 내용은 계획·검토 자료이며 현재 모집, 이용 자격, 지원금은 담당 기관에 확인해야 합니다."]
    for number, record in enumerate(records, 1):
        details = [f'{number}. {record["name"]}', f'지원 내용: {record["description"]}',
                   f'자료상 대상: {record["target"]}', f'기관: {record["agency"]}']
        if record.get("procedure"):
            details.append(f'자료상 확인·신청 절차: {record["procedure"]}')
        if record.get("plan_period"):
            details.append(f'자료상 계획기간: {record["plan_period"]} (현재 모집기간이 아님)')
        details.extend([f'확인 상태: {record["status"]}', f'출처: {record["source"]} (p. {record["pages"]})'])
        blocks.append("\n".join(details))
    blocks.append("다음 단계: 거주 지역 담당 주민센터 또는 자료에 나온 기관에 현재 운영 여부, 대상 조건, 신청 방법과 필요 서류를 확인해 주세요. "
                  "어떤 지역에서 어떤 지원을 찾고 계신가요?")
    return "\n\n".join(blocks)
