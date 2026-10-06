# data/ingestion.py

"""
DB1 Analysis2 data ingestion

Analysis2 입력 데이터를 pandas DataFrame으로 로딩한다.
통계 분석 및 데이터 검증은 이 모듈에서 수행하지 않는다.
"""

from pathlib import Path

import pandas as pd


def load_analysis2_input(file_path: str | Path) -> pd.DataFrame:
    """
    Analysis2 입력 파일을 DataFrame으로 로딩한다.

    Parameters
    ----------
    file_path : str | Path
        Analysis2 Feature Table 경로

    Returns
    -------
    pd.DataFrame
        로딩된 입력 데이터

    Raises
    ------
    FileNotFoundError
        입력 파일이 존재하지 않는 경우

    ValueError
        지원하지 않는 파일 형식인 경우
    """

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Analysis2 입력 파일을 찾을 수 없습니다: {file_path}"
        )

    suffix = file_path.suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(file_path)

    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(file_path)

    elif suffix == ".parquet":
        df = pd.read_parquet(file_path)

    else:
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {suffix}"
        )

    return df