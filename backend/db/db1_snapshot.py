"""Prepare a DB1 delivery or read-only PostgreSQL workspace for service publication."""
import json
from pipelines.db1 import database
import pandas as pd

from backend.common import ROOT
DB1 = ROOT / 'pipelines' / 'db1'
MODEL_VERSION = 'analysis1_2025H2_elder_v2'
CONTEXT_NOTE = '2025년 독거노인 수와 2025년 4분기 65세 이상 등록인구를 비교한 연간 지역 배경자료입니다. 공개 시점 미확인으로 과거 월 당시 정보나 개인 고립 판정에 사용하지 않습니다.'


def prepare_snapshot(workspace_schema=None):
    from backend.db.analysis_repository import monthly_upload, prepare_analysis2
    legacy = DB1 / 'Analysis2/data/reference/gangnam_analysis2_detection_2022_2025.csv'
    history = monthly_upload(legacy.read_bytes(), legacy.name)['data']
    history['analysis_model_version'] = 'analysis2-v11'
    history['context_model_version'] = 'analysis1_2025H2'
    if workspace_schema:
        with database.connect(workspace_schema,readonly=True) as connection:
            rows = connection.execute('SELECT result_json, model_version FROM a2_detection ORDER BY date,adm_cd').fetchall()
            current = pd.DataFrame([dict(json.loads(payload), context_model_version=version,
                                         analysis_model_version='analysis2-sequential-v1') for payload, version in rows])
            period = connection.execute('SELECT MAX(period) FROM a1_context').fetchone()[0]
            if not period:
                raise ValueError('Analysis1 지역 유형 결과가 없습니다.')
            contexts = connection.execute('''SELECT c.adm_cd,c.adm_nm,c.cluster,c.cluster_type,c.model_version,c.feature_json,i.input_json
                FROM a1_context c JOIN a1_input i ON i.adm_cd=c.adm_cd AND i.period=c.period WHERE c.period=%s''', (period,)).fetchall()
            context = pd.DataFrame([dict(json.loads(raw), **json.loads(features), cluster=cluster,
                cluster_type=label, model_version=version, context_period=period)
                for code, name, cluster, label, version, features, raw in contexts])
            metadata = json.loads(connection.execute("SELECT metadata_json FROM db1_run WHERE analysis='analysis1' AND period=%s", (period,)).fetchone()[0])
            elder = metadata.get('public_sources', {}).get('elderly_cluster_input', {})
            for key in ('elder_year', 'denominator_reference', 'available_from', 'alignment'):
                context['elder_' + key if key in ('available_from', 'alignment') else key] = elder.get(key)
    else:
        current = pd.read_csv(DB1 / 'Analysis2/outputs/detection.csv', dtype={'adm_cd': str, '행정동코드': str})
        current['analysis_model_version'] = 'analysis2-sequential-v1'
        # Existing Analysis2 observations are deliberately preserved by the delivery.
        current['context_model_version'] = 'analysis1_2025H2'
        raw = pd.read_csv(DB1 / 'Analysis1/data/reference/reference_pca_input_2025H2.csv', dtype={'adm_cd': str})
        features = pd.read_csv(DB1 / 'Analysis1/outputs/periods/2025H2/context.csv', dtype={'adm_cd': str})
        context = raw.merge(features.drop(columns=['dong_name']), on='adm_cd', validate='one_to_one', suffixes=('_raw', ''))
        context['model_version'] = MODEL_VERSION
        context['context_period'] = '2025H2'
        context['elder_year'] = 2025
        context['denominator_reference'] = '2025Q4'
        context['elder_available_from'] = None
        context['elder_alignment'] = 'retrospective_annual_to_Q4'
        period = '2025H2'
    if not current.empty:
        normalized = prepare_analysis2(current, 'DB1 sequential')['data']
        history = pd.concat([history, normalized], ignore_index=True).drop_duplicates(['date', '행정동코드'], keep='last')
    monthly = prepare_analysis2(history, 'DB1 · Analysis2 delivery')
    required = {'adm_cd', 'dong_name', 'cluster', 'cluster_type', 'model_version', 'elderly_living_alone_rate_65plus'}
    if not required.issubset(context.columns) or len(context) != 22 or context.adm_cd.nunique() != 22:
        raise ValueError('Analysis1의 elder v2 결과와 강남구 22개 동이 필요합니다.')
    if not context.model_version.eq(MODEL_VERSION).all() or not context.elderly_living_alone_rate_65plus.between(0, 1).all():
        raise ValueError('Analysis1 모델 버전 또는 독거노인 비율이 올바르지 않습니다.')
    context['context_note'] = CONTEXT_NOTE if period == '2025H2' else '연간 독거노인 구조자료이며 개인 고립 판정이 아닙니다. 공개 시점과 연간 기준을 함께 확인하세요.'
    structure = dict(kind='structure', source='DB1 · Analysis1 elder v2', period=period, data=context,
                     context=context, report=dict(rule_version=MODEL_VERSION))
    return monthly, structure
