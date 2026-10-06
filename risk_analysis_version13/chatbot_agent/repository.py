"""3단계의 정확한 CSV 조회. LLM에게 전체 집계를 맡기지 않는다."""
from __future__ import annotations
from pathlib import Path
import pandas as pd

SOURCES = {
 "detection":"Analysis2/outputs/gangnam_analysis2_detection_2022_2025.csv",
 "evidence":"Analysis2/outputs/gangnam_analysis2_evidence_card_2022_2025.csv",
 "feature":"Analysis2/gangnam_analysis2_feature_table_2022_2025.csv",
 "typology":"Analysis2/reference/gangnam_analysis1_final_region_typology_2025H2.csv",
}
class DataRepository:
 def __init__(self, root: Path): self.root=root; self._cache={}
 def _read(self, name):
  if name not in self._cache:
   path=self.root/SOURCES[name]
   if not path.is_file(): raise FileNotFoundError(f"필수 데이터가 없습니다: {path}")
   self._cache[name]=pd.read_csv(path, encoding="utf-8-sig")
  return self._cache[name].copy()
 def districts(self): return set(self._read("feature")["행정동"].dropna())
 def available_period(self):
  """LLM 해석 결과를 검증할 수 있는 실제 탐지 데이터의 월 범위."""
  dates=pd.to_datetime(self._read("detection")["date"])
  return dates.min().strftime("%Y-%m"), dates.max().strftime("%Y-%m")
 def _period(self, df, start, end):
  d=pd.to_datetime(df["date"])
  if start: df=df[d>=pd.Timestamp(start)]
  if end: df=df[pd.to_datetime(df["date"])<=pd.Timestamp(end)+pd.offsets.MonthEnd(0)]
  return df
 def signals(self, start=None,end=None,dong=None,signal="any"):
  df=self._period(self._read("detection"),start,end)
  if dong: df=df[df["행정동"]==dong]
  col={"any":"any_signal","communication":"communication_signal","mobility":"mobility_signal","combined":"combined_signal"}[signal]
  return df[df[col].astype(bool)].sort_values(["date","행정동"])
 def anomalies(self,start=None,end=None,metric=None):
  df=self._period(self._read("detection"),start,end)
  if not metric: metric="weekday_move_count"
  rz=f"{metric}_residual_change_expanding_rz"
  if rz not in df: raise ValueError("지원하지 않는 활동 지표입니다.")
  return df[df[rz].notna()].sort_values(rz).head(10), rz
 def activity(self,dong,start=None,end=None):
  df=self._period(self._read("detection"),start,end)
  return df[df["행정동"]==dong].sort_values("date")
 def evidence(self,dong,start=None,end=None):
  df=self._period(self._read("evidence"),start,end)
  return df[df["행정동"]==dong].sort_values("date")
 def context(self,dong):
  df=self._read("typology")
  return df[df["dong_name"]==dong]
