"""Read the delivered dong/age/month detections without recomputing or merging legacy flags."""
from pathlib import Path
from functools import lru_cache
from copy import deepcopy
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'pipelines/db1/Analysis2/outputs/age_detection/analysis2_age_detection.csv'
AGE_LABELS = {'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60대 이상'}
AGE_BANDS = {v:k for k,v in AGE_LABELS.items()}
# Same administrative code, renamed dong in the current map/flow catalogue.
DISPLAY_NAMES = {'1123074':'개포3동'}
METRICS = [('call_contacts','전화 연락','communication'),('text_contacts','문자 연락','communication'),
           ('weekday_move_count','평일 이동','mobility'),('weekend_move_count','휴일 이동','mobility')]

def flag(value):
    if value is None or pd.isna(value) or value == '': return None
    if str(value).lower() in ('true','1','1.0'): return True
    if str(value).lower() in ('false','0','0.0'): return False
    raise ValueError('Invalid detection flag')

def percent(value):
    return math.expm1(value)*100 if isinstance(value,(float,int)) and math.isfinite(value) else None

def prepare_age_analysis(frame, source):
    frame=frame.copy()
    required={'date','행정동코드','행정동','age_band','detection_model_version','communication_signal','mobility_signal'}
    if frame.empty or not required.issubset(frame): raise ValueError('동·연령별 탐지 결과가 필요합니다.')
    frame['month']=pd.to_datetime(frame.date,format='mixed').dt.strftime('%Y-%m')
    frame['행정동코드']=frame['행정동코드'].astype(str)
    if frame.duplicated(['month','행정동코드','age_band']).any(): raise ValueError('동·연령·월 탐지 결과 중복 또는 모델 버전 혼재')
    if frame.detection_model_version.nunique()!=1: raise ValueError('활성 탐지 모델은 하나여야 합니다.')
    if not set(frame.age_band).issubset(AGE_LABELS): raise ValueError('지원하지 않는 탐지 연령대')
    assessment=[];cases=[];alerts=[]
    for r in json.loads(frame.to_json(orient='records',force_ascii=False)):
        for key in list(r):
            if key.endswith(('_signal','_assessable')) or key=='any_signal': r[key]=flag(r[key])
        age=AGE_LABELS[r['age_band']]; code=r['행정동코드'];month=r['month']
        name=DISPLAY_NAMES.get(code,r['행정동'])
        case_id='/'.join([month,code,r['age_band'],r['detection_model_version']])
        any_signal=r['communication_signal'] is True or r['mobility_signal'] is True
        status=r.get('signal_status')
        case=dict(case_id=case_id,code=code,district=name,source_district=r['행정동'],month=month,age=age,age_band=r['age_band'],
                  model_version=r['detection_model_version'],sex_scope='성별 통합',
                  communication_signal=r['communication_signal'],mobility_signal=r['mobility_signal'],
                  any_signal=any_signal,assessment_status=r.get('assessment_status'),signal_status=status,
                  payload=r,source_file=source,scope='dong_age')
        cases.append(case)
        if any_signal: alerts.append({k:v for k,v in case.items() if k!='payload'})
        for metric,label,domain in METRICS:
            own=flag(r.get(domain+'_absolute_signal'));local=flag(r.get(domain+'_local_signal'))
            scope='absolute' if own else 'local' if local else 'absolute' if flag(r.get(metric+'_absolute_assessable')) else 'local'
            assessable=flag(r.get(metric+'_'+scope+'_assessable')) is True and r[domain+'_signal'] is not None
            row={'행정동코드':code,'행정동명':name,'source_district':r['행정동'],'기준연월':month,'age_band':r['age_band'],'age_label':age,
                 'case_id':case_id,'model_version':r['detection_model_version'],'scope':'dong_age','sex_scope':'성별 통합',
                 'metric':metric,'metric_label':age+' '+label,'metric_value':r.get(metric),'metric_unit':'명' if domain=='communication' else '회',
                 'change_pct':percent(r.get(metric+'_log_change')),'relative_change_pp':r.get(metric+'_residual')*100 if r.get(metric+'_residual') is not None else None,
                 'risk_robust_z':r.get(metric+'_'+scope+'_rz'),'threshold':r.get(metric+'_'+scope+'_threshold'),
                 'has_enough_history':assessable,'is_risk_signal':r[domain+'_signal'] is True,
                 'domain_signal':r[domain+'_signal'],'absolute_signal':own,'local_signal':local,
                 'detection_path':'자체 이력·공통 변화 조정' if own and local else '자체 이력' if own else '공통 변화 조정' if local else '미탐지',
                 'absolute_rz':r.get(metric+'_absolute_rz'),'local_rz':r.get(metric+'_local_rz'),
                 'absolute_threshold':r.get(metric+'_absolute_threshold'),'local_threshold':r.get(metric+'_local_threshold'),
                 'explanation':r['행정동']+' '+age+' · 성별 통합 통화·문자·이동 변화',
                 'context_note':'연령대의 성별 통합 판정이며 선택 성별의 판정이나 개인의 고립 판정이 아닙니다.'}
            assessment.append(row)
    months=sorted(frame.month.unique().tolist())
    return dict(connected=True,isDemo=False,source='DB1 · 동·연령별 통화·문자·이동 탐지 (성별 통합)',
                runId='analysis2-age-'+str(Path(source).stat().st_mtime_ns) if Path(source).exists() else 'analysis2-age-test',
                analysisScope='dong_age',assessment=assessment,signals=[r for r in assessment if r['is_risk_signal']],
                alerts=alerts,ageDetections=cases,months=months,activity=[],
                signalCounts={m:sum(c['month']==m for c in alerts) for m in months},
                runs=[dict(kind='monthly',source_name=source,period=months[0]+' ~ '+months[-1],rule_version=frame.detection_model_version.iloc[0])])

@lru_cache(maxsize=2)
def _load(path, modified_ns):
    return prepare_age_analysis(pd.read_csv(path,dtype={'행정동코드':str}),path)

def load_age_analysis():
    if not SOURCE.is_file(): raise FileNotFoundError('DB1 동·연령별 탐지 결과를 준비하세요: '+str(SOURCE))
    return deepcopy(_load(str(SOURCE),SOURCE.stat().st_mtime_ns))

def detection_for(context, data=None):
    if context['city']!='강남구':return None
    data=data if data is not None else load_age_analysis()
    band=AGE_BANDS.get(context.get('age'))
    return next((r for r in data['ageDetections'] if r['code']==context['code'] and r['month']==context['month'] and r['age_band']==band),None)
