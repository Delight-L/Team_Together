"""Read-only SQLite evidence. Never fall back to a precomputed legacy CSV."""
from __future__ import annotations
from contextlib import contextmanager
import json,sqlite3
from pathlib import Path
import pandas as pd
from .district_normalizer import ALIASES

SOURCES={'detection':'DB1: a2_detection','evidence':'DB1: a2_evidence',
         'feature':'DB1: a2_feature','typology':'DB1: a1_context / a1_input'}
CORE=('call_contacts','text_contacts','weekday_move_count','weekend_move_count')
AGE_LABEL={'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60대이상'}

class DataRepository:
    def __init__(self,root:Path,db=None):
        self.root=Path(root)
        from data_pipeline.runner import settings
        configured=Path(settings(self.root,db=db)['database'])
        from data_pipeline.snapshot_manager import resolve_database
        self.db=resolve_database(configured)

    @contextmanager
    def connection(self):
        if not self.db.is_file():raise FileNotFoundError('데이터를 초기화해 주세요: python main.py')
        con=sqlite3.connect(self.db.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            row=con.execute('SELECT payload_json FROM pipeline_state WHERE id=1').fetchone()
            if not row or json.loads(row[0]).get('status')!='ready':
                raise ValueError('데이터 갱신이 완료되지 않았습니다. 처리 상태를 확인해 주세요.')
            yield con
        finally:con.close()

    def districts(self):
        with self.connection() as c:names=[r[0] for r in c.execute('SELECT DISTINCT adm_nm FROM a1_context')]
        return {ALIASES.get(n,n) for n in names}

    def available_period(self):
        with self.connection() as c:lo,hi=c.execute('SELECT MIN(date),MAX(date) FROM a2_detection').fetchone()
        return (lo[:7],hi[:7]) if lo else ('2025-07','2025-07')

    def consumption_period(self):
        with self.connection() as c:lo,hi=c.execute('SELECT MIN(period),MAX(period) FROM a3a_feature').fetchone()
        if not lo:return self.available_period()
        return (pd.Period(lo,freq='Q').start_time.strftime('%Y-%m'),pd.Period(hi,freq='Q').end_time.strftime('%Y-%m'))

    def _read(self,name,age_band=None):
        with self.connection() as c:
            if age_band:
                rows=c.execute("SELECT result_json FROM a2_age_detection WHERE age_scheme='service' AND age_band=? ORDER BY date,adm_cd",(age_band,)).fetchall()
            else:
                table,col={'detection':('a2_detection','result_json'),'feature':('a2_feature','feature_json'),
                           'evidence':('a2_evidence','evidence_json')}[name]
                rows=c.execute(f'SELECT {col} FROM {table} ORDER BY date,adm_cd').fetchall()
        f=pd.DataFrame([json.loads(r[0]) for r in rows])
        for col in ['date','행정동','signal_type','signal_status',*CORE,'any_signal','communication_signal','mobility_signal','combined_signal']:
            if col not in f:f[col]=pd.Series(index=f.index,dtype=object)
        f['행정동']=f['행정동'].replace(ALIASES)
        if 'dong_name' in f:f['dong_name']=f.dong_name.replace(ALIASES)
        if name!='feature' or age_band:
            def signal(r):
                if r.get('combined_signal') is True or r.get('combined_signal')==1:return 'combined'
                if r.get('communication_signal') is True or r.get('communication_signal')==1:return 'communication'
                if r.get('mobility_signal') is True or r.get('mobility_signal')==1:return 'mobility'
                return 'none'
            f['signal_type']=f.apply(signal,axis=1) if not f.empty else pd.Series(dtype=object)
            for metric in CORE:
                source=metric+('_local_rz' if age_band else '_rz')
                target=metric+'_residual_change_expanding_rz'
                if target not in f:f[target]=f[source] if source in f else None
            if age_band:
                f['consecutive_signal']=f.get('adjacent_signal_run',pd.Series(0,index=f.index)).gt(1)
            elif 'consecutive_signal' not in f:f['consecutive_signal']=False
        return f

    def _period(self,f,start,end):
        if f.empty:return f
        dates=pd.to_datetime(f.date,format='mixed')
        # A scalar ``True`` is interpreted by pandas as a column label. Build a
        # row-wise mask so context questions without an explicit period still
        # return every available record.
        mask=pd.Series(True,index=f.index)
        if start:mask &= dates.ge(pd.Timestamp(start))
        if end:mask &= dates.le(pd.Timestamp(end)+pd.offsets.MonthEnd(0))
        return f.loc[mask].copy()

    def signals(self,start=None,end=None,dong=None,signal='any',age_band=None):
        f=self.activity(dong,start,end,age_band)
        return f.loc[f[{'any':'any_signal','communication':'communication_signal','mobility':'mobility_signal','combined':'combined_signal'}[signal]].fillna(False).eq(True)]

    def anomalies(self,start=None,end=None,metric=None,age_band=None,dongs=()):
        f=self.activity(None,start,end,age_band);metric=metric or 'weekday_move_count'
        rz=metric+'_residual_change_expanding_rz'
        if rz not in f:raise ValueError('지원하지 않는 활동 지표입니다.')
        if dongs:f=f.loc[f['행정동'].isin(dongs)]
        return f.loc[f[rz].notna()].sort_values(rz).head(10),rz

    def activity(self,dong,start=None,end=None,age_band=None):
        f=self._period(self._read('detection',age_band),start,end)
        if dong:f=f.loc[f['행정동'].eq(dong)]
        return f.sort_values(['date','행정동'])

    def evidence(self,dong,start=None,end=None,age_band=None):
        if age_band:return self.signals(start,end,dong,'any',age_band)
        f=self._period(self._read('evidence'),start,end)
        return f.loc[f['행정동'].eq(dong)].sort_values('date')

    def context(self,dong,as_of=None):
        with self.connection() as c:
            rows=c.execute('SELECT c.feature_json,i.input_json,c.period,c.cluster_type,c.effective_from,r.metadata_json FROM a1_context c JOIN a1_input i ON i.adm_cd=c.adm_cd AND i.period=c.period JOIN db1_run r ON r.analysis=\'analysis1\' AND r.period=c.period WHERE c.effective_from<=? ORDER BY c.effective_from DESC',
                           (as_of or '9999-12-31',)).fetchall()
        for feature,raw,period,kind,effective,metadata in rows:
            r={**json.loads(raw),**json.loads(feature)}
            r['dong_name']=ALIASES.get(r['dong_name'],r['dong_name'])
            if r['dong_name']==dong:
                r.update(period=period,cluster_type=kind,effective_from=effective,
                         retrospective_context=json.loads(metadata).get('retrospective_context',False))
                return pd.DataFrame([r])
        return pd.DataFrame()

    def supplements(self,names,dates,age_band=None):
        """Align local quarters to observation windows; deduplicate shared district data."""
        # 관측 기간 계산은 공식 DB1 파이프라인의 함수를 씁니다.
        from pipelines.db1.Context.source_semantics import window
        local={};shared={};weather={};regions=[];sns=[];unmatched=[];elder=[];survey=[];youth=[];tracking=[]
        names=list(dict.fromkeys(names));dates=sorted(set(str(d)[:7]+'-01' for d in dates))
        with self.connection() as c:
            codes={ALIASES.get(n,n):code for code,n in c.execute('SELECT DISTINCT adm_cd,adm_nm FROM a1_context')}
            year=int(max(dates)[:4]) if dates else 2025
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_survey_annual'").fetchone():
                # 두 지표만 지역 배경으로 제시한다. 세 지원 상황 모두 도움을 줄
                # 사람이 없는 비율은 관계망을, 가족 밖 외로움 동의 비율은 고립감을
                # 가장 직접적으로 보여준다. 둘 다 강남구·연령대 참고값이다.
                metrics=('no_support_all3','loneliness_outside_agree')
                params=(age_band or 'all15plus',year,*metrics)
                rs=c.execute("SELECT payload_json FROM ctx_survey_annual WHERE survey='seoul_survey' AND district='gangnam' AND age_band=? AND year=(SELECT MAX(year) FROM ctx_survey_annual WHERE survey='seoul_survey' AND year<=?) AND metric IN (?,?) ORDER BY CASE metric WHEN 'no_support_all3' THEN 1 WHEN 'loneliness_outside_agree' THEN 2 END",params).fetchall()
                survey=[json.loads(r[0]) for r in rs]
                if age_band in {'20s','30s'}:
                    youth_age='19to29' if age_band=='20s' else '30s'
                    rs=c.execute("SELECT payload_json FROM ctx_youth_reference WHERE kind='household' AND district='gangnam' AND age_band=? AND metric IN ('limited_outing_share','no_support_all_four_share') ORDER BY year DESC LIMIT 2",(youth_age,)).fetchall()
                    youth=[json.loads(r[0]) for r in rs]
            for name in names:
                if name not in codes:continue
                if age_band in {None,'60plus'} and c.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_elder_annual'").fetchone():
                    r=c.execute('SELECT payload_json FROM ctx_elder_annual WHERE adm_cd=? AND year<=? ORDER BY year DESC LIMIT 1',(codes[name],year)).fetchone()
                    if r:elder.append(json.loads(r[0]))
                if age_band and dates and c.execute("SELECT 1 FROM sqlite_master WHERE name='a2_activity_followup'").fetchone():
                    rs=c.execute('SELECT f.payload_json FROM a2_activity_followup f WHERE f.adm_cd=? AND f.age_band=? AND f.date=(SELECT MAX(x.date) FROM a2_activity_followup x WHERE x.adm_cd=f.adm_cd AND x.age_band=f.age_band AND x.signal_date=f.signal_date AND x.date<=?)',(codes[name],age_band,max(dates))).fetchall()
                    tracking.extend(json.loads(r[0]) for r in rs)
                for date in dates:
                    w=window(date);code=codes[name];q=w['exact_quarter']
                    alignment='exact_observation_quarter' if q else 'separate_prior_complete_quarter'
                    if not q:
                        candidate=pd.Period(w['observation_end'],freq='Q')
                        if candidate.end_time.normalize()>pd.Timestamp(w['observation_end']):candidate-=1
                        q=str(candidate)
                        unmatched.append({'행정동':name,'label_month':date[:7],'overlap_quarters':w['overlap_quarters']})
                    if q:
                        if age_band:
                            rs=c.execute('SELECT payload_json FROM a3a_comparison WHERE period=? AND adm_cd=? AND age=?',(q,code,AGE_LABEL[age_band])).fetchall()
                            if not rs:rs=c.execute('SELECT payload_json FROM a3a_feature WHERE period=? AND adm_cd=? AND age=?',(q,code,AGE_LABEL[age_band])).fetchall()
                            for r in rs:
                                p=json.loads(r[0]);key=(name,q,p['domain'],alignment)
                                local[key]={'행정동':name,'scope':'merchant_dong','period':q,'alignment':alignment,**p}
                        else:
                            r=c.execute('SELECT payload_json FROM a3a_quarter_summary WHERE period=? AND adm_cd=?',(q,code)).fetchone()
                            if r:local[(name,q,alignment)]={'행정동':name,'scope':'merchant_dong','period':q,'alignment':alignment,**json.loads(r[0])}
                    for month in w['observation_months']:
                        if age_band:
                            rs=c.execute('SELECT age,domain,payload_json FROM a3b_feature WHERE period=? AND district=? AND age=?',(month,'11680',AGE_LABEL[age_band])).fetchall()
                            for age,domain,payload in rs:
                                shared[(month,age,domain)]={'district':'강남구','period':month,'scope':'merchant_district_shared',**json.loads(payload)}
                        else:
                            r=c.execute('SELECT payload_json FROM a3b_month_summary WHERE period=? AND district=?',(month,'11680')).fetchone()
                            if r:shared[(month,'all','all')]={'district':'강남구','period':month,'scope':'merchant_district_shared',**json.loads(r[0])}
                    r=c.execute('SELECT payload_json FROM ctx_weather WHERE date=?',(date,)).fetchone()
                    if r:weather[date]=json.loads(r[0])
                    if age_band and c.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_sns_index'").fetchone():
                        r=c.execute('SELECT payload_json FROM ctx_sns_index WHERE adm_cd=? AND date=? AND age_band=?',(code,date,age_band)).fetchone()
                        if r:sns.append(json.loads(r[0]))
                region=self.context(name,max(dates) if dates else None)
                if not region.empty:
                    r=region.iloc[0]
                    regions.append({k:r[k] for k in ['dong_name','period','cluster_type','retrospective_context','hh_1_ratio','hh_2_ratio','age_60_plus_ratio','disability_ratio','livelihood_recipient_ratio','elderly_living_alone_rate_65plus'] if k in r})
        return {'analysis1':regions,'analysis3_dong':list(local.values()),'analysis3_district_shared':list(shared.values()),
                'weather':weather,'sns_same_period':sns,'non_exact_quarter_windows':unmatched,
                'elder_65plus_dong':elder,'survey_district_shared':survey,'youth_reference_shared':youth,
                'activity_followup':tracking,
                'scope_note':'행정동 상권 자료와 강남구 상점 소비 자료는 보조 맥락이며 해당 동 주민의 소비나 신호 원인을 뜻하지 않습니다.',
                'district_rows_shared_once':True,'retrospective_only':True}
