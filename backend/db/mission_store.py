"""담당자·지역·기준월별 미션 및 업무 기록 (공유 PostgreSQL work 스키마에 저장)."""
import hashlib
import json
from datetime import datetime

from sqlalchemy import text

from backend.db.work_store import lock, transaction

STEPS = ["분석 확인", "근거 검토·질의", "사업 매칭 검토", "보고서 완료"]
WORKFLOW_VERSION = 3

def normalize(item):
    """이전 업무 단계 번호를 현재 네 단계로 맞추고 기존 기록을 보존합니다."""
    if item.get("workflow_version") == 2:
        item = dict(item)
        old = set(item.get("done", []))
        done = old & {0, 1, 2}
        if 4 in old:
            done.add(3)
        item["done"] = sorted(done)
        item["workflow_version"] = WORKFLOW_VERSION
        item["legacy_connections"] = item.pop("connections", [])
        item["workflow_complete"] = 3 in item["done"]
        item["card_earned"] = item["workflow_complete"]
    elif item.get("workflow_version") != WORKFLOW_VERSION:
        return {"workflow_version": WORKFLOW_VERSION, "done": [], "reviews": [], "questions": [], "legacy": item}
    return item

def review_revision(item):
    """검토 내용의 지문으로 보고서 초안 이후 검토가 바뀌었는지 확인합니다."""
    reviews = json.dumps(item.get("reviews", []), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(reviews.encode()).hexdigest()

def identity(request):
    """SQLite 시절의 키 형식을 유지하여 옮겨 온 업무를 계속 찾습니다."""
    owner = request["user"]["id"]
    if request.get("workflow_mode") == "demo":
        owner = "demo:" + owner
    fields = [owner, request["city"], request["district"], request["month"]]
    return json.dumps(fields, ensure_ascii=False, separators=(",", ":"))

def load_all():
    with transaction() as db:
        items = {}
        for key, value in db.execute(text("SELECT key,value FROM work.missions")):
            items[key] = normalize(json.loads(value))
        return items

def timestamp():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")

def save_event(request, step, record=None):
    """단계 순서를 검사하고 기록·Word 파일·보고서 이력을 함께 저장합니다."""
    if step not in range(4):
        raise ValueError("유효하지 않은 업무 단계입니다.")
    if not request.get("district"):
        raise ValueError("행정동을 먼저 선택하세요.")
    key = identity(request)
    with transaction() as db:
        lock(db, key)
        row = db.execute(text("SELECT value FROM work.missions WHERE key=:key"), {"key": key}).fetchone()
        item = normalize(json.loads(row[0]) if row else {})
        done = set(item["done"])
        record = dict(record or {})
        if step > 0 and not set(range(step)).issubset(done):
            raise ValueError("분석 확인 → 근거 검토 → 사업 매칭 검토 → 보고서 저장 순서로 진행하세요.")
        if item.get("workflow_complete") and step in (1, 2):
            raise ValueError("보고서 완료된 업무는 수정할 수 없습니다. 새 업무로 진행하세요.")
        record["created_at"] = timestamp()
        record["actor"] = request["user"]["id"]
        item["is_demo"] = request.get("workflow_mode") == "demo"
        if step == 0:
            if not record.get("run_id") or not record.get("evidence"):
                raise ValueError("실제 DB1 분석 결과가 있어야 업무를 시작할 수 있습니다.")
            if 0 in done:
                # 이미 시작한 업무는 저장 당시 근거를 그대로 씁니다. 분석이 새로 적재돼도 다시 열 수 있습니다.
                return item
            item["analysis_run_id"] = record["run_id"]
            item["analysis_evidence"] = record["evidence"]
            item["analysis_source"] = record.get("source_note", "저장된 DB1 분석")
        elif step == 1:
            if record.get("question", "").strip():
                item["questions"].append(record)
            elif not record.get("confirmed"):
                raise ValueError("분석 근거 확인이 필요합니다.")
            item["evidence_reviewed_at"] = record["created_at"]
        elif step == 2:
            if not record.get("note", "").strip() or not record.get("service_key"):
                raise ValueError("사업과 매칭 검토 근거를 입력하세요.")
            if record.get("decision") not in ["적합", "보류", "부적합"]:
                raise ValueError("검토 결과가 필요합니다.")
            item["reviews"].append(record)
        elif step == 3:
            if not all(record.get(field) for field in ["sha256", "filename", "author", "department", "opinion", "confirmed"]):
                raise ValueError("보고서 파일과 필수 항목, 최종 확인이 필요합니다.")
            if record.get("review_id") != review_revision(item):
                raise ValueError("현재 사업 검토 내역과 일치하는 보고서가 필요합니다.")
            document = record.pop("_document", b"")
            if not document or hashlib.sha256(document).hexdigest() != record["sha256"]:
                raise ValueError("실제 보고서 파일을 생성한 후 저장하세요.")
            revision = db.execute(text("SELECT COALESCE(MAX(revision),0) FROM work.report_versions WHERE key=:key"),
                                  {"key": key}).scalar_one()
            previous = db.execute(text("SELECT document FROM work.report_files WHERE key=:key"), {"key": key}).fetchone()
            insert_version = text("INSERT INTO work.report_versions (key,revision,document,record) "
                                  "VALUES (:key,:revision,:document,:record)")
            # 이 기능 도입 전에 저장된 보고서도 첫 재작성 시 이력에 남깁니다.
            if previous and revision == 0:
                revision = 1
                db.execute(insert_version, dict(key=key, revision=revision, document=bytes(previous[0]),
                                                record=json.dumps(item.get('report', {}), ensure_ascii=False)))
            record['revision'] = revision + 1
            record['analysis_run_id'] = item.get('analysis_run_id')
            db.execute(insert_version, dict(key=key, revision=record['revision'], document=document,
                                            record=json.dumps(record, ensure_ascii=False)))
            db.execute(text("""INSERT INTO work.report_files (key,document) VALUES (:key,:document)
                ON CONFLICT (key) DO UPDATE SET document=excluded.document"""), {"key": key, "document": document})
            item["report"] = record
        done.add(step)
        item["done"] = sorted(done)
        item["card_earned"] = 3 in done
        item["workflow_complete"] = 3 in done
        db.execute(text("""INSERT INTO work.missions (key,value) VALUES (:key,:value)
            ON CONFLICT (key) DO UPDATE SET value=excluded.value"""), {"key": key, "value": json.dumps(item, ensure_ascii=False)})
    return item


def restart(request, record):
    """저장된 근거가 지금 분석과 다를 때 업무를 최신 분석으로 다시 시작합니다(① 분석 확인까지 저장).

    이전 회차의 진행 기록은 previous_rounds에 보관합니다. 보고서 파일은 report_versions에 남아
    다음 저장 때 차수가 이어집니다.
    """
    if not record.get("run_id") or not record.get("evidence"):
        raise ValueError("실제 DB1 분석 결과가 있어야 업무를 시작할 수 있습니다.")
    if not request.get("district"):
        raise ValueError("행정동을 먼저 선택하세요.")
    key = identity(request)
    with transaction() as db:
        lock(db, key)
        row = db.execute(text("SELECT value FROM work.missions WHERE key=:key"), {"key": key}).fetchone()
        item = normalize(json.loads(row[0]) if row else {})
        if 0 not in item.get("done", []):
            raise ValueError("아직 시작하지 않은 업무입니다. 상세 분석·업무 시작을 누르세요.")
        if item.get("analysis_run_id") == record["run_id"]:
            raise ValueError("이미 최신 분석으로 진행 중인 업무입니다.")
        previous = item.pop("previous_rounds", [])
        item["ended_at"] = timestamp()
        restarted = {
            "workflow_version": WORKFLOW_VERSION, "done": [0], "reviews": [], "questions": [],
            "is_demo": request.get("workflow_mode") == "demo",
            "card_earned": False, "workflow_complete": False,
            "analysis_run_id": record["run_id"], "analysis_evidence": record["evidence"],
            "analysis_source": record.get("source_note", "저장된 DB1 분석"),
            "previous_rounds": previous + [item],
        }
        db.execute(text("""INSERT INTO work.missions (key,value) VALUES (:key,:value)
            ON CONFLICT (key) DO UPDATE SET value=excluded.value"""),
                   {"key": key, "value": json.dumps(restarted, ensure_ascii=False)})
        # 검토·후속 조치 기록도 같은 트랜잭션에서 회차를 나눕니다(순환 import를 피해 여기서 불러옵니다).
        from backend.db import experience_store
        experience_store.start_new_round(db, request, item.get("analysis_run_id"))
    return restarted


# 시·군·구 → (시·도, 옛 시·도 표기). 연계 후보는 이 시·도 자료에서만 고릅니다.
LOCAL_PROVINCES = {"강남구": ("서울특별시", "서울특별시"),
                   "춘천시": ("강원특별자치도", "강원도")}


def service_candidates(city):
    """주기 수집된 지자체 사업을 검토 후보로 조회합니다. 게시 지역은 자격이 아닙니다."""
    from sqlalchemy import text
    from backend.db.analysis_repository import get_engine
    from datetime import datetime
    from zoneinfo import ZoneInfo
    provinces = LOCAL_PROVINCES.get(city)
    if not provinces:
        return []
    query = text("""SELECT s.*,
            'local_welfare_api' AS source_id,
            s.province || ':' || COALESCE(s.district, '') AS region_id,
            s.service_id AS external_id,
            s.benefit_text AS support_text,
            'unknown' AS coverage_scope,
            '지원 대상·거주 조건은 원문 및 운영기관 확인 필요' AS residency_text
        FROM db2.local_welfare_services s
        WHERE s.province IN (:province, :province_alias)
          AND (s.district = :city OR COALESCE(TRIM(s.district), '') IN ('', '-'))
          AND (s.effective_start IS NULL OR s.effective_start <= :today)
          AND (s.effective_end IS NULL OR s.effective_end >= :today)
        ORDER BY s.name, s.service_id""")
    with get_engine().connect() as db:
        return [dict(row) for row in db.execute(query, {
            "province": provinces[0], "province_alias": provinces[1], "city": city,
            "today": datetime.now(ZoneInfo('Asia/Seoul')).date()}).mappings()]


REFERENCE_FIELDS = ["name", "summary", "benefit_text"]


def reference_services(city, terms, limit=20):
    """다른 지역 사업을 새 사업 기획의 참고 사례로 찾습니다. 선택 지역 주민의 연계 후보가 아닙니다.

    사업 내용(이름·요약·지원 내용)에 관련어가 많이 들어 있는 순서로 limit건까지 돌려줍니다.
    service_candidates가 고르는 자료(같은 시·군·구와 같은 시·도의 지역 미지정 자료)는 제외합니다.
    """
    from sqlalchemy import text
    from backend.db.analysis_repository import get_engine
    from datetime import datetime
    from zoneinfo import ZoneInfo
    terms = list(dict.fromkeys(term for term in terms if term))
    if not terms:
        return []
    params = {"today": datetime.now(ZoneInfo('Asia/Seoul')).date()}
    corpus = " || ' ' || ".join(f"COALESCE(s.{field}, '')" for field in REFERENCE_FIELDS)
    like = []
    for index, term in enumerate(terms):
        params[f"t{index}"] = f"%{term}%"
        like.append(f"({corpus}) LIKE :t{index}")
    local = "FALSE"
    provinces = LOCAL_PROVINCES.get(city)
    if provinces:
        params.update(province=provinces[0], province_alias=provinces[1], city=city)
        # NULL이 섞여도 NOT(...)이 참·거짓으로만 나오도록 COALESCE로 감쌉니다.
        local = """COALESCE(s.province, '') IN (:province, :province_alias)
            AND (s.district = :city OR COALESCE(TRIM(s.district), '') IN ('', '-'))"""
    # 원문 JSON(list_payload·detail_payload)은 크므로 화면에 쓰는 열만 읽습니다.
    query = text(f"""SELECT s.service_id, s.name, s.province, s.district, s.summary,
            s.target_text, s.eligibility_text, s.benefit_text, s.application_text,
            s.effective_start, s.effective_end, s.source_url, s.detail_pending,
            s.detail_checked_at, s.benefit_text AS support_text,
            'local_welfare_api' AS source_id
        FROM db2.local_welfare_services s
        WHERE ({' OR '.join(like)})
          AND NOT ({local})
          AND (s.effective_start IS NULL OR s.effective_start <= :today)
          AND (s.effective_end IS NULL OR s.effective_end >= :today)""")
    with get_engine().connect() as db:
        rows = [dict(row) for row in db.execute(query, params).mappings()]
    for row in rows:
        content = " ".join(str(row.get(field) or "") for field in REFERENCE_FIELDS)
        row["matched_terms"] = [term for term in terms if term in content]
    rows.sort(key=lambda row: (-len(row["matched_terms"]), row["name"], row["service_id"]))
    return rows[:limit]


def service_key(service):
    if service.get('source_id') == 'local_welfare_api':
        # 명칭·지역 표기가 갱신되어도 API 서비스 ID로 같은 사업을 식별합니다.
        return json.dumps(['local_welfare_api', service['service_id']], ensure_ascii=False)
    return json.dumps([service["source_id"], service["region_id"], service["external_id"]], ensure_ascii=False)


def load_report(request, revision=None):
    """저장한 보고서 파일입니다. revision이 없으면 최신본, 있으면 그 저장본입니다."""
    with transaction() as db:
        if revision is None:
            row = db.execute(text("SELECT document FROM work.report_files WHERE key=:key"), {"key": identity(request)}).fetchone()
        else:
            row = db.execute(text("SELECT document FROM work.report_versions WHERE key=:key AND revision=:revision"),
                             {"key": identity(request), "revision": revision}).fetchone()
        return bytes(row[0]) if row else None


def report_versions(request):
    """이 업무에서 최종 저장한 보고서 목록(최신순). 파일 본문은 넣지 않습니다."""
    with transaction() as db:
        rows = db.execute(text("SELECT revision, record FROM work.report_versions WHERE key=:key ORDER BY revision DESC"),
                          {"key": identity(request)}).fetchall()
    items = []
    for revision, record in rows:
        record = json.loads(record or "{}")
        items.append({"revision": revision, "created_at": record.get("created_at", ""),
                      "author": record.get("author", ""), "department": record.get("department", ""),
                      "title": (record.get("content") or {}).get("title", ""),
                      "analysis_run_id": record.get("analysis_run_id", "")})
    return items
