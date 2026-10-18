"""Read-only DB1 evidence: Db1Repository 구현의 공통부(조회 SQL·캐시·동별 인덱스). Never fall back to a precomputed legacy CSV.

챗봇 로직은 SQL을 직접 쓰지 않고 db1_repository.Db1Repository 계약의 메서드만 부릅니다.
연결·신선도·상태 확인은 하위 클래스가 맡고, 현재 구현은 pg_repository.PostgresDb1Repository 하나입니다."""
from __future__ import annotations
from contextlib import contextmanager
import json,threading
import pandas as pd

from .period_matching import nearest_period
from .district_normalizer import ALIASES

SOURCES={'detection':'DB1: a2_detection','evidence':'DB1: a2_evidence',
         'feature':'DB1: a2_feature','typology':'DB1: a1_context / a1_input'}
CORE=('call_contacts','text_contacts','weekday_move_count','weekend_move_count')
AGE_LABEL={'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60대이상'}

class _Memo:
    """한 번의 조회 안에서 같은 SQL·인자의 결과를 다시 묻지 않게 합니다(결과는 항상 같음)."""
    def __init__(self,con):
        self.con=con;self.store={}
    def all(self,sql,params=()):
        key=(sql,tuple(params))
        if key not in self.store:self.store[key]=self.con.execute(sql,tuple(params)).fetchall()
        return self.store[key]
    def one(self,sql,params=()):
        rows=self.all(sql,params)
        return rows[0] if rows else None


class SqlDb1Repository:
    # 여러 행을 돌려주는 조회는 ORDER BY를 명시합니다. SQLite는 기본키 색인 순서로, PostgreSQL은 저장 순서로 돌려줘
    # 같은 SQL이라도 행 순서가 달라질 수 있기 때문입니다(실제 db1.sqlite로 대조하다 확인). 아래 순서는 원래 SQLite가 돌려주던 기본키 순서와 같습니다.
    """DB1 근거 조회의 공통 로직(SQL·캐시·인덱스). 연결·신선도·상태 확인은 하위 클래스가 맡습니다.

    SQL은 표준 구문과 `?` 자리표시자만 씁니다. 하위 클래스가 `?`를 자기 드라이버 형식으로 바꾸는 연결 객체
    (`execute(sql, params)` → `fetchall()`/`fetchone()`)를 돌려주면 같은 로직이 그대로 동작합니다.

    효율: 연결 한 개를 재사용하고 «갱신 완료» 확인은 연결을 열 때만 합니다. 캐시는 이 객체의 수명 동안만 유지됩니다(요청 단위).
    """
    _immutable=False  # True이면 열린 뒤에는 신선도를 다시 확인하지 않음

    def __init__(self):
        self._lock=threading.RLock()
        self._con=None;self._token=None;self._cache={};self._dates_cache={};self._index_cache={};self._depth=0

    # ── 하위 클래스가 구현하는 부분 ──────────────────────────────
    def _precheck(self):
        """연결 전 확인(예: 파일 존재). 문제가 있으면 예외."""

    def _connect(self):
        """(연결, 신선도 토큰)을 돌려줍니다. «갱신 완료» 상태가 아니면 ValueError."""
        raise NotImplementedError

    def _is_stale(self):
        """열려 있는 연결이 더는 최신 공개본이 아닌지."""
        return False

    def _table_names(self,con):
        """조회 가능한 테이블 이름 집합(선택 자료의 존재 확인용)."""
        raise NotImplementedError

    def has_data(self):
        raise NotImplementedError

    def pipeline_status(self):
        raise NotImplementedError

    # ── 연결 수명 ────────────────────────────────────────────────
    def _open(self,check=True):
        """연결을 돌려줍니다. (_lock을 잡은 채 호출)

        check=True(가장 바깥 호출)일 때만 신선도를 확인하고, 최신이 아니면 연결과 캐시를 버리고 다시 엽니다.
        """
        if self._con is not None and (not check or self._immutable):return self._con
        self._precheck()
        if self._con is not None and not self._is_stale():return self._con
        self.close()
        self._con,self._token=self._connect()
        return self._con

    def _close_connection(self,con):
        con.close()

    def close(self):
        """연결과 캐시를 닫습니다. 요청이 끝나면 호출하세요(호출하지 않아도 객체가 사라질 때 닫힙니다)."""
        with self._lock:
            if self._con is not None:
                try:self._close_connection(self._con)
                finally:self._con=None
            self._token=None;self._cache={};self._dates_cache={};self._index_cache={}

    @contextmanager
    def connection(self):
        with self._lock:
            con=self._open(check=self._depth==0)
            self._depth+=1
            try:yield con
            finally:self._depth-=1

    def _cached(self,key,loader):
        """같은 공개본에서는 같은 조회를 한 번만 합니다."""
        with self._lock:
            self._open(check=self._depth==0)  # 바깥 호출이면 신선도 확인(바뀌었으면 캐시가 비워짐)
            if key not in self._cache:
                self._depth+=1
                try:self._cache[key]=loader()
                finally:self._depth-=1
            return self._cache[key]

    def districts(self):
        def load():
            with self.connection() as c:names=[r[0] for r in c.execute('SELECT DISTINCT adm_nm FROM a1_context')]
            return {ALIASES.get(n,n) for n in names}
        return set(self._cached(('districts',),load))

    def cluster_types(self):
        def load():
            with self.connection() as c:
                return [str(r[0]) for r in c.execute('SELECT DISTINCT cluster_type FROM a1_context WHERE cluster_type IS NOT NULL ORDER BY cluster_type')]
        return list(self._cached(('cluster_types',),load))

    def cluster_districts(self,cluster):
        def load():
            with self.connection() as c:
                return [str(r[0]) for r in c.execute('SELECT DISTINCT adm_nm FROM a1_context WHERE cluster_type=? ORDER BY adm_nm',(cluster,))]
        return list(self._cached(('cluster_districts',cluster),load))

    def available_period(self):
        def load():
            with self.connection() as c:lo,hi=c.execute('SELECT MIN(date),MAX(date) FROM a2_detection').fetchone()
            return (lo[:7],hi[:7]) if lo else ('2025-07','2025-07')
        return self._cached(('available_period',),load)

    def consumption_period(self):
        def load():
            with self.connection() as c:lo,hi=c.execute('SELECT MIN(period),MAX(period) FROM a3a_feature').fetchone()
            if not lo:return self.available_period()
            return (pd.Period(lo,freq='Q').start_time.strftime('%Y-%m'),pd.Period(hi,freq='Q').end_time.strftime('%Y-%m'))
        return self._cached(('consumption_period',),load)

    def _read(self,name,age_band=None):
        """탐지·근거 표(DataFrame). 같은 표는 한 번만 읽습니다. 호출부는 결과를 제자리에서 바꾸지 않습니다."""
        return self._cached(('read',name,age_band),lambda:self._load_frame(name,age_band))

    def _load_frame(self,name,age_band=None):
        with self.connection() as c:
            if name=='age_detection':
                sql="SELECT result_json FROM a2_age_detection WHERE age_scheme='service'"
                params=[]
                if age_band:
                    sql += ' AND age_band=?'; params.append(age_band)
                sql += ' ORDER BY date,adm_cd,age_band'
                rows=c.execute(sql,params).fetchall()
            elif age_band:
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
        if name!='feature' or age_band or name=='age_detection':
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
            if age_band or name=='age_detection':
                f['consecutive_signal']=f.get('adjacent_signal_run',pd.Series(0,index=f.index)).gt(1)
            elif 'consecutive_signal' not in f:f['consecutive_signal']=False
        return f

    def _dates(self,f):
        """표의 date 열을 날짜로 바꾼 결과. 같은 표(캐시된 것)는 한 번만 변환합니다."""
        key=(id(f),len(f))
        with self._lock:
            if key not in self._dates_cache:self._dates_cache[key]=pd.to_datetime(f.date,format='mixed')
            return self._dates_cache[key]

    def _dong_entry(self,frame,dong):
        """그 동의 (date·행정동 순으로 정렬한 행, 정렬된 날짜 배열 또는 None). 없으면 None. 요청된 동만 만들어 둡니다.

        날짜가 모두 해석되고 정렬 순서와 시간 순서가 같을 때만 날짜 배열을 둡니다(이진 탐색 가능).
        그렇지 않으면 배열이 None이라 기존 방식(마스크로 거르기)으로 처리합니다.
        """
        key=(id(frame),len(frame))
        with self._lock:
            index=self._index_cache.get(key)
            if index is None:
                positions=frame.groupby('행정동',sort=False).indices if not frame.empty else {}
                index=self._index_cache[key]={'positions':positions,'parts':{}}
            if dong not in index['parts']:
                rows=index['positions'].get(dong)
                if rows is None:index['parts'][dong]=None
                else:
                    part=frame.iloc[rows].sort_values(['date','행정동'])
                    dates=pd.to_datetime(part['date'],format='mixed')
                    index['parts'][dong]=(part,dates.to_numpy() if dates.notna().all() and dates.is_monotonic_increasing else None)
            return index['parts'][dong]

    def _period(self,f,start,end):
        if f.empty:return f
        dates=self._dates(f)
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

    def age_signal_cases(self,start=None,end=None,dong=None,signal='any',age_band=None):
        """Return only confirmed rows from the age-level detection table.

        The overall signal table and the age-level table have different grains;
        keeping this as a separate repository method prevents a global request
        from accidentally showing a dong-level row as an age-level case.
        """
        f=self._read('age_detection',age_band)
        if f.empty:return f.copy()
        f=self._period(f,start,end)
        if dong:f=f.loc[f['행정동'].eq(dong)]
        column={'any':'any_signal','communication':'communication_signal',
                'mobility':'mobility_signal','combined':'combined_signal'}[signal]
        # A deferred/unknown flag is deliberately not treated as a positive
        # signal, while the original nullable component columns remain intact.
        return f.loc[f[column].fillna(False).eq(True)].sort_values(['date','행정동','age_band'])

    def anomalies(self,start=None,end=None,metric=None,age_band=None,dongs=()):
        f=self.activity(None,start,end,age_band);metric=metric or 'weekday_move_count'
        rz=metric+'_residual_change_expanding_rz'
        if rz not in f:raise ValueError('지원하지 않는 활동 지표입니다.')
        if dongs:f=f.loc[f['행정동'].isin(dongs)]
        return f.loc[f[rz].notna()].sort_values(rz).head(10),rz

    def activity(self,dong,start=None,end=None,age_band=None):
        frame=self._read('detection',age_band)
        if dong:
            entry=self._dong_entry(frame,dong)
            if entry is None:return frame.iloc[0:0].copy()  # 그 동의 행이 없음(같은 열 구조의 빈 표)
            part,dates=entry
            if dates is not None:
                # 정렬된 날짜에서 기간의 양 끝을 이진 탐색: 마스크·재정렬 없이 같은 행·같은 순서를 돌려줍니다.
                low=dates.searchsorted(pd.Timestamp(start).to_datetime64(),side='left') if start else 0
                high=dates.searchsorted((pd.Timestamp(end)+pd.offsets.MonthEnd(0)).to_datetime64(),side='right') if end else len(dates)
                return part.iloc[low:high].copy()
            frame=part
        f=self._period(frame,start,end)
        if dong:f=f.loc[f['행정동'].eq(dong)]
        return f.sort_values(['date','행정동'])

    def evidence(self,dong,start=None,end=None,age_band=None):
        if age_band:return self.signals(start,end,dong,'any',age_band)
        f=self._period(self._read('evidence'),start,end)
        return f.loc[f['행정동'].eq(dong)].sort_values('date')

    def context(self,dong,as_of=None):
        rows=self._cached(('context_rows',as_of or '9999-12-31'),lambda:self._context_rows(as_of))
        for feature,raw,period,kind,effective,metadata in rows:
            r={**json.loads(raw),**json.loads(feature)}
            r['dong_name']=ALIASES.get(r['dong_name'],r['dong_name'])
            if r['dong_name']==dong:
                r.update(period=period,cluster_type=kind,effective_from=effective,
                         retrospective_context=json.loads(metadata).get('retrospective_context',False))
                return pd.DataFrame([r])
        return pd.DataFrame()

    def _context_rows(self,as_of=None):
        with self.connection() as c:
            return c.execute('SELECT c.feature_json,i.input_json,c.period,c.cluster_type,c.effective_from,r.metadata_json FROM a1_context c JOIN a1_input i ON i.adm_cd=c.adm_cd AND i.period=c.period JOIN db1_run r ON r.analysis=\'analysis1\' AND r.period=c.period WHERE c.effective_from<=? ORDER BY c.effective_from DESC',
                           (as_of or '9999-12-31',)).fetchall()

    # ── 저장소 경계 밖으로 새던 SQL을 모은 메서드들 ─────────────────────────
    def district_codes(self):
        """행정동 이름(별칭 정규화) → 행정동 코드."""
        def load():
            with self.connection() as c:
                return {ALIASES.get(n,n):code for code,n in c.execute('SELECT DISTINCT adm_cd,adm_nm FROM a1_context')}
        return dict(self._cached(('district_codes',),load))

    # 테이블별로 SQL 조건을 걸 수 있는 컬럼
    CONSUMPTION_TABLES={'a3a_feature':('period','adm_cd','age'),'a3a_comparison':('period','adm_cd','age'),
                        'a3b_feature':('period','district','age')}
    MAX_IN=500  # IN 목록이 이보다 길면 그 조건은 걸지 않습니다(더 많이 읽을 뿐 결과는 같음)

    def consumption_payloads(self,table,*,periods=None,adm_cds=None,ages=None,districts=None):
        """소비 자료 테이블의 payload. 목록 조건을 주면 해당 값의 행만 SQL로 읽습니다.

        조건을 주지 않으면 전체, 빈 목록을 주면 «아무 행도 해당하지 않음»이라 빈 결과입니다.
        """
        if table not in self.CONSUMPTION_TABLES:raise ValueError('지원하지 않는 소비 자료입니다.')
        wanted={'period':periods,'adm_cd':adm_cds,'age':ages,'district':districts}
        conditions,params=[],[]
        for column,values in wanted.items():
            if values is None:continue
            if column not in self.CONSUMPTION_TABLES[table]:raise ValueError(f'{table}에는 {column} 조건을 쓸 수 없습니다.')
            values=sorted(set(values))
            if not values:return []
            if len(values)>self.MAX_IN:continue
            conditions.append(f'{column} IN ({",".join("?"*len(values))})');params.extend(values)
        sql=f'SELECT payload_json FROM {table}'+(' WHERE '+' AND '.join(conditions) if conditions else '')
        def load():
            with self.connection() as c:
                return [json.loads(r[0]) for r in c.execute(sql,params)]
        return [dict(payload) for payload in self._cached(('consumption',table,sql,tuple(params)),load)]

    def consumption_evidence(self,names,start,end,age):
        """요청한 달력 기간의 동 상권 자료(rows)와 강남구 공통 소비 자료(shared)를 함께 돌려줍니다."""
        rows=[];shared={}
        with self.connection() as con:
            c=_Memo(con)
            mapping={n:code for code,n in c.all('SELECT DISTINCT adm_cd,adm_nm FROM a1_context')}
            mapping={ALIASES.get(n,n):code for n,code in mapping.items()}
            for month in pd.period_range(start,end,freq='M'):
                q=f'{month.year}Q{month.quarter}'
                for name in names:
                    if age:
                        rs=c.all('SELECT payload_json FROM a3a_comparison WHERE period=? AND adm_cd=? AND age=? ORDER BY domain',(q,mapping[name],AGE_LABEL[age]))
                        for r in rs:
                            payload=json.loads(r[0]);key=(name,q,payload['domain'])
                            if not any((x['행정동'],x['period'],x.get('domain'))==key for x in rows):rows.append({'행정동':name,'범위':'해당 동 소재 상점',**payload})
                    else:
                        r=c.one('SELECT payload_json FROM a3a_quarter_summary WHERE period=? AND adm_cd=?',(q,mapping[name]))
                        if r and not any(x['행정동']==name and x['period']==q for x in rows):rows.append({'행정동':name,'period':q,'범위':'해당 동 소재 상점',**json.loads(r[0])})
                if age:
                    rs=c.all('SELECT domain,payload_json FROM a3b_feature WHERE period=? AND district=? AND age=? ORDER BY domain',(str(month),'11680',AGE_LABEL[age]))
                    for domain,payload in rs:shared[(str(month),domain)]={'district':'강남구','period':str(month),'scope':'merchant_district_shared',**json.loads(payload)}
                else:
                    r=c.one('SELECT payload_json FROM a3b_month_summary WHERE period=? AND district=?',(str(month),'11680'))
                    if r:shared[str(month)]={'district':'강남구','period':str(month),'scope':'merchant_district_shared',**json.loads(r[0])}
        return rows,shared

    def supplements(self,names,dates,age_band=None):
        """Align local quarters to observation windows; deduplicate shared district data."""
        # 관측 기간 계산은 공식 DB1 파이프라인의 함수를 씁니다.
        from pipelines.db1.Context.source_semantics import window
        local={};shared={};weather={};regions=[];sns=[];unmatched=[];elder=[];survey=[];youth=[];tracking=[]
        names=list(dict.fromkeys(names));dates=sorted(set(str(d)[:7]+'-01' for d in dates))
        with self.connection() as con:
            c=_Memo(con)
            tables=self._table_names(con)
            weather_rows=c.all('SELECT date,payload_json FROM ctx_weather ORDER BY date') if 'ctx_weather' in tables else []
            weather_by_date={str(date)[:7]:json.loads(payload) for date,payload in weather_rows}
            codes={ALIASES.get(n,n):code for code,n in c.all('SELECT DISTINCT adm_cd,adm_nm FROM a1_context')}
            year=int(max(dates)[:4]) if dates else 2025
            if 'ctx_survey_annual' in tables:
                # 두 지표만 지역 배경으로 제시한다. 세 지원 상황 모두 도움을 줄
                # 사람이 없는 비율은 관계망을, 가족 밖 외로움 동의 비율은 고립감을
                # 가장 직접적으로 보여준다. 둘 다 강남구·연령대 참고값이다.
                metrics=('no_support_all3','loneliness_outside_agree')
                params=(age_band or 'all15plus',year,*metrics)
                rs=c.all("SELECT payload_json FROM ctx_survey_annual WHERE survey='seoul_survey' AND district='gangnam' AND age_band=? AND year=(SELECT MAX(year) FROM ctx_survey_annual WHERE survey='seoul_survey' AND year<=?) AND metric IN (?,?) ORDER BY CASE metric WHEN 'no_support_all3' THEN 1 WHEN 'loneliness_outside_agree' THEN 2 END",params)
                survey=[json.loads(r[0]) for r in rs]
                if age_band in {'20s','30s'}:
                    youth_age='19to29' if age_band=='20s' else '30s'
                    rs=c.all("SELECT payload_json FROM ctx_youth_reference WHERE kind='household' AND district='gangnam' AND age_band=? AND metric IN ('limited_outing_share','no_support_all_four_share') ORDER BY year DESC LIMIT 2",(youth_age,))
                    youth=[json.loads(r[0]) for r in rs]
            for name in names:
                if name not in codes:continue
                if age_band in {None,'60plus'} and 'ctx_elder_annual' in tables:
                    r=c.one('SELECT payload_json FROM ctx_elder_annual WHERE adm_cd=? AND year<=? ORDER BY year DESC LIMIT 1',(codes[name],year))
                    if r:elder.append(json.loads(r[0]))
                if age_band and dates and 'a2_activity_followup' in tables:
                    rs=c.all('SELECT f.payload_json FROM a2_activity_followup f WHERE f.adm_cd=? AND f.age_band=? AND f.date=(SELECT MAX(x.date) FROM a2_activity_followup x WHERE x.adm_cd=f.adm_cd AND x.age_band=f.age_band AND x.signal_date=f.signal_date AND x.date<=?) ORDER BY f.signal_date,f.date,f.age_band,f.detection_model_version,f.version',(codes[name],age_band,max(dates)))
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
                            rs=c.all('SELECT payload_json FROM a3a_comparison WHERE period=? AND adm_cd=? AND age=? ORDER BY domain',(q,code,AGE_LABEL[age_band]))
                            if not rs:rs=c.all('SELECT payload_json FROM a3a_feature WHERE period=? AND adm_cd=? AND age=? ORDER BY domain',(q,code,AGE_LABEL[age_band]))
                            for r in rs:
                                p=json.loads(r[0]);key=(name,q,p['domain'],alignment)
                                local[key]={'행정동':name,'scope':'merchant_dong','period':q,'alignment':alignment,**p}
                        else:
                            r=c.one('SELECT payload_json FROM a3a_quarter_summary WHERE period=? AND adm_cd=?',(q,code))
                            if r:local[(name,q,alignment)]={'행정동':name,'scope':'merchant_dong','period':q,'alignment':alignment,**json.loads(r[0])}
                    for month in w['observation_months']:
                        if age_band:
                            rs=c.all('SELECT age,domain,payload_json FROM a3b_feature WHERE period=? AND district=? AND age=? ORDER BY domain',(month,'11680',AGE_LABEL[age_band]))
                            for age,domain,payload in rs:
                                shared[(month,age,domain)]={'district':'강남구','period':month,'scope':'merchant_district_shared',**json.loads(payload)}
                        else:
                            r=c.one('SELECT payload_json FROM a3b_month_summary WHERE period=? AND district=?',(month,'11680'))
                            if r:shared[(month,'all','all')]={'district':'강남구','period':month,'scope':'merchant_district_shared',**json.loads(r[0])}
                    requested_weather=date[:7]
                    matched_weather=requested_weather if requested_weather in weather_by_date else nearest_period(weather_by_date, requested_weather)
                    if matched_weather:
                        item=dict(weather_by_date[matched_weather])
                        if matched_weather != requested_weather:
                            item['selection_alignment']='nearest_available_period'
                            item['requested_period']=requested_weather
                            item['reference_period']=matched_weather
                        weather[date]=item
                    if age_band and 'ctx_sns_index' in tables:
                        r=c.one('SELECT payload_json FROM ctx_sns_index WHERE adm_cd=? AND date=? AND age_band=?',(code,date,age_band))
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
