from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ALLOWED_PATTERNS = (
    "agents/regional_analysis/Analysis2/outputs/*.csv",
    "agents/regional_analysis/Analysis2/outputs/*.json",
    "agents/regional_analysis/Analysis2/gangnam_analysis2_feature_table_*.csv",
    "preprocessing/regional_types/outputs/**/*.csv",
    "preprocessing/regional_types/outputs/**/*.json",
    "preprocessing/regional_features/outputs/*.csv",
    "preprocessing/regional_features/outputs/*.json",
    "agents/regional_analysis/analysis2_execution_report.json",
)

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_]+")


@dataclass(frozen=True)
class CatalogConfig:
    max_rows_per_file: int = 5
    max_total_rows: int = 20
    max_context_chars: int = 12000
    max_scan_rows: int = 10000
    max_json_bytes: int = 2_000_000


@dataclass(frozen=True)
class ContextResult:
    text: str
    sources: tuple[str, ...]
    missing_patterns: tuple[str, ...]
    selected_rows: int


def discover_sources(project_root: Path) -> tuple[list[Path], list[str]]:
    """Return only files matched by the fixed Version 5 output allowlist."""
    root = project_root.resolve()
    found: dict[str, Path] = {}
    missing: list[str] = []
    for pattern in ALLOWED_PATTERNS:
        matches = [p.resolve() for p in root.glob(pattern) if p.is_file()]
        safe_matches = [p for p in matches if p.is_relative_to(root)]
        if not safe_matches:
            missing.append(pattern)
        for path in safe_matches:
            found[path.relative_to(root).as_posix()] = path
    return [found[key] for key in sorted(found)], missing


def _tokens(question: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(question) if len(token) >= 2}


def _score(value: Any, tokens: set[str]) -> int:
    haystack = json.dumps(value, ensure_ascii=False, default=str).lower()
    return sum(1 for token in tokens if token in haystack)


def _open_csv(path: Path):
    try:
        return path.open("r", encoding="utf-8-sig", newline="")
    except UnicodeDecodeError:
        return path.open("r", encoding="cp949", newline="")


def _csv_evidence(path: Path, tokens: set[str], config: CatalogConfig) -> dict[str, Any]:
    candidates: list[tuple[int, int, dict[str, str]]] = []
    row_count = 0
    handle = _open_csv(path)
    try:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        for index, row in enumerate(reader):
            row_count += 1
            if index >= config.max_scan_rows:
                break
            score = _score(row, tokens)
            candidates.append((score, index, row))
    except UnicodeDecodeError:
        handle.close()
        handle = path.open("r", encoding="cp949", newline="")
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        candidates = []
        row_count = 0
        for index, row in enumerate(reader):
            row_count += 1
            if index >= config.max_scan_rows:
                break
            candidates.append((_score(row, tokens), index, row))
    finally:
        handle.close()

    if tokens and any(score > 0 for score, _, _ in candidates):
        candidates.sort(key=lambda item: (-item[0], item[1]))
    else:
        candidates.sort(key=lambda item: item[1])
    rows = [row for _, _, row in candidates[: config.max_rows_per_file]]
    return {
        "type": "csv",
        "columns": columns,
        "rows_scanned": row_count,
        "scan_truncated": row_count >= config.max_scan_rows,
        "sample_or_relevant_rows": rows,
    }


def _json_evidence(path: Path, tokens: set[str], config: CatalogConfig) -> dict[str, Any]:
    if path.stat().st_size > config.max_json_bytes:
        return {"type": "json", "read_error": f"파일 크기 제한 초과: {config.max_json_bytes} bytes"}
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if isinstance(value, list):
        ranked = sorted(enumerate(value), key=lambda item: (-_score(item[1], tokens), item[0]))
        selected = [item for _, item in ranked[: config.max_rows_per_file]]
        return {"type": "json", "items": len(value), "sample_or_relevant_items": selected}
    return {"type": "json", "value": value}


def _trim_record(record: dict[str, Any], available_chars: int) -> str:
    rendered = json.dumps(record, ensure_ascii=False, default=str, indent=2)
    if len(rendered) <= available_chars:
        return rendered
    minimal = {
        "source": record["source"],
        "type": record.get("type"),
        "columns": record.get("columns", []),
        "rows_scanned": record.get("rows_scanned"),
        "notice": "행 데이터는 문맥 길이 제한으로 생략됨",
    }
    return json.dumps(minimal, ensure_ascii=False, default=str, indent=2)[:available_chars]


def build_context(project_root: Path, question: str, config: CatalogConfig) -> ContextResult:
    sources, missing = discover_sources(project_root)
    tokens = _tokens(question)
    chunks: list[str] = []
    used: list[str] = []
    selected_rows = 0
    current_chars = 0

    for path in sources:
        relative = path.resolve().relative_to(project_root.resolve()).as_posix()
        try:
            evidence = (
                _csv_evidence(path, tokens, config)
                if path.suffix.lower() == ".csv"
                else _json_evidence(path, tokens, config)
            )
        except (OSError, csv.Error, json.JSONDecodeError, UnicodeError) as exc:
            evidence = {"type": path.suffix.lstrip("."), "read_error": str(exc)}

        if evidence.get("type") == "csv":
            rows = evidence.get("sample_or_relevant_rows", [])
            remaining_rows = max(0, config.max_total_rows - selected_rows)
            evidence["sample_or_relevant_rows"] = rows[:remaining_rows]
            selected_rows += len(evidence["sample_or_relevant_rows"])

        record = {"source": relative, **evidence}
        separator_size = 2 if chunks else 0
        remaining_chars = config.max_context_chars - current_chars - separator_size
        if remaining_chars <= 0:
            break
        rendered = _trim_record(record, remaining_chars)
        if not rendered:
            break
        chunks.append(rendered)
        used.append(relative)
        current_chars += len(rendered) + separator_size

    return ContextResult(
        text="\n\n".join(chunks),
        sources=tuple(used),
        missing_patterns=tuple(missing),
        selected_rows=selected_rows,
    )


def load_catalog_config(config_path: Path) -> CatalogConfig:
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("config.json 최상위 값은 객체여야 합니다.")
    retrieval = raw.get("retrieval", {})
    if not isinstance(retrieval, dict):
        raise ValueError("retrieval 설정은 객체여야 합니다.")
    limits = {
        "max_rows_per_file": (1, 100),
        "max_total_rows": (1, 500),
        "max_context_chars": (1000, 100000),
        "max_scan_rows": (1, 1000000),
        "max_json_bytes": (1000, 10000000),
    }
    values = {}
    defaults = CatalogConfig()
    for name, (minimum, maximum) in limits.items():
        value = retrieval.get(name, getattr(defaults, name))
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{name}은 {minimum}~{maximum} 범위의 정수여야 합니다.")
        values[name] = value
    return CatalogConfig(
        **values,
    )
