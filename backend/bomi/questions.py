"""질문 문장을 분류하는 순수 함수와 키워드 목록. 담당 선택(routing.py)과 지역 분석 에이전트가 함께 씁니다.

부분 문자열 포함 검사이므로 오탐이 있을 수 있습니다. 새 단어를 넣을 때는 test_questions.py에 예시 질문을 함께 추가하세요.
"""
import re

from backend.agents import report_writer
from backend.bomi.phrases import WORK_GUIDES
from backend.chatbot.welfare.app.dialogue.resources import has_program_name

WELFARE_WORDS = ('사업', '지원', '서비스', '복지', '신청', '돌봄', '동행', '모임', '상담', '기관',
                 '프로그램', '도시락', '식사', '일자리', '바우처', '급여')
ANALYSIS_WORDS = ('판정', '판단', '보류', '후보', '변화', '지표', '요약', '추이', '근거', '의미', '뜻', '다음',
                  '비율', '연간', '지역 배경', '인구 기준', '독거노인 통계', '감소', '증가', '통화', '문자', '이동', '유동', '요일',
                  '시간', '그룹', '이유', '왜', '신호', '탐지', '지역', '군집', '배경', '소비', '상권', 'Robust', 'robust')
# 그룹이 열린 화면에서 그룹 분석으로 보낼 말과, 그래도 지역 변화 신호 분석으로 보낼 말(띄어쓰기 없이 비교)
GROUP_WORDS = ('이그룹', '그룹의', '유동', '성별', '남성', '여성', '시간대', '요일별', '이지표')
REGIONAL_WORDS = ('이상신호', '탐지', 'robust', '군집', '지역배경', '소비', '상권', '통화', '문자', '이동')
SURVEY_WORDS = ('사회적 연결', '사회적 연결 마음', '사회적 연결마음', '마음 지표', '마음지표', '관계망', '서울서베이', '도움받을 사람', '조언을 구할 사람', '금전적으로 도움',
                '아플 때 도움', '외로움', '가족 외 관계', '동반자 부족', '혼자 남겨짐', '사람들 사이에서 고립',
                '다른 지표', '추가 지표', '별도 문항')
TAB_WORDS = ('어느 지역을 살펴볼까요', '우리 동은 어떤 지역', '어떤 지역일까', '소비는 어떻게 달라졌', '탭에 대해', '탭 설명', '이 탭', '자체 과거 비교', '공통 변화 제거 후 비교', '두 비교 모두', '탐지 이후', '탐지월', '통신 탐지', '통신탐지', '탐지 직전 기준월', '탐지직전 기준월',
             '통신 지표 흐름', '이동 지표 흐름', '전화 연락', '문자 연락', '평일 이동', '휴일 이동', '유동량 변화', '유동량 추이', '전체 유동량', '가구 구성', '가구 구성 비율', '독거노인', '이야기할 사람이 없는 비율', '가구·관계망 함께 보기', '가구 관계망 함께 보기', '탐지 현황', '탐지현황', '조사 파일', '조사파일', '자료 확인', '자료확인', '최초 탐지월', '탐지 사례', '연령대', '어느 지역을 살펴볼까요', '지도에서 지역', '실제 활동량', '실제활동량', '실제 활동', '원값', '원값 변화', '계절성 고려', '계절성', '같은 달 비교', '과거 같은 달', '강남구 흐름 고려', '강남구흐름', '강남구 전체 흐름', '구 전체 흐름', '공통 흐름')
# 대시보드 화면의 판정·수치 용어. 지역 변화 신호 분석은 이 용어를 모르므로 화면 기준을 아는 동 분석이 설명합니다.
TAB_DETAIL_WORDS = ('지역별 변화 한눈에 살펴보기', '지역별 변화', '유효 비율', '판정 기준', '총 추정 인구', '미추정 인구', '확인 대상', '영향 기준월',
                    '전월 자료 제외', '변화량 계산 불가', '판정 가능', '미탐지')
SCREEN_TERMS = ('판정', '신규 후보', '연속 후보', '변화 후보', '판단 보류', '기준 미해당', '자료 부족', '자료 없음',
                '이력 부족', '평소 대비', '전월 변화율', '지역유형', '고활동', '청년유동', '1인가구 중심형', '2인가구', '다인가구')
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


def is_survey_metric_question(question: str) -> bool:
    """Questions about the social-connection survey cards or their extra metrics."""
    return any(word in question for word in SURVEY_WORDS)


def is_tab_question(question: str) -> bool:
    """Questions about labels and comparison methods shown in a dashboard tab."""
    compact = question.replace(' ', '')
    if not any(word in question or word.replace(' ', '') in compact for word in (*TAB_WORDS, *TAB_DETAIL_WORDS)):
        return False
    # '독거노인'·'연령대'·'계절성'처럼 흔한 말은 복지사업 찾기에도 쓰입니다.
    # 탭을 직접 묻지 않으면서 사업·지원을 찾는 질문(예: "독거노인 돌봄 사업 찾아줘")은 복지사업 담당이 답합니다.
    return '탭' in question or not any(word in question for word in WELFARE_WORDS)


def program_name_hit(question: str, city: str = '') -> bool:
    """질문의 낱말(동의어 포함)이 팀 자료의 사업 이름에 들어 있는지. 설명문에만 있는 흔한 말은 보지 않습니다."""
    return has_program_name(question, city=city)


def mentions_district(question: str) -> bool:
    return bool(DISTRICT_NAME.search(question))


def is_screen_summary(question: str) -> bool:
    """현재 화면에 대한 요약·정리·설명 요청."""
    return bool(re.search(r'(?:화면|대시보드|지금\s*보는|현재\s*보는).*(?:요약|정리|설명)|(?:요약|정리|설명).*(?:화면|대시보드)', question))


def is_period_expansion(question: str) -> bool:
    """직전 분석의 기간을 넓히는 짧은 후속 질문인지 판별한다."""
    return bool(re.search(r'(?:20\d{2}\s*년(?:도)?|전체\s*(?:기간|연도)|전\s*(?:기간|연도)).*(?:확대|넓혀|넓혀서|전체|전부)|(?:확대|넓혀|넓혀서).*(?:20\d{2}\s*년(?:도)?|전체\s*(?:기간|연도)|전\s*(?:기간|연도))', question))
