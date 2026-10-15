"""Immutable, local serving snapshots for the monthly replay pipeline."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def runtime_dir(database: str | Path) -> Path:
    database = Path(database)
    # The production DB keeps the documented outputs/runtime location.  Ad-hoc
    # verification DBs get their own pointer so one test cannot redirect another.
    return database.parent / ("runtime" if database.name == "db1.sqlite" else f"{database.stem}.runtime")


def active_snapshot(database: str | Path) -> dict | None:
    pointer = runtime_dir(database) / "active_snapshot.json"
    if not pointer.is_file():
        return None
    return json.loads(pointer.read_text(encoding="utf-8"))


def resolve_database(database: str | Path) -> Path:
    """Return the active immutable DB when it exists, otherwise the caller DB.

    The fallback keeps command-line and isolated test DBs usable before first publish.
    """
    pointer = active_snapshot(database)
    if not pointer:
        return Path(database)
    candidate = Path(pointer.get("database", ""))
    if candidate.is_file() and _sha256(candidate) == pointer.get("sha256"):
        return candidate
    snapshots = runtime_dir(database) / "snapshots"
    for manifest_path in sorted(snapshots.glob("db1-*.json"), reverse=True):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        prior = Path(manifest.get("database", ""))
        if prior.is_file() and _sha256(prior) == manifest.get("sha256"):
            return prior
    raise ValueError("공개 snapshot이 손상되었고 복구할 이전 공개본이 없습니다.")


def publish(database: str | Path, period: str | None = None) -> dict:
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(database)
    con = sqlite3.connect(database)
    try:
        state = con.execute("SELECT payload_json FROM pipeline_state WHERE id=1").fetchone()
        status = json.loads(state[0]).get("status") if state else None
        if status != "ready":
            raise ValueError("완료(ready) 상태의 작업 DB만 공개할 수 있습니다.")
        coverage = period or con.execute("SELECT MAX(date) FROM a2_feature").fetchone()[0]
        rows = con.execute("SELECT COUNT(*) FROM a2_feature").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = con.execute("PRAGMA foreign_key_check").fetchall()
        imports = dict(con.execute("SELECT path,sha256 FROM input_import ORDER BY path").fetchall())
    finally:
        con.close()
    if integrity != "ok" or foreign_keys:
        raise ValueError("공개 전 DB 무결성 검사에 실패했습니다.")
    runtime = runtime_dir(database)
    snapshots = runtime / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"db1-{str(coverage)[:7].replace('-', '')}-{_sha256(database)[:12]}"
    target = snapshots / f"{snapshot_id}.sqlite"
    if target.exists():
        check = sqlite3.connect(target)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("기존 snapshot 파일이 손상되었습니다.")
        finally:
            check.close()
    if not target.exists():
        # SQLite backup creates a consistent database image even when a WAL file
        # exists.  The temporary file is only made visible after integrity checks.
        temporary = target.with_suffix(".sqlite.tmp")
        temporary.unlink(missing_ok=True)
        try:
            source = sqlite3.connect(database)
            destination = sqlite3.connect(temporary)
            try:
                source.backup(destination)
            finally:
                destination.close()
                source.close()
            check = sqlite3.connect(temporary)
            try:
                if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("snapshot 무결성 검사에 실패했습니다.")
            finally:
                check.close()
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    manifest = {
        "snapshot_id": snapshot_id, "coverage_end": coverage, "database": str(target),
        "sha256": _sha256(target), "feature_rows": rows,
        "provenance": {"source_database_sha256": _sha256(database), "input_hashes": imports,
                       "method_version": "v16", "integrity_check": integrity, "foreign_key_violations": len(foreign_keys)},
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    (snapshots / f"{snapshot_id}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary = runtime / "active_snapshot.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(runtime / "active_snapshot.json")
    return manifest
