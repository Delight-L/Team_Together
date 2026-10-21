"""주제 밖 대화 응답과 LLM 장애 시 보수적인 목적 분류."""

import re
from .schemas import QueryIntent

DIALOGUE_REPLIES = {
    "off_topic": "저는 지역 변화 신호와 복지 지원에 관한 질문을 도와드려요. 확인하고 싶은 지역이나 지표를 말씀해 주세요.",
    "insult": "확인하고 싶은 지역이나 지표를 말씀해 주세요.",
    "feedback": "어떤 부분이 잘못됐거나 불편했는지 알려주시면 다시 확인할게요.",
    "greeting": "안녕하세요. 어떤 지역의 변화를 확인해 드릴까요?",
    "thanks": "도움이 되었다니 다행이에요. 더 확인할 내용이 있으면 말씀해 주세요.",
}


def dialogue_intent(kind):
    return QueryIntent("dialogue", kind)


def fallback_dialogue(question, districts, memory):
    """LLM을 사용할 수 없을 때만 사용. 알 수 없는 입력을 조회로 강제하지 않는다."""
    q = question.strip()
    if re.search(r"(답변|설명|수치|계산|결과).*(틀|잘못|이상|오류|불편)|다시 확인|정정해", q):
        return dialogue_intent("feedback")
    if re.fullmatch(r"(안녕(하세요)?|반가워(요)?|하이|hello|hi)[!?.~\s]*", q, re.I):
        return dialogue_intent("greeting")
    if re.fullmatch(r"(감사(합니다|해요)?|고마워(요)?|고맙습니다|thanks)[!?.~\s]*", q, re.I):
        return dialogue_intent("thanks")
    # 정상 업무 질문에 부정적 표현이 섞인 경우 업무 조회를 유지한다.
    if any(name in q for name in districts) or re.search(
        r"지역|행정동|통신|통화|문자|이동|고립|복지|예방|신호|탐지|지표|robust|분석|계산|변화|추이|근거|전월|하반기|상반기|기간|소비|상권|카드|데이터|연령|나이|비교|[2-6]0\s*대|60\s*세|초기.?이력|처리.?상태|\d+.*동",
        q,
        re.I,
    ):
        return None
    if re.search(r"못된|멍청|바보|쓸모없|닥쳐|씨발", q):
        return dialogue_intent("insult")
    # 확정 조회 직후의 짧은 후속 질문/조건은 기존 조회 해석에 맡긴다.
    if memory.last_scope() and re.search(r"왜|그 동|위 결과|아까|다시|\d+월|202[2-5]|전부", q):
        return None
    return dialogue_intent("off_topic")
