"""DB1 실행기: 두 전처리 에이전트 실행 후 Analysis2까지 수행한다."""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent

def run(script, arguments=None):
    command = [sys.executable, "-X", "utf8", str(script), *(arguments or [])]
    print("[실행]", " ".join(command), flush=True)
    subprocess.run(command, cwd=script.parent, check=True)

def verify_analysis2():
    output = BASE / "Analysis2" / "outputs"
    required = {
        output / "gangnam_analysis2_detection_2022_2025.csv": {"date", "행정동코드", "communication_signal", "mobility_signal", "any_signal"},
        output / "gangnam_analysis2_evidence_card_2022_2025.csv": {"date", "행정동코드", "signal_status"},
    }
    result = {"status": "PASS", "files": {}}
    for path, columns in required.items():
        info = {"exists": path.is_file(), "path": str(path)}
        if path.is_file():
            frame = pd.read_csv(path)
            missing = sorted(columns - set(frame.columns))
            info.update(rows=len(frame), columns=len(frame.columns), missing_columns=missing)
            if missing: result["status"] = "FAIL"
        else:
            result["status"] = "FAIL"
        result["files"][path.name] = info
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-download", action="store_true")
    args = p.parse_args()

    a1 = BASE.parents[1] / "preprocessing" / "regional_types"
    a2 = BASE.parents[1] / "preprocessing" / "regional_features"
    analysis2 = BASE / "Analysis2"
    run(a1 / "main.py")
    run(a2 / "main.py", ["--no-download"] if args.no_download else [])
    source = a2 / "outputs" / "gangnam_analysis2_feature_table_2022_2025.csv"
    target = analysis2 / "gangnam_analysis2_feature_table_2022_2025.csv"
    if not source.is_file():
        raise FileNotFoundError(f"Analysis2 입력 feature table이 없습니다: {source}")
    shutil.copy2(source, target)
    run(analysis2 / "run_analysis2.py")
    verification = verify_analysis2()
    report = BASE / "analysis2_execution_report.json"
    report.write_text(json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[검증] Analysis2: {verification['status']}")
    print(f"[보고서] {report}")
    return 0 if verification["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
