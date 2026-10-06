from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd

MALE_COLS=[f'MAN_FLOW_POP_CNT_{x}' for x in ['10G','20G','30G','40G','50G','60GU']]
FEMALE_COLS=[f'WMAN_FLOW_POP_CNT_{x}' for x in ['10G','20G','30G','40G','50G','60GU']]
AGE_GROUPS={
 '10':['MAN_FLOW_POP_CNT_10G','WMAN_FLOW_POP_CNT_10G'],
 '20':['MAN_FLOW_POP_CNT_20G','WMAN_FLOW_POP_CNT_20G'],
 '30':['MAN_FLOW_POP_CNT_30G','WMAN_FLOW_POP_CNT_30G'],
 '40':['MAN_FLOW_POP_CNT_40G','WMAN_FLOW_POP_CNT_40G'],
 '50':['MAN_FLOW_POP_CNT_50G','WMAN_FLOW_POP_CNT_50G'],
 '60_plus':['MAN_FLOW_POP_CNT_60GU','WMAN_FLOW_POP_CNT_60GU'],
}
HOUR_COLS=[f'TMST_{h:02d}' for h in range(24)]
DAY_COLS=['FLOW_POP_CNT_MON','FLOW_POP_CNT_TUS','FLOW_POP_CNT_WED','FLOW_POP_CNT_THU','FLOW_POP_CNT_FRI','FLOW_POP_CNT_SAT','FLOW_POP_CNT_SUN']
WEEKDAY_COLS=DAY_COLS[:5]; WEEKEND_COLS=DAY_COLS[5:]
DAY_NAME_MAP=dict(zip(DAY_COLS,['월','화','수','목','금','토','일']))

# 2017 행정동 경계 기준 강남구 22개 코드. 1123074의 표시명만 개포3동으로 표준화.
GANGNAM_DONGS={
 '1123051':'신사동','1123052':'논현1동','1123053':'논현2동','1123058':'삼성1동','1123059':'삼성2동',
 '1123060':'대치1동','1123061':'대치4동','1123063':'역삼1동','1123064':'역삼2동','1123065':'도곡1동',
 '1123066':'도곡2동','1123067':'개포1동','1123068':'개포4동','1123071':'세곡동','1123072':'일원본동',
 '1123073':'일원1동','1123074':'개포3동','1123075':'수서동','1123076':'압구정동','1123077':'청담동',
 '1123078':'대치2동','1123079':'개포2동'
}

def read_skt(path: str|Path) -> pd.DataFrame:
    df=pd.read_csv(path,sep='|',encoding='utf-8-sig',dtype={'BLOCK_CD':str},low_memory=False)
    return df.drop_duplicates().copy()

def discover_month_files(raw_dir: str|Path, prefix: str) -> dict[str,Path]:
    out={}
    for p in Path(raw_dir).glob(f'{prefix}_*.csv'):
        m=re.search(r'(20\d{4})',p.name)
        if m: out[m.group(1)]=p
    return dict(sorted(out.items()))

def build_coord_map(df: pd.DataFrame, boundary_path: str|Path) -> pd.DataFrame:
    """Colab 원본과 동일하게 EPSG:5179 좌표를 행정동 경계에 within 공간조인한다."""
    try:
        import geopandas as gpd
    except ImportError as e:
        raise ImportError("SKT 공간조인에는 geopandas가 필요합니다: pip install geopandas") from e
    geo=gpd.read_file(boundary_path)
    if geo.crs is None:
        raise ValueError("행정동 경계 파일에 CRS가 없습니다.")
    if str(geo.crs).upper() != "EPSG:5179":
        geo=geo.to_crs("EPSG:5179")
    gangnam=geo[geo["adm_nm"].astype(str).str.contains("강남구",na=False)][["adm_cd","adm_nm","geometry"]].copy()
    gangnam["adm_cd"]=gangnam["adm_cd"].astype(str)
    pts=df[["X_COORD","Y_COORD"]].drop_duplicates().copy()
    pts=gpd.GeoDataFrame(pts,geometry=gpd.points_from_xy(pts.X_COORD,pts.Y_COORD),crs="EPSG:5179")
    m=gpd.sjoin(pts,gangnam,how="inner",predicate="within")
    m["dong_name"]=m["adm_nm"].str.replace("서울특별시 강남구 ","",regex=False)
    m.loc[m["adm_cd"]=="1123074","dong_name"]="개포3동"
    return pd.DataFrame(m[["X_COORD","Y_COORD","adm_cd","adm_nm","dong_name"]])

def add_admin(df: pd.DataFrame, boundary_path: str|Path) -> pd.DataFrame:
    cmap=build_coord_map(df,boundary_path)
    return df.merge(cmap,on=["X_COORD","Y_COORD"],how="inner",validate="many_to_one")

def _safe_div(a,b):
    return a.div(b.replace(0,np.nan))

def preprocess_age(df: pd.DataFrame, boundary_path) -> pd.DataFrame:
    x=add_admin(df, boundary_path)
    x['male_flow']=x[MALE_COLS].sum(axis=1); x['female_flow']=x[FEMALE_COLS].sum(axis=1)
    x['total_flow']=x['male_flow']+x['female_flow']
    for age,cols in AGE_GROUPS.items(): x[f'age_{age}_flow']=x[cols].sum(axis=1)
    sums=['male_flow','female_flow','total_flow']+[f'age_{a}_flow' for a in AGE_GROUPS]
    g=x.groupby(['STD_YM','adm_cd','adm_nm','dong_name'],as_index=False)[sums].sum()
    pc=x.groupby(['STD_YM','adm_cd','adm_nm','dong_name']).size().reset_index(name='point_count')
    g=g.merge(pc,on=['STD_YM','adm_cd','adm_nm','dong_name'],validate='one_to_one')
    g['flow_per_point']=g['total_flow']/g['point_count']
    g['male_ratio']=_safe_div(g['male_flow'],g['total_flow']); g['female_ratio']=_safe_div(g['female_flow'],g['total_flow'])
    for age in AGE_GROUPS: g[f'age_{age}_ratio']=_safe_div(g[f'age_{age}_flow'],g['total_flow'])
    return g

def preprocess_time(df: pd.DataFrame, boundary_path, time_profile: str="baseline") -> pd.DataFrame:
    x=add_admin(df, boundary_path)
    g=x.groupby(['STD_YM','adm_cd','adm_nm','dong_name'],as_index=False)[HOUR_COLS].sum()
    pc=x.groupby(['STD_YM','adm_cd','adm_nm','dong_name']).size().reset_index(name='time_point_count')
    g=g.merge(pc,on=['STD_YM','adm_cd','adm_nm','dong_name'],validate='one_to_one')
    g['time_total']=g[HOUR_COLS].sum(axis=1); g['time_flow_per_point']=g['time_total']/g['time_point_count']
    # Analysis1 최종 2025H2 PCA 입력 기준(baseline): 00~06 / 07~11 / 12~18 / 19~23.
    # legacy_202507은 과거 gangnam_db1_features_202507.csv 회귀검증 전용이다.
    profiles={
        'baseline': {'night':range(0,7),'morning':range(7,12),'daytime':range(12,19),'evening':range(19,24)},
        'legacy_202507': {'night':range(0,6),'morning':range(6,11),'daytime':range(11,19),'evening':range(19,24)},
    }
    if time_profile not in profiles:
        raise ValueError(f'Unknown time_profile: {time_profile}')
    periods=profiles[time_profile]
    for name,hours in periods.items(): g[f'{name}_ratio']=_safe_div(g[[f'TMST_{h:02d}' for h in hours]].sum(axis=1),g['time_total'])
    peak=g[HOUR_COLS].idxmax(axis=1); g['peak_hour']=peak.str[-2:].astype(int)
    g['peak_hour_ratio']=g[HOUR_COLS].max(axis=1)/g['time_total']
    return g

def preprocess_weekday(df: pd.DataFrame, boundary_path) -> pd.DataFrame:
    x=add_admin(df, boundary_path)
    g=x.groupby(['STD_YM','adm_cd','adm_nm','dong_name'],as_index=False)[DAY_COLS].sum()
    pc=x.groupby(['STD_YM','adm_cd','adm_nm','dong_name']).size().reset_index(name='weekday_point_count')
    g=g.merge(pc,on=['STD_YM','adm_cd','adm_nm','dong_name'],validate='one_to_one')
    g['week_total']=g[DAY_COLS].sum(axis=1); g['week_flow_per_point']=g['week_total']/g['weekday_point_count']
    wd=g[WEEKDAY_COLS].sum(axis=1); we=g[WEEKEND_COLS].sum(axis=1)
    # 기존 202507 산출물 컬럼명(workday_ratio)을 그대로 보존한다.
    g['workday_ratio']=_safe_div(wd,g['week_total']); g['weekend_ratio']=_safe_div(we,g['week_total'])
    g['sat_ratio']=_safe_div(g['FLOW_POP_CNT_SAT'],g['week_total']); g['sun_ratio']=_safe_div(g['FLOW_POP_CNT_SUN'],g['week_total'])
    g['weekend_weekday_index']=(we/2)/(wd/5)
    peak=g[DAY_COLS].idxmax(axis=1); g['peak_day']=peak.map(DAY_NAME_MAP); g['peak_day_ratio']=g[DAY_COLS].max(axis=1)/g['week_total']
    return g

def build_month_features(age_path, time_path, wkdy_path, boundary_path, time_profile: str="baseline") -> pd.DataFrame:
    a=preprocess_age(read_skt(age_path), boundary_path); t=preprocess_time(read_skt(time_path), boundary_path, time_profile=time_profile); w=preprocess_weekday(read_skt(wkdy_path), boundary_path)
    keys=['STD_YM','adm_cd','adm_nm','dong_name']
    a_cols=keys+['total_flow','point_count','flow_per_point','male_ratio','female_ratio']+[f'age_{a}_ratio' for a in AGE_GROUPS]
    t_cols=keys+['time_total','time_point_count','time_flow_per_point','night_ratio','morning_ratio','daytime_ratio','evening_ratio','peak_hour','peak_hour_ratio']
    w_cols=keys+['week_total','weekday_point_count','week_flow_per_point','workday_ratio','weekend_ratio','weekend_weekday_index','sat_ratio','sun_ratio','peak_day','peak_day_ratio']
    out=a[a_cols].merge(t[t_cols],on=keys,validate='one_to_one').merge(w[w_cols],on=keys,validate='one_to_one')
    return out.sort_values('adm_cd').reset_index(drop=True)

def build_month_from_dir(raw_dir: str|Path, month: str, boundary_path: str|Path, time_profile: str="baseline") -> pd.DataFrame:
    d=Path(raw_dir)
    def pick(prefix):
        hits=list(d.glob(f'{prefix}_{month}*.csv'))
        if len(hits)!=1: raise FileNotFoundError(f'{prefix}_{month}: expected 1 file, found {len(hits)}')
        return hits[0]
    return build_month_features(pick('flow_age_pop'),pick('flow_time_pop'),pick('flow_wkdy_pop'),boundary_path,time_profile=time_profile)

def validate_against_reference(actual: pd.DataFrame, reference_path: str|Path, atol=1e-8, rtol=1e-6) -> dict:
    ref=pd.read_csv(reference_path,dtype={'adm_cd':str})
    ref.loc[ref['adm_cd']=='1123074','dong_name']='개포3동'
    act=actual.copy(); act['adm_cd']=act['adm_cd'].astype(str)
    missing=set(ref.columns)-set(act.columns)
    if missing or len(act)!=len(ref) or act.adm_cd.duplicated().any() or set(act.adm_cd)!=set(ref.adm_cd):
        return {'ok':False,'rows':len(act),'missing_columns':sorted(missing),'error':'Schema/area coverage mismatch'}
    # reference에는 STD_YM이 없으므로 비교에서 제외
    common=[c for c in ref.columns if c in act.columns]
    keys=['adm_cd','dong_name']
    m=ref[common].merge(act[common],on=keys,suffixes=('_ref','_act'),validate='one_to_one')
    num=[c for c in common if c not in ['adm_cd','adm_nm','dong_name','peak_day']]
    diffs={}
    for c in num:
        r=pd.to_numeric(m[f'{c}_ref'],errors='coerce'); a=pd.to_numeric(m[f'{c}_act'],errors='coerce')
        diffs[c]=float(np.nanmax(np.abs(r-a))) if len(r) else np.nan
    cat={c:int((m[f'{c}_ref'].astype(str)!=m[f'{c}_act'].astype(str)).sum()) for c in ['peak_day'] if c in common}
    ok=all(np.allclose(pd.to_numeric(m[f'{c}_ref'],errors='coerce'),pd.to_numeric(m[f'{c}_act'],errors='coerce'),equal_nan=True,atol=atol,rtol=rtol) for c in num) and all(v==0 for v in cat.values())
    return {'ok':bool(ok),'rows':len(m),'max_abs_diff':diffs,'categorical_mismatch':cat}

def build_period_from_dir(raw_dir: str|Path, months: list[str], boundary_path: str|Path, time_profile: str='baseline') -> tuple[pd.DataFrame,pd.DataFrame]:
    """Build monthly SKT features and the Analysis1 period mean used by the 2025H2 baseline."""
    frames=[]
    for month in months:
        m=build_month_from_dir(raw_dir, month, boundary_path, time_profile=time_profile)
        observed=set(m['STD_YM'].astype(str).unique())
        if observed != {month}:
            raise ValueError(f'{month}: STD_YM mismatch: {sorted(observed)}')
        if len(m)!=22 or m['adm_cd'].nunique()!=22:
            raise ValueError(f'{month}: expected 22 Gangnam dongs, got {len(m)} rows/{m["adm_cd"].nunique()} dongs')
        frames.append(m)
    monthly=pd.concat(frames,ignore_index=True)
    mean_cols=['flow_per_point','male_ratio','age_10_ratio','age_20_ratio','age_30_ratio','age_40_ratio','age_50_ratio','age_60_plus_ratio',
               'night_ratio','morning_ratio','daytime_ratio','evening_ratio','weekend_weekday_index']
    period=(monthly.groupby(['adm_cd','dong_name'],as_index=False)[mean_cols].mean()
            .sort_values('adm_cd').reset_index(drop=True))
    return monthly, period
