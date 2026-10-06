"""동·월별 탐지 결과와 공식 2025년 사업 계획의 연결 근거를 전수 기록한다.

실행: python -m dashboard.tools.recommendation_audit
"""
import json
from collections import Counter
from pathlib import Path

import streamlit as st

from dashboard.tools.detection_data import METRICS, load_detection_rows
from dashboard.tools.policy_data import POLICY_FILE, load_policy_plans


AUDIT_FILE = Path(__file__).resolve().parents[1] / "data" / "policy_recommendation_audit_2025.json"
SUMMARY_FILE = Path(__file__).resolve().parents[1] / "data" / "policy_recommendation_audit_2025.md"


def decision(row: dict, plan: dict) -> dict:
    month = int(row["month"][-2:])
    reasons = []
    if row["stage"] == "조건 미충족":
        reasons.append("소통·평일·휴일 외출·결합 지표의 동시 악화 기준 미충족")
    if plan["dong"] and plan["dong"] != row["dong"]:
        reasons.append(f"지역 범위 불일치: {plan['dong']} 중심 사업")
    if not plan["fromMonth"] <= month <= plan["throughMonth"]:
        reasons.append(f"계획기간 밖: {plan['planPeriod']}")
    if not row["comm"]:
        reasons.append("소통 적음 비율 증가와 통화대상자 수 감소가 함께 나타나지 않음")
    if plan["signal"] == "소통·외출" and not row["outing"]:
        reasons.append("평일·휴일 외출 적음 비율 증가와 이동 횟수 감소가 함께 나타나지 않음")
    matched = not reasons
    return {
        "month": row["month"], "dongCode": row["dongCode"], "dong": row["dong"],
        "stage": row["stage"], "planName": plan["name"], "matched": matched,
        "reasons": ["동·월 변화 신호, 사업 지역, 계획기간 일치"] if matched else reasons,
        "sourceFile": plan["sourceFile"], "sourcePage": plan["sourcePage"],
        "planPeriod": plan["planPeriod"],
        "caution": "2025년 12월에는 21개 동의 통화·이동 감소가 공통으로 나타남; 원인 확인 필요" if month == 12 else "",
    }


def build_audit(detection: dict, plans: list[dict]) -> dict:
    rows = detection["rows"]
    if len(rows) != 252 or len(plans) != 3:
        raise ValueError("검토표는 2025년 21개 동 × 12개월 × 연결 가능한 사업 3개를 대상으로 합니다.")
    decisions = [decision(row, plan) for row in rows for plan in plans]
    if len({(d["month"], d["dongCode"], d["planName"]) for d in decisions}) != 756:
        raise ValueError("동·월·사업 조합이 누락되거나 중복되었습니다.")
    return {
        "scope": "2025년 21개 동 × 12개월 × 공식 계획사업 3개",
        "source": detection["source"],
        "method": "탐지 단계, 소통·외출 변화, 계획 지역·기간의 규칙 대조; 개인 자격·운영 여부·사업 효과 판단 제외",
        "decisions": decisions,
    }


@st.cache_data(show_spinner=False)
def load_recommendation_audit(path: str, modified_ns: int) -> dict:
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    decisions = result["decisions"]
    if len(decisions) != 756 or len({(d["month"], d["dongCode"], d["planName"]) for d in decisions}) != 756:
        raise ValueError("사업 연결 검토표는 756개 고유 판정이어야 합니다.")
    return result


def write_summary(audit: dict, output: Path) -> None:
    decisions = audit["decisions"]
    matched = [d for d in decisions if d["matched"]]
    by_plan = Counter(d["planName"] for d in matched)
    by_month = Counter(d["month"] for d in matched)
    signals = sorted({(d["month"], d["dong"], d["stage"]) for d in decisions if d["stage"] != "조건 미충족"})
    lines = [
        "# 2025년 동·월별 지원사업 연결 전수 검토",
        "",
        "- 범위: 21개 동 × 12개월 = 252개 탐지 결과; 연결 가능한 계획사업 3개에 대해 756개 판정",
        f"- 탐지 조건 충족: {len(signals)}개 동·월; 사업 검토 후보 판정: {len(matched)}건",
        "- 후보는 지역·기간·변화 신호가 맞는 **공식 2025년 계획사업**입니다. 실제 운영, 개인 자격, 신청 가능 여부, 효과를 뜻하지 않습니다.",
        "- 개포3동은 원자료 0값 검토 전 제외했습니다. 2026년 보도자료는 포함하지 않았습니다.",
        "- 2025년 12월은 21개 동에서 통화·이동 감소가 공통으로 나타나 원인 확인이 필요합니다.",
        "",
        "## 사업별 후보 판정",
        "",
        "| 사업 | 후보 동·월 건수 | 근거 문서 |",
        "|---|---:|---|",
    ]
    for plan in sorted({d["planName"] for d in decisions}):
        one = next(d for d in decisions if d["planName"] == plan)
        lines.append(f"| {plan} | {by_plan[plan]} | {one['sourceFile']} · {one['sourcePage']}쪽 |")
    lines += ["", "## 월별 후보 판정", "", "| 월 | 후보 건수 |", "|---|---:|"]
    for month in sorted({d["month"] for d in decisions}):
        lines.append(f"| {month} | {by_month[month]} |")
    lines += ["", "## 탐지 조건을 충족한 동·월", "", "| 월 | 동 | 탐지 단계 | 사업 후보 |", "|---|---|---|---|"]
    for month, dong, stage in signals:
        names = [d["planName"] for d in matched if d["month"] == month and d["dong"] == dong]
        lines.append(f"| {month} | {dong} | {stage} | {', '.join(names) or '없음'} |")
    lines += [
        "", "## 판정 해석", "",
        "전체 756건의 후보·제외 이유는 같은 이름의 JSON 파일에 있습니다. 제외 사유에는 탐지 기준, 동 범위, 계획기간, 소통·외출 신호를 각각 기록했습니다.",
        "2025년 동·월별 결과보고 실적은 아직 확보되지 않아 추천 적합성이나 탐지 정확도를 평가할 수 없습니다.",
        "",
    ]
    output.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    detection = load_detection_rows(str(METRICS), METRICS.stat().st_mtime_ns)
    plans = load_policy_plans(str(POLICY_FILE), POLICY_FILE.stat().st_mtime_ns)
    audit = build_audit(detection, plans)
    AUDIT_FILE.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary(audit, SUMMARY_FILE)
    print(f"{len(audit['decisions'])}개 사업 판정 완료")
