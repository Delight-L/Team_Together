"""3단계 설명 생성. 기본 템플릿은 API 없이도 정확한 답을 제공한다."""
from __future__ import annotations
import os
from .schemas import Evidence, QueryIntent
from .knowledge_retriever import retrieve
from .llm_intent_resolver import _api_key

COLUMN_NAMES={
 "date":"월", "행정동":"행정동", "signal_type":"신호 종류", "signal_status":"상태",
 "call_contacts_residual_change_expanding_rz":"통화 Robust Z", "text_contacts_residual_change_expanding_rz":"문자 Robust Z",
 "weekday_move_count_residual_change_expanding_rz":"평일 이동 Robust Z", "weekend_move_count_residual_change_expanding_rz":"휴일 이동 Robust Z",
 "previous_signal_date":"이전 신호", "months_since_previous_signal":"이전 신호 이후 개월", "consecutive_signal":"전월에도 탐지됨",
 "dong_name":"행정동", "신호 건수":"신호 건수", "cluster_type":"지역유형",
 "age_60_plus_ratio":"60세 이상 활동인구 비율", "hh_1_ratio":"1인가구 비율",
 "hh_2_ratio":"2인가구 비율", "disability_ratio":"장애인 비율",
 "livelihood_recipient_ratio":"기초생활수급자 비율",
 "rain_days":"강수일", "rainfall_mm":"강수량", "snow_days":"적설일"
}
def _format_row(row: dict) -> str:
    values=[]
    for key,value in row.items():
        if value is None or str(value).lower()=="nan": continue
        if key.endswith("_ratio") and isinstance(value,(int,float)):
            value=f"{value * 100:.1f}%"
        elif isinstance(value,float): value=round(value,3)
        values.append(f"{COLUMN_NAMES.get(key,key)}: {value}")
    return " · ".join(values)
def _value(value) -> str:
    if value is None or str(value).lower()=="nan": return "-"
    return str(round(value, 2)) if isinstance(value, float) else str(value)

def _z_meaning(value) -> str:
    if value is None or str(value).lower()=="nan": return "이번 신호의 직접 근거가 아닙니다."
    number=float(value)
    if number <= -3: return "과거 월별 변화와 비교해 매우 이례적으로 낮았습니다."
    if number <= -2: return "과거 월별 변화와 비교해 이례적으로 낮았습니다."
    return "이번 신호의 직접 근거로 해석하지 않습니다."

def _reason_answer(evidence: Evidence) -> list[str]:
    lines=[]
    for row in evidence.rows[:10]:
        signal=str(row.get("signal_type", "")).lower()
        is_mobility="mobility" in signal or "combined" in signal
        is_communication="communication" in signal or "combined" in signal
        title=f"### {row.get('행정동','해당 동')} · {row.get('date','-')} {row.get('signal_type','')} 신호"
        lines.extend([title, "", "**한 줄 결론**"])
        if is_mobility and is_communication:
            lines.append("통신과 이동 변화가 모두 과거 변화 범위보다 이례적으로 낮아 동시 신호로 분류됐습니다.")
        elif is_mobility:
            lines.append("평일과 휴일 이동 변화가 모두 과거 변화 범위보다 이례적으로 낮아 이동 신호로 분류됐습니다.")
        else:
            lines.append("통화와 문자 변화가 모두 과거 변화 범위보다 이례적으로 낮아 통신 신호로 분류됐습니다.")
        lines.extend(["", "| 확인 수치 | 쉬운 설명 |", "|---|---|"])
        if is_mobility:
            for key,label in (("weekday_move_count_residual_change_expanding_rz","평일 이동 Robust Z"),
                              ("weekend_move_count_residual_change_expanding_rz","휴일 이동 Robust Z")):
                value=row.get(key)
                lines.append(f"| {label}: **{_value(value)}** | {_z_meaning(value)} |")
            lines.append("| 이동 신호 | 평일·휴일 이동 지표가 함께 기준을 충족했습니다. |")
        if is_communication:
            for key,label in (("call_contacts_residual_change_expanding_rz","통화 Robust Z"),
                              ("text_contacts_residual_change_expanding_rz","문자 Robust Z")):
                value=row.get(key)
                lines.append(f"| {label}: **{_value(value)}** | {_z_meaning(value)} |")
            lines.append("| 통신 신호 | 통화·문자 지표가 함께 기준을 충족했습니다. |")
        for key,label in (("rain_days","강수일"),("rainfall_mm","강수량"),("snow_days","적설일")):
            value=row.get(key)
            if value is not None and str(value).lower()!="nan":
                lines.append(f"| {label}: **{_value(value)}** | 신호 판정 기준은 아니며, 당시 상황을 확인할 보조 정보입니다. |")
        lines.extend(["", "**현장 확인 방향**", "이동·통신 변화가 행사·공사·계절 요인 또는 생활권 이용 변화와 관련 있는지 확인해 볼 수 있습니다.", ""])
    return lines

def _previous_answer(evidence: Evidence) -> str:
    """전월 질문에는 사용자가 요청한 판정만 짧게 보여준다."""
    if not evidence.rows:
        return "결론: 조회 기간에 비교할 신호 기록이 없습니다."
    lines=["결론: 전월 신호 여부입니다.", ""]
    for row in evidence.rows:
        status="탐지됨" if bool(row.get("consecutive_signal")) else "미탐지"
        lines.append(f"- {row.get('행정동','해당 동')} · {row.get('date','-')} · {row.get('signal_type','신호')}: **{status}**")
    return "\n".join(lines)

def template_answer(intent: QueryIntent, evidence: Evidence, knowledge: str, explanation: str = "") -> str:
    if intent.question_type == "reason" and evidence.rows:
        return "\n".join(_reason_answer(evidence))
    if intent.question_type == "previous":
        return _previous_answer(evidence)
    lines=[f"결론: {evidence.summary}"]
    if evidence.rows:
        lines.append("\n근거:")
        lines.extend(f"- {_format_row(row)}" for row in evidence.rows[:10])
        if len(evidence.rows)>10: lines.append(f"- 총 {len(evidence.rows)}건 중 상위 10건만 표시했습니다.")
    lines.append("\n해석:")
    if intent.question_type=="reason": lines.append("통신 또는 이동의 짝 지표가 모두 기준을 통과했을 때만 신호가 됩니다. 아래 Robust Z는 그 동의 과거 변화와 비교한 값입니다.")
    elif intent.question_type=="context": lines.append("이 값은 신호를 판정하는 조건이 아니라, 신호가 발생한 지역의 평상시 구조적 배경을 이해하기 위한 정보입니다.")
    else: lines.append("분석 신호는 추가 확인이 필요한 지역 행동변화이며, 사회적 고립을 확정하는 판정은 아닙니다.")
    if knowledge:
        lines.append("\n참고: " + knowledge)
    if evidence.limitations: lines.append("\n확인 범위: " + " / ".join(evidence.limitations))
    return "\n".join(lines)
def try_gemini(question: str, intent: QueryIntent, evidence: Evidence, knowledge: str,
               explanation: str, model: str, project_root=None) -> str | None:
    key=_api_key(project_root) if project_root else os.getenv("GEMINI_API_KEY", "").strip()
    if not key: return None
    try:
        from google import genai
        prompt=f'''당신은 강남구 지역 변화 신호 설명 도우미입니다. 아래의 구조화된 조회 결과와 설명 기준에 있는 사실만 사용하세요.
개인의 사회적 고립이나 원인을 확정하지 마세요. 답은 한국어로 짧게 작성하세요.
질문이 신호 선정 이유라면 반드시 `한 줄 결론`, `| 확인 수치 | 쉬운 설명 |` 표, `현장 확인 방향` 순서로 작성하세요.
표에는 신호의 직접 판정 수치를 원값과 함께 모두 쓰고, 각각의 쉬운 뜻을 바로 옆에 붙이세요.
날씨·지역 특성은 보조 정보로 구분하고, 모든 답변에 같은 주의 문구를 반복하지 마세요.
질문이 전월 탐지 여부라면 행정동·월·신호 종류별로 `전월 신호 여부: 탐지됨` 또는
`전월 신호 여부: 미탐지`만 보여주세요. 변화율, Robust Z, 이전 신호 날짜, 날씨 등은 쓰지 마세요.
[사용자 질문]\n{question}\n[조회 조건]\n{intent}\n[조회 결과]\n{evidence.rows}\n[설명 근거]\n{knowledge}\n[제한]\n{evidence.limitations}'''
        prompt += f"\n[설명 기준 RAG]\n{explanation}"
        result=genai.Client(api_key=key).models.generate_content(model=model, contents=prompt)
        return getattr(result,"text",None)
    except Exception:
        return None
