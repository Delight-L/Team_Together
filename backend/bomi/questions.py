"""질문 문장을 분류하는 순수 함수와 키워드 목록. 담당 선택(routing.py)과 지역 분석 에이전트가 함께 씁니다.

부분 문자열 포함 검사이므로 오탐이 있을 수 있습니다. 새 단어를 넣을 때는 test_questions.py에 예시 질문을 함께 추가하세요.
"""
import re

from backend.agents import report_writer
from backend.bomi.phrases import WORK_GUIDES
from backend.chatbot.welfare.app.dialogue.resources import COVERED_CITIES, SYNONYM_GROUPS, load_resources

WELFARE_WORDS = ('사업', '지원', '서비스', '복지', '신청', '돌봄', '동행', '모임', '상담', '기관',
                 '프로그램', '도시락', '식사', '일자리', '바우처', '급여')
ANALYSIS_WORDS = ('판정', '판단', '보류', '후보', '변화', '지표', '요약', '추이', '근거', '의미', '뜻', '다음',
                  '비율', '연간', '지역 배경', '인구 기준', '독거노인 통계', '감소', '증가', '통화', '문자', '이동', '유동', '요일',
                  '시간', '그룹', '이유', '왜', '신호', '탐지', '지역', '군집', '배경', '소비', '상권', 'Robust', 'robust')
# 그룹이 열린 화면에서 그룹 분석으로 보낼 말과, 그래도 지역 변화 신호 분석으로 보낼 말(띄어쓰기 없이 비교)
GROUP_WORDS = ('이그룹', '그룹의', '유동', '성별', '남성', '여성', '시간대', '요일별', '이지표')
REGIONAL_WORDS = ('이상신호', '탐지', 'robust', '군집', '지역배경', '소비', '상권', '통화', '문자', '이동')
# 대시보드 화면의 판정·수치 용어. 지역 변화 신호 분석은 이 용어를 모르므로 화면 기준을 아는 동 분석이 설명합니다.
SCREEN_TERMS = ('판정', '신규 후보', '연속 후보', '변화 후보', '판단 보류', '기준 미해당', '자료 부족', '자료 없음',
                '이력 부족', '평소 대비', '전월 변화율')
MEANING_WORDS = ('뜻', '의미', '차이', '다른', '다르', '무엇', '뭐', '뭔', '설명')
# 이 말이 있으면 탐지 기준·공식 질문입니다(예: "이상신호 판정 기준은?").
METHOD_WORDS = ('이상신호', '탐지', 'robust', '공식')
# "삼성1동은?", "역삼동 어때"처럼 동 이름만 넣은 질문. "세곡동행"처럼 낱말 중간의 '동'은 제외합니다.
DISTRICT_NAME = re.compile(r'[가-힣]\d?동(?=$|[\s?!.,]|[은는이가의에도과와랑만](?![가-힣]))')


def is_report_request(question: str) -> bool:
    """«보고서 초안 만들어 줘»처럼 보고서를 쓰거나 다듬어 달라는 요청."""
    return report_writer.is_draft_request(question)


def work_guide(question: str) -> str | None:
    """업무 방법 질문이면 정해진 답을, 아니면 None을 돌려줍니다."""
    for words, required, answer in WORK_GUIDES:
        if any(word in question for word in words) and (not required or any(word in question for word in required)):
            return answer
    return None


def is_screen_term_question(question: str) -> bool:
    """«자료 부족과 기준 미해당은 어떻게 다른가요?»처럼 화면 판정·수치 용어의 뜻을 묻는 질문인지."""
    if any(word in question.lower() for word in METHOD_WORDS):
        return False
    return any(term in question for term in SCREEN_TERMS) and any(word in question for word in MEANING_WORDS)


def is_group_focused(question: str) -> bool:
    """그룹 화면에서, 열린 그룹 자체를 묻는 질문인지(동 단위 이상신호·소비 질문은 제외)."""
    compact = question.replace(' ', '')
    focused = compact in {'요약', '변화요약'} or any(word in compact for word in GROUP_WORDS)
    return focused and not any(word in compact.lower() for word in REGIONAL_WORDS)


def program_name_hit(question: str, city: str = '') -> bool:
    """질문의 낱말(동의어 포함)이 팀 자료의 사업 이름에 들어 있는지. 설명문에만 있는 흔한 말은 보지 않습니다."""
    if city and city not in COVERED_CITIES:
        return False
    terms = set(re.findall(r'[가-힣a-zA-Z0-9]{2,}', question))
    for group in SYNONYM_GROUPS:
        if any(word in question for word in group):
            terms.update(group)
    return any(term in record['name'] for record in load_resources() for term in terms)


def mentions_district(question: str) -> bool:
    return bool(DISTRICT_NAME.search(question))
