"""Analysis1 원천자료 → Agent-ready 1행/동 입력 변환기.

현재 입력 변환은 DB1의 elder v2 전처리·모델을 별도 프로세스로 호출합니다.
이 모듈은 실행 결과를 받아 서비스 업로드·CLI에서 쓰는 형식으로 저장합니다.
"""
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

PCA_MAPPING = {
 "active_pop":["male_ratio","age_10_ratio","age_20_ratio","age_30_ratio","age_40_ratio","age_50_ratio","age_60_plus_ratio"],
 "time_structure":["night_ratio","morning_ratio","daytime_ratio","evening_ratio"],
 "resident_age":["resident_ratio_0_19","resident_ratio_20_29","resident_ratio_30_39","resident_ratio_40_49","resident_ratio_50_64","resident_ratio_65_plus"],
 "household_structure":["hh_1_ratio","hh_2_ratio","hh_3_ratio","hh_4plus_ratio"],
}

class PreprocessError(ValueError):
    pass


def preprocess_raw_dir(raw_dir: str|Path) -> tuple[pd.DataFrame,pd.DataFrame,dict]:
    """Use elder v2 pipelines/preprocessing/model without sharing Analysis1/2 imports."""
    import subprocess
    import sys
    import tempfile
    script = Path(__file__).resolve().parents[3] / 'pipelines/db1/Analysis1/service_adapter.py'
    with tempfile.TemporaryDirectory(prefix='db1-structure-') as output:
        result = subprocess.run(
            [sys.executable, '-X', 'utf8', str(script), '--raw-dir', str(Path(raw_dir).resolve()), '--output-dir', output],
            capture_output=True, text=True, encoding='utf-8', timeout=120,
        )
        if result.returncode:
            detail = result.stderr.strip().splitlines()
            raise PreprocessError(detail[-1] if detail else '지역 구조자료 분석에 실패했습니다.')
        base = pd.read_csv(Path(output) / 'input.csv', dtype={'adm_cd': str})
        context = pd.read_csv(Path(output) / 'context.csv', dtype={'adm_cd': str})
        report = json.loads((Path(output) / 'report.json').read_text(encoding='utf-8'))
        return base, context, report


def save(base:pd.DataFrame, profile:pd.DataFrame, report:dict, output:Path):
    output.mkdir(parents=True,exist_ok=True)
    base.to_csv(output/'analysis1_input.csv',index=False,encoding='utf-8-sig')
    profile.to_csv(output/'analysis1_profile.csv',index=False,encoding='utf-8-sig')
    (output/'pca_columns.json').write_text(json.dumps(PCA_MAPPING,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'preprocessing_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
