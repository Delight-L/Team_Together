"""3단계 목적별 데이터 조합. 질문마다 필요한 전체 결과를 코드로 만든다."""
from __future__ import annotations
from .schemas import Evidence, QueryIntent
from .repository import DataRepository, SOURCES

LABEL={"communication":"통신","mobility":"이동","combined":"통신·이동 동시","any":"전체"}
METRIC_LABEL={"call_contacts":"통화 상대 수","text_contacts":"문자 상대 수","weekday_move_count":"평일 이동 횟수","weekend_move_count":"휴일 이동 횟수"}
def _records(df, cols): return df[cols].copy().assign(date=lambda x:x["date"].astype(str).str[:7]).to_dict("records")
def execute(repo: DataRepository, intent: QueryIntent) -> Evidence:
 if intent.question_type=="rank_regions":
  df=repo.signals(intent.start_month,intent.end_month,None,intent.signal)
  limit=intent.limit or 3
  grouped=(df.groupby("행정동",as_index=False).size().rename(columns={"size":"신호 건수"})
           .sort_values(["신호 건수","행정동"],ascending=[False,True]).head(limit))
  rows=grouped.to_dict("records")
  return Evidence("신호가 많은 지역",f"{LABEL[intent.signal]} 신호 건수가 많은 동 {len(rows)}곳입니다.",rows,[SOURCES['detection']], ["건수는 개인 수나 고립 발생률이 아니라 동×월 신호 기록 수입니다."])
 if intent.question_type=="signals":
  # 새로 지정한 동이 여러 개면, 직전 조회 결과가 아니라 그 동들만 다시 조회한다.
  names=intent.dongs or ((intent.dong,) if intent.dong else ())
  if names:
   import pandas as pd
   df=pd.concat([repo.signals(intent.start_month,intent.end_month,name,intent.signal) for name in names],ignore_index=True)
  else:
   df=repo.signals(intent.start_month,intent.end_month,None,intent.signal)
  rows=_records(df,["date","행정동","signal_type"])
  return Evidence("신호가 나온 지역",f"조건에 맞는 {LABEL[intent.signal]} 신호는 {len(rows)}건입니다.",rows,[SOURCES['detection']], ["신호는 개인의 고립을 확정하지 않습니다."])
 if intent.question_type=="anomaly":
  df,rz=repo.anomalies(intent.start_month,intent.end_month,intent.metric)
  rows=_records(df,["date","행정동",rz])
  return Evidence("이례적 감소 후보",f"{METRIC_LABEL.get(intent.metric,'평일 이동 횟수')}의 Robust Z가 낮은 순으로 최대 10건을 표시합니다.",rows,[SOURCES['detection']], ["Robust Z가 낮을수록 해당 동의 과거 변화에 비해 이례적인 감소입니다."])
 if intent.question_type=="activity":
  df=repo.activity(intent.dong,intent.start_month,intent.end_month)
  cols=["date","call_contacts","text_contacts","weekday_move_count","weekend_move_count","communication_signal","mobility_signal"]
  rows=_records(df,cols)
  return Evidence(f"{intent.dong}의 활동 변화",f"조회 기간에 {len(rows)}개월의 월별 행동값을 확인했습니다.",rows,[SOURCES['detection']], ["행동값은 지역 집계이며 개인 상태를 뜻하지 않습니다."])
 if intent.question_type=="previous":
  import pandas as pd
  names=intent.dongs or ((intent.dong,) if intent.dong else ())
  df=pd.concat([repo.evidence(name,intent.start_month,intent.end_month) for name in names],ignore_index=True)
  # 전월 확인에는 탐지 여부만 전달한다. 날짜·Z값·날씨 같은 상세 근거는 제외한다.
  rows=_records(df,["date","행정동","signal_type","consecutive_signal"])
  return Evidence("전월 신호 여부",f"조건에 맞는 신호 기록은 {len(rows)}건입니다.",rows,[SOURCES['evidence']], ["전월 탐지 여부는 신호의 악화 여부를 뜻하지 않습니다."])
 if intent.question_type in {"reason","support"}:
  import pandas as pd
  names=intent.dongs or ((intent.dong,) if intent.dong else ())
  df=pd.concat([repo.evidence(name,intent.start_month,intent.end_month) for name in names],ignore_index=True)
  cols=["date","행정동","signal_type","signal_status","previous_signal_date","months_since_previous_signal","consecutive_signal","call_contacts_residual_change_expanding_rz","text_contacts_residual_change_expanding_rz","weekday_move_count_residual_change_expanding_rz","weekend_move_count_residual_change_expanding_rz","mobility_distance_support","communication_interest_support","rain_days","rainfall_mm","snow_days"]
  rows=_records(df,cols)
  title="선정 근거" if intent.question_type=="reason" else "이전 신호와 보조 근거"
  return Evidence(title,f"조건에 맞는 신호 기록은 {len(rows)}건입니다.",rows,[SOURCES['evidence']], ["전월에도 탐지됨은 최근 3개월 평균 기간의 중첩 때문에 악화를 뜻하지 않습니다.","날씨와 보조 지표는 원인을 확정하지 않습니다."])
 if intent.question_type=="context":
  names=intent.dongs or ((intent.dong,) if intent.dong else ())
  frames=[repo.context(name) for name in names]
  if not frames: raise ValueError("지역 특성을 조회할 행정동이 필요합니다.")
  import pandas as pd
  df=pd.concat(frames,ignore_index=True)
  cols=["dong_name","cluster_type","age_60_plus_ratio","hh_1_ratio","hh_2_ratio","disability_ratio","livelihood_recipient_ratio"]
  rows=df[cols].to_dict("records")
  title=(f"{names[0]}의 지역 특성" if len(names)==1 else f"{len(names)}개 동의 지역 특성")
  return Evidence(title, "2025년 하반기 지역유형과 구조적 특성을 표시합니다.",rows,[SOURCES['typology']], ["지역유형은 신호의 원인이나 위험도를 의미하지 않습니다."])
 raise ValueError("지원하지 않는 질문 유형입니다.")
