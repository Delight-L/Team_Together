"""기존 JSON 챗봇 호출도 복지이음으로 연결하는 호환 어댑터."""
from chatbot.welfare.service import complete_reply

TOPICS = {
    'care': ('어르신 돌봄', '혼자 사는 어르신 돌봄 지원'),
    'health': ('병원 동행', '병원 동행 지원'),
    'connection': ('관계 모임', '청년 관계 모임 지원'),
    'meal': ('식생활 지원', '식생활 지원'),
}

def topic_reply(topic, evidence, context):
    if topic not in TOPICS:
        raise ValueError('유효한 대화 주제를 선택하세요.')
    # 새 화면의 예시 질문과 같은 검색·답변 경로를 사용합니다.
    return free_reply(TOPICS[topic][1], evidence, context)

def free_reply(question, evidence, context, history=None):
    messages = [{'role': m.get('role'), 'content': m.get('content', m.get('text', ''))}
                for m in (history or [])[-20:] if isinstance(m, dict)]
    messages.append({'role': 'user', 'content': question})
    return complete_reply(messages, context)
