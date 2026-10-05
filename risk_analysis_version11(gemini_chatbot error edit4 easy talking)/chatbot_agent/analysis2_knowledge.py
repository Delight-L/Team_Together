from __future__ import annotations

KNOWLEDGE = {
    "통신 신호": "통화 대상자 수와 문자 대상자 수의 Robust Z-score가 각각 -2.0 이하인 경우입니다. 해당 행정동의 통신 행동이 과거 기준보다 이례적으로 낮다는 뜻이며, 사회적 고립을 확정하는 판정은 아닙니다.",
    "이동 신호": "평일 이동 횟수와 휴일 이동 횟수의 Robust Z-score가 각각 -2.0 이하인 경우입니다. 해당 행정동의 이동 행동이 과거 기준보다 이례적으로 낮다는 뜻입니다.",
    "combined": "통신 신호와 이동 신호가 같은 행정동·월에 동시에 발생한 경우입니다. 여러 행동 영역에서 같은 방향의 변화가 나타난 후보라는 뜻이지, 위험 등급이나 고립 확정 판정은 아닙니다.",
    "robust z": "Robust Z-score는 현재 변화가 해당 행정동의 과거 변화 범위에서 얼마나 이례적인지 나타냅니다. Analysis2에서는 과거 중앙값과 MAD를 사용하며, -2.0 이하는 위험 방향의 이례적 감소 신호로 봅니다.",
    "mad": "MAD는 과거 residual이 중앙값에서 얼마나 퍼져 있는지 나타내는 변동성 지표입니다. 이상치의 영향을 덜 받도록 평균·표준편차 대신 Robust Z-score 계산에 사용합니다.",
    "임계값": "운영 임계값은 Robust Z-score -2.0입니다. 사회적 고립의 공식 기준이 아니라, 이번 데이터에서 검토할 변화 신호의 민감도와 희소성을 비교해 선택한 기준입니다.",
    "공통변화": "같은 달 강남구 22개 행정동에 공통으로 나타난 변화의 중앙값을 각 동의 변화에서 빼는 과정입니다. 강남구 전체 계절·사회적 변화와 특정 동의 상대적 변화를 구분하기 위한 절차입니다.",
    "new": "New는 해당 월에 신호가 탐지됐지만 직전 월에는 신호가 없었던 상태입니다.",
    "continuing": "Continuing은 직전 월에도 신호가 있었던 상태입니다. 최근 3개월 평균의 기간이 겹칠 수 있으므로 자동으로 위험 악화나 독립 사건의 반복을 뜻하지 않습니다.",
}

CALCULATION_GUIDE = """1) 월별·행정동별 통신 및 이동 지표를 집계합니다.
2) 같은 달 강남구 전체의 공통 변화를 제거해 행정동 고유 변화를 계산합니다.
3) 기준기간의 중앙값과 MAD로 Robust Z를 계산합니다.
4) Robust Z가 -2.0 이하인지 통신·이동 조건별로 검사합니다.
5) 두 영역의 조건이 같은 행정동·월에 함께 성립하면 combined 신호로 기록합니다.
6) 결과는 사회적 고립의 확정 판정이 아니라 추가 확인이 필요한 이상 신호입니다."""


def answer_methodology(question: str) -> str | None:
    q = question.lower()
    keys = [key for key in KNOWLEDGE if key in q]
    if not keys:
        return None
    return "\n\n".join(f"{key}: {KNOWLEDGE[key]}" for key in keys) + "\n\n근거: Analysis2/DB1_Analysis2_Report.md, Analysis2/common/config.py, Analysis2/analysis/analysis2.py"
