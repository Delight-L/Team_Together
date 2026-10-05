"""담당자·지역·기준월별 미션 및 업무 기록 (로컬 SQLite 영구 저장)."""
import json
from contextlib import contextmanager
import sqlite3
from pathlib import Path
from datetime import datetime

STORE = Path(__file__).resolve().parent / "data" / "mission_records.sqlite3"
STEPS = ["분석 확인", "근거 검토·질의", "사업 매칭 검토", "보고서 완료"]
WORKFLOW_VERSION = 3

def normalize(item):
    if item.get("workflow_version") == 2:
        item = dict(item)
        old = set(item.get("done", []))
        item["done"] = sorted((old & {0,1,2}) | ({3} if 4 in old else set()))
        item["workflow_version"] = WORKFLOW_VERSION
        item["legacy_connections"] = item.pop("connections", [])
        item["workflow_complete"] = 3 in item["done"]
        item["card_earned"] = item["workflow_complete"]
    elif item.get("workflow_version") != WORKFLOW_VERSION:
        return {"workflow_version": WORKFLOW_VERSION, "done": [], "reviews": [], "questions": [], "legacy": item}
    return item

def review_revision(item):
    import hashlib
    return hashlib.sha256(json.dumps(item.get("reviews", []),sort_keys=True,ensure_ascii=False).encode()).hexdigest()

@contextmanager
def connection():
    STORE.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(STORE)
    db.execute("CREATE TABLE IF NOT EXISTS missions (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    try:
        with db:
            yield db
    finally:
        db.close()

def identity(request):
    return json.dumps([("demo:" if request.get("workflow_mode") == "demo" else "") + request["user"]["id"], request["city"], request["district"], request["month"]], ensure_ascii=False, separators=(",", ":"))

def load_all():
    with connection() as db:
        return {key: normalize(json.loads(value)) for key, value in db.execute("SELECT key,value FROM missions")}

def timestamp():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")

def save_event(request, step, record=None):
    if step not in range(4):
        raise ValueError("유효하지 않은 업무 단계입니다.")
    if not request.get("district"):
        raise ValueError("행정동을 먼저 선택하세요.")
    key = identity(request)
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT value FROM missions WHERE key=?", (key,)).fetchone()
        item = normalize(json.loads(row[0]) if row else {})
        done = set(item["done"])
        record = dict(record or {})
        if step > 0 and not set(range(step)).issubset(done):
            raise ValueError("분석 확인 → 근거 검토 → 사업 매칭 검토 → 보고서 저장 순서로 진행하세요.")
        if item.get("workflow_complete") and step >= 1:
            raise ValueError("보고서 완료된 업무는 수정할 수 없습니다. 새 업무로 진행하세요.")
        record["created_at"] = timestamp()
        record["actor"] = request["user"]["id"]
        item["is_demo"] = request.get("workflow_mode") == "demo"
        if step == 0:
            if not record.get("run_id") or not record.get("evidence"):
                raise ValueError("실제 DB1 분석 결과가 있어야 업무를 시작할 수 있습니다.")
            if item.get("analysis_run_id") and item["analysis_run_id"] != record["run_id"]:
                raise ValueError("이 업무에 저장된 분석 버전과 다릅니다. 저장된 근거를 확인하세요.")
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
            import hashlib
            document = record.pop("_document", b"")
            if not document or hashlib.sha256(document).hexdigest() != record["sha256"]:
                raise ValueError("실제 보고서 파일을 생성한 후 저장하세요.")
            db.execute("CREATE TABLE IF NOT EXISTS report_files (key TEXT PRIMARY KEY, document BLOB NOT NULL)")
            db.execute("INSERT OR REPLACE INTO report_files VALUES (?,?)", (key, document))
            item["report"] = record
        done.add(step)
        item["done"] = sorted(done)
        item["card_earned"] = 3 in done
        item["workflow_complete"] = 3 in done
        db.execute("INSERT OR REPLACE INTO missions VALUES (?,?)", (key, json.dumps(item, ensure_ascii=False)))
    return item


def service_candidates(city):
    """DB2의 검토된 이용 범위로 조회. 게시 지역을 이용 자격으로 간주하지 않습니다."""
    from sqlalchemy import text
    from dashboard.pipeline import get_engine
    region = {"강남구": "gangnam", "춘천시": "chuncheon"}.get(city)
    if not region:
        return []
    query = text("""SELECT s.* FROM db2.reviewed_service_candidates s
        WHERE s.coverage_scope = 'national' OR EXISTS (
        SELECT 1 FROM db2.service_coverage c
        WHERE (c.source_id,c.provider_region_id,c.service_id) = (s.source_id,s.region_id,s.external_id)
        AND c.eligible_region_id = :region)
        ORDER BY s.name""")
    with get_engine().connect() as db:
        return [dict(row) for row in db.execute(query, {"region": region}).mappings()]

def service_key(service):
    return json.dumps([service["source_id"], service["region_id"], service["external_id"]], ensure_ascii=False)


def load_report(request):
    with connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS report_files (key TEXT PRIMARY KEY, document BLOB NOT NULL)")
        row = db.execute("SELECT document FROM report_files WHERE key=?", (identity(request),)).fetchone()
        return row[0] if row else None
