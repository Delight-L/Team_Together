import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


DATA_FILE = Path(__file__).with_name("mock_data.json")
MODEL_NAME = "gemini-3.7-flash"


def load_mock_data() -> dict:
    with DATA_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def get_risk_result(region: str) -> dict | None:
    """현재는 가상 JSON을 조회한다. 나중에는 위험분석 에이전트 API 호출로 교체한다."""
    return load_mock_data().get("regions", {}).get(region)


def is_gemini_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def get_example_questions() -> list[str]:
    return [
        "논현1동은 왜 후보야?",
        "역삼1동 분석 결과를 보여줘",
        "Robust Z-score 2.5는 무슨 뜻이야?",
        "상대 변화량은 왜 봐야 해?",
    ]


def normalize_region_name(name: str) -> str:
    return re.sub(r"\s+", "", name)


def resolve_region(question: str) -> tuple[str | None, str | None]:
    """정확 일치 또는 한글 오타를 보정해 지역명을 찾는다.

    반환값: (실제 지역명, 보정 안내 문장). 유사도가 낮으면 자동 보정하지 않는다.
    """
    regions = list(load_mock_data().get("regions", {}))
    normalized_question = normalize_region_name(question)

    for region in regions:
        if normalize_region_name(region) in normalized_question:
            return region, None

    # '논형돈 1동'처럼 문장 안에 쓰인 동 이름 후보를 분리한다.
    candidates = re.findall(r"[가-힣]+(?:\s*\d+)?동", question)
    for candidate in candidates:
        normalized_candidate = normalize_region_name(candidate)
        scored = sorted(
            (
                SequenceMatcher(None, normalized_candidate, normalize_region_name(region)).ratio(),
                region,
            )
            for region in regions
        )
        best_score, best_region = scored[-1]
        second_score = scored[-2][0] if len(scored) > 1 else 0

        # 한두 글자 오타는 보정하되, 다른 후보와 너무 비슷하면 확인을 요청한다.
        # 첫 글자와 '동'이 같고 다른 후보보다 충분히 유사할 때만 보정한다.
        same_boundary = (
            normalized_candidate[0] == normalize_region_name(best_region)[0]
            and normalized_candidate.endswith("동")
        )
        if same_boundary and best_score >= 0.66 and best_score - second_score >= 0.15:
            return best_region, f"입력하신 **{candidate}**을(를) **{best_region}**으로 이해했습니다."

    return None, None


def explain_region(region: str, result: dict, correction_note: str | None = None) -> str:
    change = result["change_pct"]
    relative = result["relative_change_pct"]
    z_score = result["robust_z_score"]
    direction = "감소" if change < 0 else "증가"
    relative_direction = "더 큰 감소" if relative < 0 else "더 큰 증가"
    threshold = result["threshold"]

    correction = f"{correction_note}\n\n" if correction_note else ""
    return (
        correction +
        f"### {region} · {result['month']} 분석 결과\n\n"
        f"- **{result['metric']}**: 전월 대비 **{change:+.1f}%** ({direction})\n"
        f"- **전체 중앙값 대비 상대 변화량**: **{relative:+.1f}%p** ({relative_direction})\n"
        f"- **Robust Z-score**: **{z_score:.1f}**\n\n"
        f"이 지역의 Z-score는 현재 기준 **{threshold:.1f} 이상**이므로, 평소 월별 변동범위를 벗어난 "
        f"활동 변화 **확인 후보**입니다. 이는 사회적 고립을 확정하는 판정이 아니라, "
        f"담당자가 원인과 데이터 상태를 추가 확인할 신호입니다.\n\n"
        f"_데이터 기준일: {result['data_as_of']} · 현재는 시연용 가상 데이터입니다._"
    )


def deterministic_answer(question: str) -> str:
    region, correction_note = resolve_region(question)
    if region:
        return explain_region(region, get_risk_result(region), correction_note)

    normalized = question.lower().replace(" ", "")
    if "robustz" in normalized or "zscore" in normalized or "z점수" in normalized:
        return (
            "**Robust Z-score**는 한 지역의 이번 달 변화율이 그 지역의 과거 변화 패턴에서 "
            "얼마나 이례적인지를 보여주는 값입니다. 중앙값과 MAD를 사용하므로, 극단값의 영향을 "
            "덜 받습니다.\n\n"
            "- 1.5 이상: 관찰 후보\n- 2.5 이상: 기본 이상 신호\n- 3.5 이상: 강한 경고 후보\n\n"
            "현재 대시보드에서 선택한 기준값 이상이면 확인 후보로 표시합니다."
        )
    if "상대변화" in normalized or "중앙값" in normalized or "전체" in normalized:
        return (
            "**상대 변화량**은 ‘이 동의 전월 변화율 − 전체 동의 전월 변화율 중앙값’입니다.\n\n"
            "예를 들어 모든 동이 명절·계절 요인으로 함께 감소한 달이라면, 단순 감소율만으로 "
            "특정 동을 위험 후보로 보기 어렵습니다. 상대 변화량은 그중에서도 유독 크게 변한 동을 "
            "찾기 위해 사용합니다."
        )
    if "변화율" in normalized:
        return (
            "**전월 대비 변화율**은 이번 달 지표가 지난달보다 얼마나 변했는지 나타냅니다.\n\n"
            "`(이번 달 값 − 지난달 값) ÷ 지난달 값 × 100`으로 계산합니다. 다만 변화율만으로는 "
            "전체 동시 변화와 평소 변동폭을 구분하기 어려워, 상대 변화량과 Robust Z-score를 함께 봅니다."
        )
    if "자원" in normalized or "지원" in normalized:
        return "자원연결 기능은 아직 준비 중입니다. 나중에 `get_resources(region)` 함수를 자원연결 에이전트 API와 연결할 예정입니다."

    return (
        "현재는 시연용 설명 챗봇입니다. 다음처럼 질문해 보세요.\n\n"
        "- ‘논현1동은 왜 후보야?’\n"
        "- ‘Robust Z-score 2.5는 무슨 뜻이야?’\n"
        "- ‘상대 변화량은 왜 봐야 해?’"
    )


def build_data_context(region: str | None, correction_note: str | None = None) -> str:
    if not region:
        return "현재 질문에 연결된 특정 지역은 없습니다."

    result = get_risk_result(region)
    correction = f"입력 보정: {correction_note}\n" if correction_note else ""
    return (
        correction +
        f"지역: {region}\n"
        f"분석 월: {result['month']}\n"
        f"지표: {result['metric']}\n"
        f"전월 대비 변화율: {result['change_pct']:+.1f}%\n"
        f"전체 중앙값 대비 상대 변화량: {result['relative_change_pct']:+.1f}%p\n"
        f"Robust Z-score: {result['robust_z_score']:.1f}\n"
        f"현재 임계값: {result['threshold']:.1f}\n"
        f"데이터 기준일: {result['data_as_of']}\n"
        "중요: 위 데이터는 시연용 가상 데이터입니다."
    )


def answer_with_gemini(question: str, history: list[dict]) -> str:
    """LLM은 문장 이해·설명만 한다. 수치와 판정 근거는 JSON 데이터에서만 가져온다."""
    from google import genai
    from google.genai import types

    region, correction_note = resolve_region(question)
    data_context = build_data_context(region, correction_note)
    recent_history = "\n".join(
        f"{'사용자' if item['role'] == 'user' else '챗봇'}: {item['content']}"
        for item in history[-6:]
    )

    system_instruction = """당신은 공무원용 '지역 활동 변화 설명 챗봇'입니다.
사회적 고립을 확정하거나 개인을 추정하지 않습니다. 제공된 지역 집계 데이터만 근거로 설명합니다.
숫자·월·지역을 지어내지 마세요. 제공되지 않은 정보는 '현재 연결된 데이터에는 없습니다'라고 말하세요.
답변은 한국어로, 공무원이 빠르게 판단할 수 있게 3~6문장으로 명확히 작성하세요.
Robust Z-score는 평소 변화 패턴에서 얼마나 이례적인지, 상대 변화량은 전체 동시 변화를 보정하기 위한 값이라고 설명하세요.
자원 추천·개입 처방은 아직 연결되지 않았으므로 요청받으면 준비 중이라고 안내하세요."""

    prompt = (
        f"[현재 지역 분석 데이터]\n{data_context}\n\n"
        f"[최근 대화]\n{recent_history or '없음'}\n\n"
        f"[사용자 질문]\n{question}"
    )
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    prefix = f"{correction_note}\n\n" if correction_note else ""
    return prefix + (response.text or "응답을 생성하지 못했습니다. 잠시 후 다시 질문해 주세요.")


def answer_question(question: str, history: list[dict] | None = None) -> str:
    """API 키가 있으면 자유 질문을 Gemini로 설명하고, 없으면 기존 안전 답변으로 동작한다."""
    if not is_gemini_configured():
        return deterministic_answer(question)

    try:
        return answer_with_gemini(question, history or [])
    except Exception:
        return (
            "Gemini 연결에 실패해 기본 안내 모드로 답변합니다. API 키와 모델 사용 가능 여부를 확인해 주세요.\n\n"
            + deterministic_answer(question)
        )
