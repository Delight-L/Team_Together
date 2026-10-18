"""Read-only source inventory: syntax, local frontend imports and duplicates.

Run from any directory: python scripts/audit_repository.py --output .tmp/audit.json
This inspects Git-visible files, so ignored local tests/data and installations
are excluded. Unreferenced modules are candidates for review, not safe deletions.
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
FRONTEND_IMPORT = re.compile(
    r'''(?:from\s*|import\s*(?:\(\s*)?|@import\s*)['"](\.[^'"\n]+)['"]'''
)


def visible_files():
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, capture_output=True,
    )
    return sorted({
        name.decode("utf-8") for name in result.stdout.split(b"\0")
        if name and (ROOT / name.decode("utf-8")).is_file()
    })


def resolve_frontend_import(source, specifier):
    target = (source.parent / specifier.split("?", 1)[0]).resolve()
    candidates = [target]
    if not target.suffix:
        candidates += [Path(str(target) + suffix) for suffix in (
            ".js", ".jsx", ".mjs", ".json", ".css",
        )]
        candidates += [target / name for name in ("index.js", "index.jsx")]
    return next((path for path in candidates if path.is_file()), None)


def audit():
    files = visible_files()
    counts = defaultdict(int)
    hashes = defaultdict(list)
    syntax_errors, missing_imports = [], []
    frontend_modules, imported = set(), set()
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
                    imported.add(target)
                else:
                    missing_imports.append({"path": name, "import": match[1]})
    return {
        "file_count": len(files),
        "files_by_area": dict(sorted(counts.items())),
        "syntax_errors": syntax_errors,
        "missing_frontend_imports": missing_imports,
        "unreferenced_frontend_candidates": sorted(
            path.relative_to(ROOT).as_posix()
            for path in frontend_modules - imported if path.name != "main.jsx"
        ),
        "exact_text_duplicates": sorted(group for group in hashes.values() if len(group) > 1),
        "largest_source_files": sorted(largest, key=lambda item: (-item["lines"], item["path"]))[:20],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON inventory; relative to repository root")
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
