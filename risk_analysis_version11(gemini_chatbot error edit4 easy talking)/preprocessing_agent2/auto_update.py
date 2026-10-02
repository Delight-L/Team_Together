"""월별 원본 확인, 다운로드, 증분 전처리, Analysis2 실행."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from preprocessing.archives import sha256
from preprocessing.features import assemble, load_weather
from preprocessing.readers import month_from_name, read_workbook


MONTH_RE = re.compile(r"(20\d{2})[^0-9]{0,8}(0?[1-9]|1[0-2])(?:월|month|[-_. ]|$)", re.I)


def _month(name: str):
    m = MONTH_RE.search(name)
    if not m:
        try:
            return month_from_name(name)
        except Exception:
            return None
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"


def _links(page_url: str) -> list[tuple[str, str]]:
    req = Request(page_url, headers={"User-Agent": "preprocessing-agent2/1.0"})
    html = urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    found = []
    for href, text in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        label = re.sub(r"<[^>]+>", " ", text)
        label = re.sub(r"\s+", " ", label).strip()
        target = urljoin(page_url, href)
        if _month(label) or _month(target) or re.search(r"(?:download|filedown|attach|xlsx|zip)", target, re.I):
            found.append((target, label or target))
    return list(dict.fromkeys(found))


def download_latest(config: dict, raw_dir: Path, baseline_month: str | None) -> list[Path]:
    """공식 페이지에서 기준월 이후의 파일만 내려받는다.

    페이지 구조가 바뀌어도 href/파일명에 월이 포함된 링크를 우선 사용한다.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for kind, page in config.get("sources", {}).items():
        if not page:
            continue
        for href, label in _links(page):
            month = _month(label) or _month(href)
            if not month or (baseline_month and month <= baseline_month):
                continue
            suffix = Path(href.split("?")[0]).suffix.lower() or ".xlsx"
            if suffix not in {".xlsx", ".xls", ".zip", ".csv"}:
                continue
            safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", label or Path(href).name).strip("_")
            if not Path(safe).suffix:
                safe += suffix
            path = raw_dir / f"{kind}_{month}_{safe}"
            if path.exists():
                continue
            req = Request(href, headers={"User-Agent": "preprocessing-agent2/1.0"})
            with urlopen(req, timeout=120) as response, path.open("wb") as out:
                shutil.copyfileobj(response, out)
            downloaded.append(path)
    return downloaded


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader(); w.writerows(rows)
    tmp.replace(path)


def run_incremental(base: Path, config: dict, no_download: bool = False) -> dict:
    out = base / config.get("output", "outputs")
    raw = base / config.get("input", "raw_data")
    feature = out / "gangnam_analysis2_feature_table_2022_2025.csv"
    columns = json.loads((base / "reference" / "columns.json").read_text(encoding="utf-8"))
    areas = json.loads((base / "reference" / "areas.json").read_text(encoding="utf-8"))
    if not feature.exists():
        raise FileNotFoundError(f"기준 feature table이 없습니다: {feature}")
    old_columns, old_rows = _read_csv(feature)
    if old_columns != columns:
        raise ValueError("기존 feature table의 컬럼이 Analysis2 계약과 다릅니다.")
    existing = sorted({str(r["date"])[:7] for r in old_rows})
    baseline = existing[-1] if existing else None
    new_files = [] if no_download else download_latest(config, raw, baseline)
    candidates = list(raw.rglob("*.xlsx")) + list(raw.rglob("*.xls")) + list(raw.rglob("*.zip"))
    candidates = [p for p in candidates if (_month(p.name) or "") > (baseline or "")]
    if not candidates:
        analysis_status = "SKIPPED"
        detection = out / "gangnam_analysis2_detection_2022_2025.csv"
        evidence = out / "gangnam_analysis2_evidence_card_2022_2025.csv"
        # 기준 feature table만 전달된 새 설치에서도 최초 결과를 만든다.
        if not detection.exists() or not evidence.exists():
            _run_analysis2(base, config, feature, out)
            analysis_status = "BASELINE_ANALYSIS_CREATED"
        return {"status": "NO_NEW_DATA", "baseline_month": baseline,
                "downloaded": [str(p) for p in new_files],
                "analysis": analysis_status}
    manifest = {"status": "RUNNING", "files": [], "name_normalizations": set()}
    weather = load_weather(base / config["weather"])
    data = {}
    for p in candidates:
        try:
            month, kind, groups, digest, count = read_workbook(p, p.name, areas, manifest, config["demographics"], config["archive_limits"]["max_file_bytes"])
        except Exception:
            continue
        if month and month > (baseline or ""):
            data[(month, kind)] = groups
    months = sorted({m for m, _ in data})
    complete = [m for m in months if (m, "telecom") in data and (m, "interest") in data]
    if not complete:
        raise ValueError("새 월의 통신정보와 관심집단 파일이 모두 준비되지 않았습니다.")
    target = complete[-1]
    rows = assemble({k: v for k, v in data.items() if k[0] == target}, [target], areas, weather)
    existing_keys = {(r["date"], r["area_code"]) for r in old_rows}
    rows = [r for r in rows if (r["date"], r["area_code"]) not in existing_keys]
    _write_csv(feature, columns, old_rows + rows)
    result = {"status": "PASS", "baseline_month": baseline, "processed_month": target, "new_rows": len(rows), "downloaded": [str(p) for p in new_files]}
    _run_analysis2(base, config, feature, out)
    (out / "auto_update_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _run_analysis2(base: Path, config: dict, feature: Path, out: Path) -> None:
    analysis_dir = Path(config.get("analysis2_dir", "../Analysis2"))
    if not analysis_dir.is_absolute():
        analysis_dir = (base / analysis_dir).resolve()
    runner = analysis_dir / "run_analysis2.py"
    if not runner.exists():
        raise FileNotFoundError(f"Analysis2 실행 파일을 찾을 수 없습니다: {runner}")
    # 기존 runner는 입력 파일을 Analysis2 루트에서 읽으므로 실행 전 동기화한다.
    target = analysis_dir / "gangnam_analysis2_feature_table_2022_2025.csv"
    shutil.copy2(feature, target)
    subprocess.run([sys.executable, str(runner)], cwd=analysis_dir, check=True)
    for name in ("gangnam_analysis2_detection_2022_2025.csv", "gangnam_analysis2_evidence_card_2022_2025.csv"):
        src = analysis_dir / "outputs" / name
        if src.exists():
            shutil.copy2(src, out / name)
