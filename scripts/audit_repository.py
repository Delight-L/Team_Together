"""소스를 변경하지 않고 문법·화면 참조·중복 파일을 확인합니다.

실행: python scripts/audit_repository.py --output .tmp/audit.json
Git에서 관리하거나 새로 추가한 파일만 검사합니다. 무시된 로컬 자료·설치물은 제외합니다.
미참조 목록은 검토 후보이며, 독립 실행 도구 등을 바로 삭제해도 된다는 뜻은 아닙니다.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".css"}
TEXT_SUFFIXES = CODE_SUFFIXES | {".md", ".json", ".sql", ".ps1"}
FRONTEND_IMPORT = re.compile(r'''(?:from\s*|import\s*(?:\(\s*)?|@import\s*)['"](\.[^'"\n]+)['"]''')


def visible_files():
    """Git 관리 파일과 새 파일을 모읍니다. 설치물·로컬 자료 등 무시된 파일은 제외합니다."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    files = set()
    for raw_name in result.stdout.split(b"\0"):
        if not raw_name:
            continue
        name = raw_name.decode("utf-8")
        if (ROOT / name).is_file():
            files.add(name)
    return sorted(files)


def resolve_frontend_import(source, specifier):
    """확장자를 생략한 import와 폴더의 index 파일까지 찾아 실제 파일로 연결합니다."""
    target = (source.parent / specifier.split("?", 1)[0]).resolve()
    candidates = [target]
    if not target.suffix:
        candidates += [
            Path(str(target) + suffix)
            for suffix in (
                ".js",
                ".jsx",
                ".mjs",
                ".json",
                ".css",
            )
        ]
        candidates += [target / name for name in ("index.js", "index.jsx")]
    return next((path for path in candidates if path.is_file()), None)


def reachable_modules(entrypoint, dependencies):
    """화면 시작점에서 import를 따라갑니다. 서로만 참조하는 고립된 파일도 찾아냅니다."""
    reachable = set()
    pending = [entrypoint]
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        reachable.add(module)
        pending.extend(dependencies.get(module, ()))
    return reachable


def audit():
    files = visible_files()
    counts = defaultdict(int)
    hashes = defaultdict(list)
    syntax_errors, missing_imports = [], []
    frontend_modules = set()
    dependencies = defaultdict(set)
    largest = []
    for name in files:
        path = ROOT / name
        counts[name.split("/", 1)[0]] += 1
        if path.suffix not in TEXT_SUFFIXES:
            continue
        raw = path.read_bytes()
        if len(raw) > 150:
            hashes[hashlib.sha256(raw).hexdigest()].append(name)
        if path.suffix in CODE_SUFFIXES:
            largest.append({"path": name, "lines": len(raw.splitlines())})
        text = raw.decode("utf-8-sig")
        if path.suffix == ".py":
            try:
                ast.parse(text, filename=name)
            except SyntaxError as exc:
                syntax_errors.append({"path": name, "line": exc.lineno, "message": exc.msg})
        if name.startswith("frontend/src/") and path.suffix in {".js", ".jsx", ".mjs", ".css"}:
            frontend_modules.add(path.resolve())
            for match in FRONTEND_IMPORT.finditer(text):
                target = resolve_frontend_import(path, match[1])
                if target:
                    dependencies[path.resolve()].add(target)
                else:
                    missing_imports.append({"path": name, "import": match[1]})
    entrypoint = (ROOT / 'frontend/src/main.jsx').resolve()
    reachable = reachable_modules(entrypoint, dependencies)
    return {
        "file_count": len(files),
        "files_by_area": dict(sorted(counts.items())),
        "syntax_errors": syntax_errors,
        "missing_frontend_imports": missing_imports,
        "unreferenced_frontend_candidates": sorted(
            path.relative_to(ROOT).as_posix()
            for path in frontend_modules - reachable
            if path.name != "main.jsx"
        ),
        "exact_text_duplicates": sorted(group for group in hashes.values() if len(group) > 1),
        "largest_source_files": sorted(largest, key=lambda item: (-item["lines"], item["path"]))[
            :20
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Optional JSON inventory; relative to repository root"
    )
    args = parser.parse_args()
    result = audit()
    if args.output:
        target = ROOT / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["syntax_errors"] or result["missing_frontend_imports"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
