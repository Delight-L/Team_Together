"""위험 지표 규칙과 기본 설정.

실제 CSV의 열 이름을 알고 있다면 METRIC_RULES에 직접 등록하세요.
등록하지 않은 숫자형 열은 임시로 '감소가 위험'이라고 보고 분석합니다.
결과 파일의 metric_rule_source 열로 임시 규칙 여부를 확인할 수 있습니다.
"""
from __future__ import annotations

from dataclasses import dataclass


HISTORY_WINDOW = 3
MIN_RELATIVE_CHANGE_PP = 5.0
ROBUST_Z_THRESHOLD = 2.5


@dataclass(frozen=True)
class RiskMetric:
    column: str
    label: str
    risk_direction: str  # "감소" 또는 "증가"
    direction_sign: int  # 감소=-1, 증가=1
    meaning: str
    rule_source: str = "설정"


# 제공받은 강남구 동×월 전처리 CSV의 최종 위험신호 10개.
# 감소가 위험인 활동·관계 지표는 -1, 증가가 위험인 체류·비활동 지표는 1이다.
METRIC_RULES: dict[str, RiskMetric] = {
    "flow_per_point": RiskMetric("flow_per_point", "지점당 유동량", "감소", -1, "동 내 평균 활동량"),
    "평일 총 이동 횟수": RiskMetric("평일 총 이동 횟수", "평일 이동 횟수", "감소", -1, "평일 외부 활동성"),
    "휴일 총 이동 횟수 평균": RiskMetric("휴일 총 이동 횟수 평균", "휴일 이동 횟수", "감소", -1, "주말·휴일 외부 활동성"),
    "집 추정 위치 평일 총 체류시간": RiskMetric("집 추정 위치 평일 총 체류시간", "평일 집 체류시간", "증가", 1, "평일 집 체류 증가"),
    "집 추정 위치 휴일 총 체류시간": RiskMetric("집 추정 위치 휴일 총 체류시간", "휴일 집 체류시간", "증가", 1, "휴일 집 체류 증가"),
    "평균 통화대상자 수": RiskMetric("평균 통화대상자 수", "평균 통화대상자 수", "감소", -1, "사회적 연락 대상 감소"),
    "low_weekday_outing_ratio": RiskMetric("low_weekday_outing_ratio", "평일 저외출 비율", "증가", 1, "평일 외출 저하"),
    "low_holiday_outing_ratio": RiskMetric("low_holiday_outing_ratio", "휴일 저외출 비율", "증가", 1, "휴일 외출 저하"),
    "very_low_outing_ratio": RiskMetric("very_low_outing_ratio", "매우 낮은 외출 비율", "증가", 1, "전반적 외출 저하"),
    "카카오톡_비사용비율": RiskMetric("카카오톡_비사용비율", "카카오톡 비사용 비율", "증가", 1, "디지털 소통 활동 저하"),
}

# 행정동 식별자·분석에 쓰면 안 되는 보조 수치 열. 필요하면 추가 가능.
NON_METRIC_COLUMNS = {"행정동코드", "행정동명", "기준연월", "month", "year", "cluster_k2", "cluster_k3", "cluster_k4", "cluster_k5", "cluster_k6"}
