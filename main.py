"""Team Together 실행 진입점.

대시보드: python main.py 또는 python -m streamlit run main.py
전처리: python main.py --preprocess
지역 유형 전처리: python main.py --preprocess-analysis1
위험분석: python main.py --risk --input 월별행동.csv
설명 챗봇: python main.py --chatbot
"""

from pathlib import Path
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent


def load_processed_data():
    """전처리 CSV를 준비하고 읽습니다. 화면용 위험 요인 연결 전 단계입니다."""

    import pandas as pd
    from preprocessing.cleaning import cvt2csv

    processed = ROOT_DIR / "data" / "processed"
    names = ("time_pop", "age_pop", "wkdy_pop", "sh_data")
    needs_preprocessing = False
    for name in names:
        if not (processed / f"{name}.csv").exists():
            needs_preprocessing = True
    if needs_preprocessing:
        cvt2csv()
    datasets = {}
    for name in names:
        path = processed / f"{name}.csv"
        datasets[name] = pd.read_csv(path, dtype={"BLOCK_CD": str})
    return datasets


def main():
    """지정한 작업을 선택합니다. 옵션이 없으면 대시보드를 엽니다."""
    arguments = sys.argv[1:]
    # 지역 유형 전처리는 화면 패키지 없이도 실행할 수 있습니다.
    if arguments[:1] == ["--preprocess-analysis1"]:
        script = (
            ROOT_DIR
            / "agent"
            / "risk_analysis_version1"
            / "preprocessing_agent"
            / "main.py"
        )
        command = [sys.executable, "-X", "utf8", str(script)] + arguments[1:]
        exit_code = subprocess.call(command, cwd=ROOT_DIR)
        raise SystemExit(exit_code)

    if arguments == ["--preprocess"]:
        for name, data in load_processed_data().items():
            print(f"{name}: {len(data):,}행")
        return

    if arguments[:1] == ["--risk"]:
        script = ROOT_DIR / "agent" / "risk_analysis_version1" / "main.py"
        command = [sys.executable, "-X", "utf8", str(script)] + arguments[1:]
        exit_code = subprocess.call(command, cwd=ROOT_DIR)
        raise SystemExit(exit_code)

    if arguments[:1] == ["--chatbot"]:
        script = ROOT_DIR / "agent" / "social_isolation_chatbot" / "app.py"
        command = [sys.executable, "-m", "streamlit", "run", str(script)] + arguments[
            1:
        ]
        exit_code = subprocess.call(command, cwd=ROOT_DIR)
        raise SystemExit(exit_code)

    from streamlit.runtime.scriptrunner import get_script_run_ctx

    if get_script_run_ctx(suppress_warning=True) is not None:
        from dashboard.main import render_app

        render_app()
        return

    # 같은 가상환경의 Streamlit으로 최상위 진입점을 실행합니다.
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(ROOT_DIR / "main.py"),
        *sys.argv[1:],
    ]
    exit_code = subprocess.call(command, cwd=ROOT_DIR)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
