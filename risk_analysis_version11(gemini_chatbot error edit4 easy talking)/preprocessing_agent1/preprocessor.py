"""Analysis1 원천자료 → Agent-ready 1행/동 입력 변환기.

CSV 파일이든 API 응답을 DataFrame으로 바꾼 것이든, 아래 `preprocess_from_frames`
함수에 같은 형태로 넣는다. API 키·URL은 이 모듈에 저장하지 않는다.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import pandas as pd

CURRENT_NAME = {"1123074": "개포3동"}
PCA_MAPPING = {
 "active_pop":["male_ratio","age_10_ratio","age_20_ratio","age_30_ratio","age_40_ratio","age_50_ratio","age_60_plus_ratio"],
 "time_structure":["night_ratio","morning_ratio","daytime_ratio","evening_ratio"],
 "resident_age":["resident_ratio_0_19","resident_ratio_20_29","resident_ratio_30_39","resident_ratio_40_49","resident_ratio_50_64","resident_ratio_65_plus"],
 "household_structure":["hh_1_ratio","hh_2_ratio","hh_3_ratio","hh_4plus_ratio"],
}

class PreprocessError(ValueError): pass

def read_csv(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig","cp949","euc-kr","utf-8"):
        for sep in (",", "\t"):
            try:
                df=pd.read_csv(path, encoding=enc, sep=sep, low_memory=False)
                if df.shape[1] > 1: return df
            except Exception: pass
    raise PreprocessError(f"읽을 수 없는 CSV: {path.name}")

def _file(raw: Path, contains: str) -> Path:
    found=list(raw.glob(f"*{contains}*"))
    if not found: raise PreprocessError(f"원본 폴더에 '{contains}' 파일이 없습니다.")
    return found[0]

def _names(df: pd.DataFrame) -> pd.DataFrame:
    df=df.copy(); df["adm_cd"]=df["adm_cd"].astype(str).str.replace(r"\.0$","",regex=True)
    df["dong_name"]=df["dong_name"].astype(str).str.strip()
    for code,name in CURRENT_NAME.items(): df.loc[df.adm_cd.eq(code),"dong_name"]=name
    return df

def skt_features(df: pd.DataFrame) -> pd.DataFrame:
    need=["adm_cd","dong_name","flow_per_point","male_ratio","age_10_ratio","age_20_ratio","age_30_ratio","age_40_ratio","age_50_ratio","age_60_plus_ratio","night_ratio","morning_ratio","daytime_ratio","evening_ratio","weekend_weekday_index"]
    miss=[x for x in need if x not in df]
    if miss: raise PreprocessError("SKT 유동인구 파일 필수 열 누락: "+", ".join(miss))
    return _names(df[need]).drop_duplicates("adm_cd")

def resident_features(df: pd.DataFrame) -> pd.DataFrame:
    # 팀 노트북과 동일하게 1~2행의 다중 헤더를 값으로 읽고 Q3/Q4를 위치로 나눈다.
    rows=df[(df["동별(1)"].eq("강남구")) & (~df["동별(2)"].eq("소계"))].copy()
    labels=df.iloc[0,3:25].tolist(); vals=[]
    for quarter, start in [("Q3",3),("Q4",25)]:
        x=rows[["동별(2)","항목"]+list(df.columns[start:start+22])].copy()
        x.columns=["dong_name","category"]+["total" if a=="합계" else "age_"+str(a).replace("~","_").replace("세 이상","_plus").replace("세","") for a in labels]
        x["quarter"]=quarter
        for c in x.columns[2:-1]: x[c]=pd.to_numeric(x[c].astype(str).str.replace(",","").replace("-","0"),errors="coerce")
        vals.append(x)
    x=pd.concat(vals); total=x[x.category.eq("계")].copy(); foreign=x[x.category.eq("등록외국인")][["dong_name","quarter","total"]].rename(columns={"total":"foreign"})
    ages={"0_19":["age_0_4","age_5_9","age_10_14","age_15_19"],"20_29":["age_20_24","age_25_29"],"30_39":["age_30_34","age_35_39"],"40_49":["age_40_44","age_45_49"],"50_64":["age_50_54","age_55_59","age_60_64"],"65_plus":["age_65_69","age_70_74","age_75_79","age_80_84","age_85_89","age_90_94","age_95_99","age_100_plus"]}
    for k,cols in ages.items(): total["resident_ratio_"+k]=total[cols].sum(axis=1)/total.total
    total=total.merge(foreign,on=["dong_name","quarter"],validate="one_to_one"); total["foreigner_ratio"]=total.foreign/total.total
    cols=["dong_name",*['resident_ratio_'+k for k in ages],"foreigner_ratio"]
    return total[cols].groupby("dong_name",as_index=False).mean()

def household_features(df: pd.DataFrame) -> pd.DataFrame:
    # 세대원수별 세대수 원본의 3번째 행부터 22개 동, Q3/Q4 각 11열 규칙
    x=df.iloc[2:].copy(); names=["total","hh_1","hh_2","hh_3","hh_4","hh_5","hh_6","hh_7","hh_8","hh_9","hh_10plus"]
    parts=[]
    for start in (2,13):
        q=x.iloc[:,[1]+list(range(start,start+11))].copy(); q.columns=["dong_name"]+names
        for c in names: q[c]=pd.to_numeric(q[c].astype(str).str.replace(",","").replace("-","0"),errors="coerce")
        parts.append(q)
    q=pd.concat(parts); out=q[["dong_name"]].copy(); out["hh_1_ratio"]=q.hh_1/q.total; out["hh_2_ratio"]=q.hh_2/q.total; out["hh_3_ratio"]=q.hh_3/q.total; out["hh_4plus_ratio"]=q[["hh_4","hh_5","hh_6","hh_7","hh_8","hh_9","hh_10plus"]].sum(axis=1)/q.total
    return out.groupby("dong_name",as_index=False).mean()

def disability_features(df: pd.DataFrame, resident: pd.DataFrame) -> pd.DataFrame:
    x=df.copy(); value_col="2025 년" if "2025 년" in x else next((c for c in x if "2025" in str(c)),None)
    if not value_col: raise PreprocessError("장애인 파일에서 2025년 값 열을 찾지 못했습니다.")
    x["v"]=pd.to_numeric(x[value_col].astype(str).str.replace(",","").replace("-","0"),errors="coerce")
    x=x[(x["장애유형별"].eq("합계")) & (x["성별"].eq("계"))][["동별","v"]].rename(columns={"동별":"dong_name"})
    # 주민 총수는 비율 원형 검증을 위해 resident 원본에서 별도 계산하지 않고, 아래 helper가 반환한 임시 total을 사용하지 않음.
    return x

def welfare_features(path: Path) -> pd.DataFrame:
    raw=pd.read_excel(path,header=None); x=raw.iloc[3:,[0,1,2,4]].copy(); x.columns=["area","qualification","age","count"]; x[["area","qualification"]]=x[["area","qualification"]].ffill(); x["count"]=pd.to_numeric(x["count"],errors="coerce")
    # 같은 동명이 다른 자치구에도 있으므로, 노트북처럼 강남구 블록 안에서만 집계한다.
    start=x.index[x.area.eq("강남구")].min()
    after=x.loc[start:]; next_district=after.index[(after.area.astype(str).str.endswith("구")) & (~after.area.eq("강남구"))].min()
    x=x.loc[start:next_district-1]
    gangnam_dongs={"신사동","논현1동","논현2동","압구정동","청담동","삼성1동","삼성2동","대치1동","대치2동","대치4동","역삼1동","역삼2동","도곡1동","도곡2동","개포1동","개포2동","개포3동","개포4동","세곡동","일원본동","일원1동","수서동"}
    dongs=x[x.area.isin(gangnam_dongs) & x.qualification.eq("기초생계급여")]
    return dongs.groupby("area",as_index=False)["count"].sum().rename(columns={"area":"dong_name","count":"livelihood_count"})

def preprocess_raw_dir(raw_dir: str|Path) -> tuple[pd.DataFrame,pd.DataFrame,dict]:
    raw=Path(raw_dir)
    skt=skt_features(read_csv(_file(raw,"gangnam_db1_features")))
    resident=resident_features(read_csv(_file(raw,"등록인구")))
    household=household_features(read_csv(_file(raw,"세대원수별")))
    disability=disability_features(read_csv(_file(raw,"장애인 현황(장애유형별")),resident)
    welfare=welfare_features(_file(raw,"국민기초생활 수급자 동별 현황"))
    # 총인구는 resident 원본에서 Q3/Q4 평균으로 재생성해 장애·복지 분모로 쓴다.
    rdf=read_csv(_file(raw,"등록인구")); rr=rdf[(rdf["동별(1)"].eq("강남구")) & (rdf["동별(2)"]!="소계") & (rdf["항목"].eq("계"))].copy(); rr["resident_total"]=(pd.to_numeric(rr.iloc[:,3],errors="coerce")+pd.to_numeric(rr.iloc[:,25],errors="coerce"))/2; totals=rr[["동별(2)","resident_total"]].rename(columns={"동별(2)":"dong_name"})
    base=skt.merge(resident,on="dong_name",validate="one_to_one").merge(household,on="dong_name",validate="one_to_one").merge(totals,on="dong_name",validate="one_to_one").merge(disability,on="dong_name",validate="one_to_one").merge(welfare,on="dong_name",validate="one_to_one")
    base["disability_ratio"]=base.v/base.resident_total; base["livelihood_recipient_ratio"]=base.livelihood_count/base.resident_total
    base=base.drop(columns=["resident_total","v","livelihood_count"]).sort_values("adm_cd")
    if base.adm_cd.nunique()!=22 or base.isna().any().any(): raise PreprocessError(f"[판단 보류] 22개 동/결측 검증 실패: 동={base.adm_cd.nunique()}, 결측={int(base.isna().sum().sum())}")
    profile=base.copy(); report={"status":"PASS","rows":len(base),"unit":"강남구 행정동 1행","period":"2025H2 구조자료","requires_human_review":False,"rule_version":"analysis1-raw-adapter-v1","note":"지역 유형 맥락용 전처리이며 사회적 고립 위험 점수가 아님"}
    return base,profile,report

def preprocess_from_frames(frames: dict[str,pd.DataFrame]):
    """향후 API 어댑터는 API 응답을 이 frames 구조로 변환해 같은 전처리 함수를 호출한다."""
    raise NotImplementedError("현재 제공 원천자료는 파일별 다중 헤더 구조입니다. API별 응답 스키마 확정 후 이 함수에 source adapter를 추가하세요.")

def save(base:pd.DataFrame, profile:pd.DataFrame, report:dict, output:Path):
    output.mkdir(parents=True,exist_ok=True); base.to_csv(output/'analysis1_input.csv',index=False,encoding='utf-8-sig'); profile.to_csv(output/'analysis1_profile.csv',index=False,encoding='utf-8-sig'); (output/'pca_columns.json').write_text(json.dumps(PCA_MAPPING,ensure_ascii=False,indent=2),encoding='utf-8'); (output/'preprocessing_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
