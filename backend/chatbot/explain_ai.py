"""분석 근거를 AI에게 설명받는 공통 절차(동 분석·그룹 분석이 함께 씁니다).

1. AI 연결 설정과 대화 이력 형식을 검사합니다.
2. 근거 자료를 담은 지시문(prompt)과 대화를 AI에게 보내 답을 받습니다.
3. 답에 근거 자료에 없는 연락처·URL·금액이 있으면 가립니다(chatbot/guardrails.py).
"""
import asyncio

from backend.chatbot.guardrails import redact_unverified
from backend.chatbot.welfare.app.llm.client import AIUnavailable, EmptyAnswer, ai_ready, llm


def clean_history(history):
    """이전 대화를 최근 8개, 메시지당 4,000자 이하의 user/assistant 메시지로 검사합니다."""
    if not isinstance(history, list) or len(history) > 8:
        raise ValueError('대화 이력은 최근 8개까지 전달하세요.')
    cleaned = []
    for item in history:
        if not isinstance(item, dict) or item.get('role') not in {'user', 'assistant'}:
            raise ValueError('대화 형식이 올바르지 않습니다.')
        content = str(item.get('content', ''))
        if len(content) > 4000:
            raise ValueError('이전 대화가 너무 깁니다.')
        cleaned.append({'role': item['role'], 'content': content})
    return cleaned


async def _collect(messages):
    parts = []
    async for token in llm.stream(messages):
        parts.append(token)
    return ''.join(parts)


def ask_with_evidence(prompt, question, history):
    """(답변, 가린 정보 종류 목록)을 돌려줍니다. AI를 쓸 수 없거나 실패하면 LLM_ERRORS 중 하나가 납니다."""
    if not ai_ready():
        raise AIUnavailable('관리자 AI 설정이 꺼져 있거나 API 키가 없습니다.')
    messages = [{'role': 'system', 'content': prompt}, *clean_history(history),
                {'role': 'user', 'content': str(question).strip()}]
    answer = asyncio.run(_collect(messages))
    if not answer.strip():
        raise EmptyAnswer('AI 답변이 비어 있습니다.')
    return redact_unverified(answer, prompt)
