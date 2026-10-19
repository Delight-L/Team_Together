"""복지사업 에이전트: 팀 자료에서 사업을 찾아 안내하거나 신규 사업 기획 아이디어를 제안합니다.

흐름
1. DB2 문서·API·공고를 검색하고, 서명된 후속 질문은 대화 당시 근거를 유지합니다.
2. sources 이벤트로 찾은 사업을 먼저 보냅니다.
3. AI 꺼짐 → 자료 안내. AI 켬 → 전체 생성 후 사업별 근거·자격·출력 규제를 검사하고 전달합니다.
4. AI 실패 → 자료 기반 답변으로 대체합니다.

done은 보내지 않습니다(파이프라인이 한 번만 보냅니다).
"""
import json
import asyncio
import math
import re
from collections.abc import AsyncIterator
from typing import Iterator

from backend.bomi import aio, events
from backend.bomi.agents.base import RegulatedAgent
from backend.bomi.agents.welfare_prompt import SYSTEM
from backend.bomi.events import Event
from backend.bomi.phrases import BLOCKED_MODE, OUTPUT_BLOCKED
from backend.bomi.regularization import Policy
from backend.bomi.request import ChatRequest
from backend.chatbot.welfare.app.dialogue.resources import compact, local_answer, source_footer
from backend.chatbot.welfare.app.dialogue import retrieval
from backend.chatbot.welfare.app.dialogue.evidence import validate_answer
from backend.chatbot.welfare.app.dialogue.presentation import answer_material, contains_internal_metadata
from backend.chatbot.welfare.app.dialogue.query_rules import excludes_past
from backend.chatbot.welfare.app.llm.client import LLM_ERRORS, EmptyAnswer, llm
from backend.db import region_workspace

HISTORY_FOR_AI = 20
PLANNING_LABEL = '신규 사업 기획 아이디어 · 현재 운영 중인 사업이 아님\n\n'
PLANNING_NEEDS_AI = ('신규 사업 기획 아이디어를 작성하려면 AI 대화 기능이 필요합니다. '
                     '현재는 저장된 기존 사업 조회만 가능합니다. AI 대화를 켠 뒤 다시 요청해 주세요.')
PLANNING_AI_FAILED = 'AI 연결 문제로 신규 사업 기획안을 완성하지 못했습니다. 잠시 후 다시 요청해 주세요.'
AI_ERROR_NOTICE = 'AI 응답을 완료하지 못해 자료 검색 안내로 전환했습니다. 관리자 AI 설정과 연결을 확인해 주세요.'
ELIGIBILITY_MODE = '자료 기반 · 현재 자격 확인 필요'
ELIGIBILITY_NOTICE = '현재 자격이 미확인인 사업의 신청 가능·불가 단정은 자료 기반 확인 안내로 바꿨어요.'
ELIGIBILITY_DECISIONS = ('신청할수없', '신청하실수없', '신청할수있', '신청하실수있', '신청가능합니다',
                         '신청가능해요', '현재모집중입니다', '현재접수중입니다', '상시모집입니다',
                         '신청불가', '신청불가능', '신청대상입니다', '자격이있습니다', '자격이없습니다')
REVIEW_ACTION_LABEL = '사업 매칭 검토에서 검토하기'
PLANNING_REQUEST = re.compile(
    r'기존(?:의)?(?:복지)?사업(?:말고|대신|이아닌)|'
    r'(?:새로운|새|신규)(?:복지)?(?:사업|프로그램).*(?:구상|기획|아이디어|설계|추천|제안)|'
    r'(?:사업|프로그램).*(?:구상|기획|아이디어|설계)')


def is_planning_request(question: str) -> bool:
    return bool(PLANNING_REQUEST.search(re.sub(r'\s+', '', question)))


def _is_followup(question: str) -> bool:
    short = re.sub(r'\s+', '', question).strip('?!？.!')
    return retrieval.is_followup(short)


def search_question(messages: list[dict]) -> str:
    """새 주제는 독립 검색하고 후속 질문(«대상은?»)에서는 원래 사업 맥락을 유지합니다."""
    asked = [m['content'] for m in messages if m['role'] == 'user']
    query = asked[-1]
    if _is_followup(query):
        anchor = next((q for q in reversed(asked[:-1]) if not _is_followup(q)), '')
        if anchor:
            query = anchor + ' ' + query
    return query[-3000:]


def unverified_eligibility_answer(question: str, answer: str, records: list[dict]) -> str | None:
    """미검토 자격에 대한 확정 답변(«신청할 수 없습니다» 등)은 원문 대상·기관 확인 안내로 바꿉니다. 필요 없으면 None."""
    if not records or all(r.get('eligibility_reviewed') for r in records):
        return None
    if not any(phrase in compact(answer) for phrase in ELIGIBILITY_DECISIONS):
        return None
    lines = ['현재 이용 자격과 접수 여부가 확인되지 않아 이 자료만으로 신청 가능·불가를 확정할 수 없습니다.']
    for record in records:
        lines.append(f'{record["name"]}의 자료상 대상: {record["target"]}\n확인할 기관: {record["agency"]}')
    lines.append('거주 지역과 대상 조건, 현재 운영 여부를 담당 기관에 확인해 주세요.')
    return '\n\n'.join(lines) + source_footer(records)


def review_key(record: dict) -> str | None:
    """챗봇 자료 id(db:[...])를 사업 매칭 검토의 service key(mission_store.service_key)로 바꿉니다. 팀 문서는 None."""
    if not str(record.get('id', '')).startswith('db:'):
        return None
    try:
        parts = json.loads(record['id'][3:])
    except ValueError:
        return None
    if parts[0] == 'api' and len(parts) == 2:
        return json.dumps(['local_welfare_api', parts[1]], ensure_ascii=False)
    if parts[0] in ('service', 'session') and len(parts) >= 4:
        return json.dumps(parts[1:4], ensure_ascii=False)
    return None


def review_action(records: list[dict], context: dict) -> dict | None:
    """답변에 든 선택 지역 사업을 사업 매칭 검토 탭으로 넘기는 버튼. 넘길 사업이 없으면 None.

    다른 지역 참고 사례·종료된 사업은 검토 후보가 아니므로 넘기지 않습니다.
    """
    names = {}
    for record in records:
        key = None if record.get('reference_only') or record.get('expired') else review_key(record)
        if key and key not in names:
            names[key] = record['name']
    if not names:
        return None
    scope = {key: context[key] for key in ('city', 'district', 'month') if context.get(key)}
    return {'label': REVIEW_ACTION_LABEL, 'view': 'services', 'serviceKeys': list(names),
            'serviceNames': names, 'context': scope}


def signal_summary(request: ChatRequest) -> dict | None:
    """신규 사업 구상이 이 동의 분석 근거를 반영하도록 넘기는 위험 신호 요약. 분석 결과가 없으면 None."""
    if not request.district:
        return None
    found = region_workspace.region_status(request.data, request.city, request.month, request.district)
    if not found['rows']:
        return None
    signals = []
    for row in found['rows']:
        if not row.get('is_risk_signal'):
            continue
        change = row.get('change_pct')
        finite = isinstance(change, (int, float)) and math.isfinite(change)
        signals.append({'지표': row.get('metric_label'), '전월_변화율': f'{change:+.1f}%' if finite else '계산 불가'})
    summary = {'범위': f'{request.district} 동 전체 · {request.month}', '판정': found['status'],
               '후보_지표': signals[:5], '후보_지표_수': len(signals),
               '해석_제한': '지역 집계의 변화이며 개인의 고립 여부나 변화 원인을 확정하지 않음'}
    if request.group:
        summary['선택_그룹'] = f'{request.group.age} · {request.group.sex} (위 지표는 그룹이 아닌 동 전체 값)'
    return summary


class WelfareAgent(RegulatedAgent):
    id = 'welfare'
    # 답변은 AI가 쓰므로 근거에 없는 연락처·URL·금액을 가리고(규칙), 끝에서 moderate API로 한 번 더 검사합니다.
    policy = Policy(blocked_words=True, moderate_input=True, redact_unverified=True, moderate_output=True)

    def answer(self, request: ChatRequest) -> Iterator[Event]:
        context = request.public_context()
        analysis = signal_summary(request) if request.use_ai else None
        if analysis:
            context['analysis'] = analysis
        conversation = self._converse(list(request.messages), context, request.use_ai,
                                      state=request.welfare_state, prefetched=request.retrieval)
        if is_planning_request(request.messages[-1]['content']):
            return aio.iterate(conversation)
        return aio.iterate(self._with_review_action(conversation, context))

    async def _with_review_action(self, inner: AsyncIterator[Event], context: dict) -> AsyncIterator[Event]:
        """기존 답변을 그대로 보낸 뒤, 안내한 사업을 사업 매칭 검토 탭으로 넘기는 버튼을 붙입니다(차단된 답변 제외)."""
        records, blocked = [], False
        try:
            async for name, payload in inner:
                if name == events.SOURCES:
                    records = payload['records']
                elif name == events.REPLACE:
                    blocked = payload.get('mode') == BLOCKED_MODE
                yield name, payload
        finally:
            await inner.aclose()
        action = None if blocked else review_action(records, context)
        if action:
            yield events.actions([action])

    async def _converse(self, messages: list[dict], context: dict, use_ai: bool,
                        *, state=None, prefetched=None) -> AsyncIterator[Event]:
        question = messages[-1]['content']
        planning = is_planning_request(question)
        state, prefetched = state or {}, prefetched or {}
        query = search_question(messages)
        if _is_followup(question) and state.get('records') and not excludes_past(question):
            query = (state.get('anchor', '') + ' ' + question)[-3000:]
            found = {'records': state['records'], 'mode': 'conversation_snapshot'}
        elif use_ai and prefetched.get('query') == query:
            found = prefetched
        else:
            found = await retrieval.retrieve(query, city=context.get('city', ''),
                district=context.get('district', ''), use_ai=use_ai, planning=planning)
        records, mode = found['records'], found['mode']
        yield events.sources(records, 'AI 대화' if use_ai else '자료 검색 · AI 사용 안 함',
                             retrieval=mode, query=query)
        if 'partial' in mode:
            yield events.notice('일부 지역 자료는 의미 검색 색인이 없어 키워드 검색으로 보완했습니다.')
        if 'unavailable' in mode or 'missing' in mode:
            yield events.notice('의미 검색 또는 재정렬을 완료하지 못해 사용 가능한 검색 결과로 답합니다.')
        if not use_ai:
            yield events.token(PLANNING_NEEDS_AI if planning else local_answer(records))
            return
        inner = self._ask_ai(messages, context, records, planning)
        try:
            async for event in inner:
                yield event
        finally:
            await inner.aclose()  # 받는 쪽이 멈추면 AI 스트림도 함께 닫습니다.

    async def _ask_ai(self, messages, context, records, planning) -> AsyncIterator[Event]:
        material = {'context': context, 'records': records}
        material_text = json.dumps(material, ensure_ascii=False)
        prompt = (SYSTEM + '\n선택 지역은 검색 맥락이며 자격 보장이 아닙니다. 기준월은 분석 기준으로 사업 운영 시점과 다릅니다.'
                  '\n검색된 팀 자료:\n' + json.dumps(answer_material(context, records), ensure_ascii=False))
        ai_messages = [{'role': 'system', 'content': prompt}, *messages[-HISTORY_FOR_AI:]]
        if planning:
            yield events.token(PLANNING_LABEL)
        tokens = llm.stream(ai_messages)
        parts = []
        try:
            # 근거 검사와 출력 규제가 끝나기 전에는 AI 원문을 화면에 보내지 않습니다.
            async with asyncio.timeout(45):
                async for text in tokens:
                    parts.append(text)
            if not parts:
                raise EmptyAnswer('빈 AI 응답')
            if await self.regulator.output_flagged_async(''.join(parts), self.policy, generated_by_ai=True):
                yield events.replace(OUTPUT_BLOCKED, BLOCKED_MODE, '')
                return
            if not planning and contains_internal_metadata(''.join(parts), records):
                yield events.replace(local_answer(records), '자료 기반 · 확인 상태 안내')
                yield events.notice('자료의 확인 상태를 알기 쉬운 안내로 정리했어요.')
                return
            # 기존 사업 조회: 미확인 자격을 단정한 답은 확인 안내로 바꾸고, 아니면 출처·확인 상태를 붙입니다.
            # 신규 사업 구상안에는 붙이지 않습니다(기획안이 실제 사업 출처를 가진 것처럼 보이지 않게).
            correction = None if planning else unverified_eligibility_answer(messages[-1]['content'], ''.join(parts), records)
            if correction:
                yield events.replace(correction, ELIGIBILITY_MODE)
                yield events.notice(ELIGIBILITY_NOTICE)
            else:
                answer, hidden = (self.regulator.redact(''.join(parts), material_text, self.policy)
                                  if planning else validate_answer(''.join(parts), records))
                if not planning:
                    answer += source_footer(records)
                yield events.token(answer)
                if hidden:
                    yield events.notice('해당 사업 자료에서 확인되지 않은 ' + '·'.join(hidden)
                                        + '을 가렸어요. 기관 확인이 필요합니다.')
        except (*LLM_ERRORS, TimeoutError):
            yield events.error(AI_ERROR_NOTICE)
            yield events.replace(PLANNING_AI_FAILED if planning else local_answer(records), '자료 검색 · AI 연결 실패')
        finally:
            await tokens.aclose()
