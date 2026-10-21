"""공유 DB2의 복지사업 검색. JSON은 명시한 오프라인 검증 모드에서만 읽습니다."""

import json
import os
import re
from pathlib import Path

import threading
import time

from backend.common import seoul_now
from backend.chatbot.welfare.app.dialogue.query_rules import (
    compact,
    excludes_past,
    named_program,
    filter_target_records,
    select_recommendations,
)

from backend.db.welfare_chatbot_repository import (
    catalog_counts,
    database_id,
    load_dataset_rows,
    search_catalog,
)

DATA = Path(__file__).resolve().parents[2] / "data"

UNCHECKED = "계획·검토 자료 / 현재 운영 및 자격 미확인"
# 질문에 한 단어라도 있으면 같은 묶음의 다른 단어로도 찾습니다(예: '외로워' → 고립·관계·모임).
SYNONYM_GROUPS = [
    ("외로", "고립", "관계", "모임", "친구", "소통"),
    ("병원", "건강", "의료", "동행"),
    ("식사", "밥", "식생활", "요리", "식비", "급식", "도시락"),
    ("청년", "취업", "자립"),
    ("어르신", "노인", "고령", "돌봄"),
    ("주거", "집", "월세", "주택"),
]
SEARCH_FIELDS = ("name", "description", "category", "region", "target", "agency")
HOUSING_TERMS = ("주거", "주택", "월세", "임대", "보증금", "집수리")
# 서울·강남 자료이므로 다른 지역(춘천 등)에는 이용 가능한 사업으로 안내하지 않습니다.
COVERED_CITIES = {"강남구", "서울시", "서울"}
GENERAL_TERMS = {
    "지원",
    "사업",
    "서비스",
    "복지",
    "복지사업",
    "복지서비스",
    "프로그램",
    "추천",
    "추천해줘",
    "알려줘",
    "알려주세요",
    "찾아줘",
    "찾아주세요",
    "있나요",
    "있어",
    "대상",
    "대상은",
    "신청",
    "방법",
    "내용",
    "담당",
    "기관",
    "필요",
    "현재",
    "가능한",
    "강남구",
    "춘천시",
    "강남",
    "춘천",
    "서울",
    "서울시",
    "지원사업",
    "관련",
    "이번에는",
}


def candidate_record(row):
    """policy_candidates.json 한 줄 → 검색용 사업 정보."""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "region": row["reference_region"],
        "target": "자료에 상세 자격 없음",
        "agency": "자료에 담당 기관 없음",
        "source": row["source_file"],
        "pages": str(row["source_pdf_pages"]),
        "status": UNCHECKED,
        "url": row.get("official_application_url"),
        "record_kind": "검토자료 추출항목",
        "source_type": "document",
        "notes": row.get("notes", ""),
        "information_kind": row.get("information_kind", "계획·검토 자료"),
        "current_operation_verified": bool(row.get("current_operation_verified")),
        "eligibility_reviewed": bool(row.get("eligibility_reviewed")),
        "application_details_verified": bool(row.get("application_details_verified")),
    }


def plan_record(index, row):
    """gangnam_policy_plans_2025.json 한 줄 → 검색용 사업 정보."""
    return {
        "id": f"plan-{index}",
        "name": row["사업명"],
        "description": row["지원내용"],
        "category": "지역 복지",
        "region": "강남구",
        "target": row["대상"],
        "agency": row["기관"],
        "source": row["출처파일"],
        "pages": row["PDF페이지"],
        "status": row["상태"],
        "url": None,
        "procedure": row.get("확인절차", ""),
        "plan_period": row.get("계획기간", ""),
        "record_kind": "사업계획",
        "source_type": "document",
        "information_kind": "2025년 사업계획",
        "current_operation_verified": False,
        "eligibility_reviewed": False,
        "application_details_verified": False,
    }


def resource_source():
    source = (os.getenv("WELFIND_WELFARE_SOURCE") or "db").strip().lower()
    if source not in {"db", "json"}:
        raise ValueError("WELFIND_WELFARE_SOURCE는 db 또는 json이어야 합니다.")
    return source


def _read_resources():
    """요청할 때 DB를 조회하므로 DB 자료 수정은 서버 재시작 없이 반영됩니다."""
    if resource_source() == "json":
        candidates = json.loads((DATA / "policy_candidates.json").read_text(encoding="utf-8"))[
            "records"
        ]
        plans = list(
            enumerate(
                json.loads((DATA / "gangnam_policy_plans_2025.json").read_text(encoding="utf-8"))
            )
        )
    else:
        candidates, plans = load_dataset_rows()
    records = [candidate_record(row) for row in candidates]
    records += [plan_record(index, row) for index, row in plans]
    # 같은 이름의 사업이 두 자료에 있으면, 대상·기관이 자세한 계획 자료(나중 것)를 씁니다.
    by_name = {}
    for record in records:
        by_name[record["name"]] = record
    return list(by_name.values())


def database_record(row):
    """API·검토 서비스·사업 회차를 챗봇의 공통 자료 형식으로 바꿉니다."""
    kind = row["kind"]
    parts = (
        [row["external_id"]]
        if kind == "api"
        else [row["source_id"], row["region_id"], row["external_id"]]
    )
    if kind == "session":
        parts.append(row["session_id"])
    today = seoul_now().date()
    start, end = row.get("effective_start"), row.get("effective_end")
    expired = bool(end and end < today)
    future = bool(start and start > today)
    application_closed = bool(row.get("application_end") and row["application_end"] < today)
    application_future = bool(row.get("application_start") and row["application_start"] > today)
    reference = not bool(row.get("local_scope", True))
    status = (
        "과거 공고·종료 / 현재 이용 안내용이 아님"
        if expired
        else "예정 자료 / 현재 운영 미확인"
        if future
        else "공개 안내 자료 / 현재 운영·자격·접수 별도 확인 필요"
    )
    if application_closed:
        status += " / 접수기간 종료"
    elif application_future:
        status += " / 접수 시작 전"
    if row.get("detail_pending"):
        status += " / 상세정보 수집 대기"
    if row.get("review_status") == "pending":
        status += " / 검토 대기"
    if reference:
        status += " / 다른 지역 참고 사례"

    def stamp(value):
        return value.isoformat() if hasattr(value, "isoformat") else str(value or "")

    return {
        "id": database_id(kind, *parts),
        "name": row["name"],
        "description": row.get("benefit_text") or row.get("summary") or "원문 지원 내용 확인 필요",
        "summary": row.get("summary") or "",
        "category": "복지서비스" if kind != "session" else "사업 공고",
        "region": " ".join(str(row.get(k) or "") for k in ("province", "district")).strip()
        or "지역 미확인",
        "target": "\n".join(
            dict.fromkeys(str(row[k]) for k in ("target_text", "eligibility_text") if row.get(k))
        )
        or "원문 대상 조건 확인 필요",
        "agency": row.get("agency") or "원문 담당 기관 확인 필요",
        "procedure": row.get("application_text") or "",
        "contacts": row.get("contacts") or [],
        "source": row["source_name"],
        "pages": "",
        "status": status,
        "url": row.get("source_url"),
        "application_url": row.get("application_url"),
        "source_type": kind,
        "record_kind": "공개 복지서비스" if kind != "session" else "사업 회차 공고",
        "information_kind": "공공 API 안내" if kind == "api" else "DB 등록 안내 자료",
        "period": row.get("period_text") or "",
        "session_name": row.get("session_name") or "",
        "effective_start": stamp(start),
        "effective_end": stamp(end),
        "application_start": stamp(row.get("application_start")),
        "application_end": stamp(row.get("application_end")),
        "source_updated_date": stamp(row.get("source_modified")),
        "collected_at": stamp(row.get("detail_checked_at")),
        "reference_only": reference,
        "expired": expired,
        "future": future,
        "application_closed": application_closed,
        "application_future": application_future,
        "notes": row.get("residency_text")
        or "지역 표기는 자료의 적용 범위이며 신청 자격을 보장하지 않습니다.",
        "review_status": row.get("review_status") or "unreviewed",
        "current_operation_verified": False,
        "eligibility_reviewed": False,
        "application_details_verified": False,
    }


def resource_counts():
    """설정 화면용 개수. 현재 모집 중인 사업 수와는 다릅니다."""
    return {"documents": len(load_resources())} if resource_source() == "json" else catalog_counts()


def get_resources_by_ids(resource_ids, *, city=""):
    if not resource_ids:
        return []
    by_id = {r["id"]: r for r in load_resources()}
    if city and city not in COVERED_CITIES:
        by_id = {
            key: dict(r, reference_only=True, status=r["status"] + " / 다른 지역 참고 사례")
            for key, r in by_id.items()
        }
    if resource_source() == "db":
        by_id.update(
            (r["id"], r)
            for r in (
                database_record(row)
                for row in search_catalog("", city=city, resource_ids=list(resource_ids), limit=10)
            )
        )
    return [by_id[key] for key in dict.fromkeys(resource_ids) if key in by_id]


def search_terms(query):
    terms = set(re.findall(r"[가-힣a-zA-Z0-9]{2,}", query))
    terms.update(
        re.sub(r"(?:에게|에서|으로|에는|을|를|은|는|이|가|의)$", "", term)
        for term in list(terms)
        if len(term) > 3
    )
    specific = terms - GENERAL_TERMS
    if specific:
        terms = specific
    for group in SYNONYM_GROUPS:
        if any(word in query for word in group):
            terms.update(group)
    return terms


def browse_request(query):
    """지원 분야 없는 목록 조회만 허용합니다. 주거·돌봄 등 구체 조건은 검색을 유지합니다."""
    text = compact(query)
    if not any(word in text for word in ('복지', '서비스', '사업')):
        return False
    # 요청 표현을 제외하고 내용 조건이 남으면 전체 목록으로 넓히지 않습니다.
    text = re.sub(r'\d{1,2}대(?:에게|에)?', '', text)
    words = (
        '이연령대에',
        '이나이대에',
        '추천해줄만한',
        '참고할만한',
        '참고할수있는',
        '참고하려고하니까',
        '전국에',
        '전국의',
        '전국',
        '다른지역의',
        '다른지역',
        '다른',
        '복지서비스들은',
        '복지서비스는',
        '복지서비스',
        '복지사업',
        '복지',
        '서비스들은',
        '서비스는',
        '서비스',
        '사업들은',
        '사업은',
        '사업',
        '어떤게',
        '어떤것이',
        '있어',
        '있나요',
        '없어',
        '보여주세요',
        '보여줘',
        '찾아주세요',
        '찾아줘',
        '알려주세요',
        '알려줘',
        '추천해주세요',
        '추천해줘',
    )
    text = re.sub(
        '|'.join(re.escape(word) for word in sorted(words, key=len, reverse=True)), '', text
    )
    return not text


def has_program_name(query, *, city=""):
    terms = search_terms(query)
    documents = load_resources() if not city or city in COVERED_CITIES else []
    if any(
        named_program(query, r['name']) or any(term in r["name"] for term in terms)
        for r in documents
    ):
        return True
    return resource_source() == "db" and bool(
        search_catalog(query, terms, city=city, name_only=True, include_past=True, limit=1)
    )


def named_document_requested(query):
    """조건으로 제외되기 전의 고유 문서 사업명이 질문에 명시됐는지 확인합니다."""
    return any(named_program(query, record['name']) for record in load_resources())


def source_citation(record):
    citation = record["source"]
    if record.get("pages"):
        citation += f' (p. {record["pages"]})'
    elif record.get("url"):
        citation += f' · {record["url"]}'
    if record.get("collected_at"):
        citation += f' · 자료 수집일 {record["collected_at"][:10]} (운영 확인일 아님)'
    if record.get("snapshot_hash"):
        citation += ' · 대화 당시 보존 자료'
    return citation


def search(query, limit=5, *, city="", district="", include_reference=False, include_past=False):
    """질문과 관련 있는 사업을 점수 순으로 limit개까지 돌려줍니다."""
    if limit < 1:
        return []
    past_excluded = excludes_past(query)
    include_past = include_past and not past_excluded
    # 사업명 자체를 문장에서 찾습니다. 조사('세곡동행의/에')와 띄어쓰기를 허용합니다.
    # 사업을 콕 집어 물으면 일반 동의어로 찾은 다른 사업을 섞지 않습니다.
    documents = load_resources()
    requested_document = any(named_program(query, r['name']) for r in documents)
    resources = documents if not city or city in COVERED_CITIES or include_reference else []
    if city and city not in COVERED_CITIES and include_reference:
        resources = [
            dict(r, reference_only=True, status=r["status"] + " / 다른 지역 참고 사례")
            for r in resources
        ]
    if (asks_current_recruitment(query) or past_excluded) and not include_past:
        resources = [
            r
            for r in resources
            if r.get("current_operation_verified") and r.get("application_details_verified")
        ]
    terms = search_terms(query)
    browse = browse_request(query)
    if browse:
        terms = set()  # '다른', '참고' 같은 요청 표현을 사업 내용의 관련성으로 계산하지 않습니다.
    if resource_source() == "db":
        resources += [
            database_record(row)
            for row in search_catalog(
                query,
                terms,
                city=city,
                include_reference=include_reference,
                include_past=include_past,
                browse=browse,
                support_terms=HOUSING_TERMS if any(term in query for term in HOUSING_TERMS) else (),
                target_term="자립준비청년" if "자립준비청년" in compact(query) else "",
            )
        ]
    named = [r for r in resources if named_program(query, r['name'])]
    if named:
        named.sort(
            key=lambda r: (r.get("source_type") != "document", len(compact(r["name"]))),
            reverse=True,
        )
        return named[:limit]
    if requested_document:
        # 명시한 사업이 지역·기간 조건에서 제외됐다면 다른 사업으로 대체하지 않습니다.
        return []
    resources = filter_target_records(query, resources)
    # 지원 분야는 실제 사업명·지원 내용으로 확인합니다. '청년/자립' 관련성만으로
    # 경제 지원을 주거 지원으로 추천하지 않습니다.
    if any(term in query for term in HOUSING_TERMS):
        resources = [
            r
            for r in resources
            if any(term in r["name"] + " " + r["description"] for term in HOUSING_TERMS)
        ]
    if "자립준비청년" in compact(query):
        resources = [
            r
            for r in resources
            if "자립준비청년"
            in compact(
                " ".join(str(r[f] or "") for f in ("name", "description", "category", "target"))
            )
        ]
    ranked = []
    for resource in resources:
        body = " ".join(str(resource[field]) for field in SEARCH_FIELDS)
        score = 1 if browse else 0
        for term in terms:
            if term in body:
                score += 4 if term in resource["name"] else 1  # 사업 이름에 있으면 더 크게 봅니다.
        # 지원 필요가 맞는 사업 중에서 선택한 동이 적힌 사업을 조금 더 앞에 둡니다.
        if score and district and district in body:
            score += 2
        if score and resource.get("source_type") != "document":
            score += 2  # 상세 API 안내를 검토 문서의 짧은 설명 조각보다 우선합니다.
        if resource.get("reference_only") and not (browse and include_reference):
            score = score / 2
        if score:
            ranked.append((score, resource))
    ranked.sort(
        key=lambda item: (
            bool(browse and include_reference and item[1].get('reference_only')),
            item[0],
        ),
        reverse=True,
    )
    return select_recommendations([resource for score, resource in ranked], limit)


def local_answer(records, question=""):
    """AI 없이도 요청한 항목만 안내하고 출처는 sources 이벤트로 제공합니다."""
    from backend.chatbot.welfare.app.dialogue.presentation import (
        brief_description,
        record_cautions,
        requested_fields,
    )

    if not records:
        return "관련 복지사업 자료를 찾지 못했어요. 거주 지역과 필요한 지원을 알려 주세요."
    fields = requested_fields(question)
    detailed = any(word in question for word in ('자세히', '상세', '전체 내용'))
    if detailed:
        fields = [
            ('description', '지원 내용'),
            ('target', '자료상 대상'),
            ('procedure', '자료상 신청 절차'),
            ('agency', '담당 기관'),
            ('period', '기간 안내'),
        ]
    blocks = []
    grouped = not fields and any(r.get('support_role') == 'living' for r in records)
    heading = None
    for number, record in enumerate(records, 1):
        if grouped:
            section = (
                '함께 확인할 생활비 지원'
                if record.get('support_role') == 'living'
                else '돌봄 관련 지원'
            )
            if section != heading:
                blocks.append(section)
                heading = section
        caution = record_cautions(record)
        title = f'{number}. {record["name"]}' + (f' · {" / ".join(caution)}' if caution else '')
        if fields:
            details = [title]
            for key, label in fields:
                value = record.get(key)
                if key == 'period':
                    value = record.get('period') or record.get('plan_period')
                    if record.get('application_start') or record.get('application_end'):
                        value = f"공고상 접수기간: {record.get('application_start') or '미기재'} ~ {record.get('application_end') or '미기재'}"
                details.append(f'{label}: {value or "자료에 미기재 · 담당 기관 확인 필요"}')
            blocks.append("\n".join(details))
        else:
            blocks.append(
                f'{title}\n{brief_description(record.get("description", "지원 내용은 원문 확인 필요"))}'
            )
    blocks.append(
        '현재 운영 여부·이용 자격·신청 절차는 담당 기관 확인이 필요해요. 출처는 참고 자료에서 볼 수 있어요.'
    )
    return "\n\n".join(blocks)


def asks_current_recruitment(query):
    return bool(
        re.search(
            r"(?:현재|지금|오늘|모집중|접수중|신청가능).*(?:모집|접수|신청|사업)|(?:모집|접수)중",
            compact(query),
        )
    )


def retrieval_corpus(*, city="", include_reference=False, include_past=False):
    """의미 검색도 키워드 검색과 동일한 SQL 지역·기간 경계를 사용합니다."""
    rows = load_resources() if not city or city in COVERED_CITIES or include_reference else []
    if city and city not in COVERED_CITIES:
        rows = [
            dict(r, reference_only=True, status=r["status"] + " / 다른 지역 참고 사례")
            for r in rows
        ]
    if resource_source() == "db":
        offset = 0
        while True:
            batch = search_catalog(
                "",
                city=city,
                include_reference=include_reference,
                include_past=include_past,
                browse=True,
                limit=200,
                offset=offset,
            )
            rows.extend(database_record(r) for r in batch)
            if not batch:
                break
            offset += 200
    return rows


CACHE_SECONDS = 60
_cache = {"at": 0.0, "source": None, "records": None}
_cache_lock = threading.Lock()


def clear_cache():
    with _cache_lock:
        _cache.update(at=0.0, source=None, records=None)


def load_resources():
    """팀 문서의 DB 왕복을 1분간 재사용합니다. API·공고는 별도 SQL로 최신 조회합니다."""
    source = resource_source()
    with _cache_lock:
        if _cache["source"] != source or time.monotonic() - _cache["at"] >= CACHE_SECONDS:
            _cache.update(records=_read_resources(), source=source, at=time.monotonic())
        return [dict(record) for record in _cache["records"]]
