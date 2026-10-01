"""Team Together 실행 진입점.

대시보드: python main.py 또는 python -m streamlit run main.py
전처리: python main.py --preprocess
"""
from pathlib import Path
from preprocessing.cleaning import cvt2csv

import pandas as pd
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent


def load_processed_data():
    """전처리 CSV를 준비하고 읽습니다. 화면용 위험 요인 연결 전 단계입니다."""


    processed = ROOT_DIR / "data" / "processed"
    names = ("time_pop", "age_pop", "wkdy_pop", "sh_data")
    if not all((processed / f"{name}.csv").exists() for name in names):
        cvt2csv()
    return {
        name: pd.read_csv(processed / f"{name}.csv", dtype={"BLOCK_CD": str})
        for name in names
    }


def main():
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    if get_script_run_ctx(suppress_warning=True) is not None:
        from dashboard.main import render_app

        render_app()
        return

    if sys.argv[1:] == ["--preprocess"]:
        import os

        os.chdir(ROOT_DIR)
        for name, data in load_processed_data().items():
            print(f"{name}: {len(data):,}행")
        return

    # 같은 가상환경의 Streamlit으로 최상위 진입점을 실행합니다.
    raise SystemExit(subprocess.call([
        sys.executable, "-m", "streamlit", "run", str(ROOT_DIR / "main.py"),
        *sys.argv[1:],
    ], cwd=ROOT_DIR))


if __name__ == "__main__":
    main()
