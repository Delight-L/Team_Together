"""4단계 챗봇 오케스트레이터. 단계 구현은 각각의 전용 모듈에 둔다."""
from __future__ import annotations
from pathlib import Path
from dataclasses import replace
from .schemas import AnswerResult, Evidence
from .guardrails import validate_input, OUT_OF_SCOPE
from .intent_parser import parse_intent, looks_like_reason_followup
from .repository import DataRepository
from .query_service import execute
from .knowledge_retriever import retrieve
from .explanation_retriever import retrieve_explanation
from .answer_generator import template_answer, try_gemini
from .answer_validator import validate_answer
from .conversation_memory import ConversationMemory
from .llm_intent_resolver import IntentResolver
from .query_planner import complete_and_validate

class Chatbot:
 def __init__(self, project_root: Path, model: str="gemini-2.5-flash-lite", intent_resolver=None):
  self.project_root=project_root
  self.repo=DataRepository(project_root); self.model=model
  self.memory=ConversationMemory()
  self.intent_resolver=intent_resolver or IntentResolver(project_root,model,self.repo.available_period())
 def answer(self, question: str) -> AnswerResult:
  # 1. 인풋 필터링
  guard=validate_input(question)
  if not guard.allowed: return AnswerResult(guard.message, Evidence("입력 안내",guard.message))
  # 2. 목적 체크와 메뉴 필터링
  intent=self.intent_resolver.resolve(question,self.repo.districts(),self.memory)
  # 직전 결과가 지역 목록이고 현재 질문에 동 이름이 없으면, 자연스러운
  # 후속 이유 질문으로 연결한다. LLM의 분류가 signals로 흔들려도
  # 사용자가 방금 본 세 동을 다시 묻지 않도록 대화 맥락을 보장한다.
  previous=self.memory.last_scope()
  if (previous and previous.districts and not intent.dongs and not intent.dong
      and looks_like_reason_followup(question)
      and previous.question_type in {"signals", "rank_regions"}):
   intent=replace(intent, purpose="track_change", question_type="reason",
                  dong=previous.districts[0] if len(previous.districts)==1 else None,
                  dongs=previous.districts,
                  start_month=intent.start_month or previous.start_month,
                  end_month=intent.end_month or previous.end_month,
                  signal=intent.signal if intent.signal != "any" else previous.signal,
                  needs=tuple(item for item in intent.needs if item != "행정동"),
                  use_previous_scope=True,
                  clarifying_question=None)
  start,end=self.repo.available_period()
  intent=complete_and_validate(intent,self.memory,start,end)
  if intent.needs:
   text=intent.clarifying_question or self._clarify(intent.needs, intent)
   return AnswerResult(text,Evidence("추가 조건 필요",text),self._clarification_choices(intent.needs))
  # 3. 정확한 데이터 조회 + RAG + 답변 생성
  try:
   evidence=execute(self.repo,intent)
  except (ValueError,FileNotFoundError) as exc: return AnswerResult(str(exc),Evidence("조회 안내",str(exc)))
  self.memory.add(question,intent,evidence)
  knowledge=retrieve(question,intent.question_type)
  explanation=retrieve_explanation(intent,evidence)
  text=try_gemini(question,intent,evidence,knowledge,explanation,self.model,self.project_root) or template_answer(intent,evidence,knowledge,explanation)
  # 4. 답변 필터링. 실패하면 검증된 템플릿으로 되돌린다.
  passed,_=validate_answer(text,evidence)
  if not passed: text=template_answer(intent,evidence,knowledge,explanation)
  follow=("왜 신호로 잡혔나요?","전월에도 탐지됐나요?","지역 특성을 볼까요?")
  return AnswerResult(text,evidence,follow)

 @staticmethod
 def _clarify(needs, intent):
  missing=set(needs)
  if missing == {"기간"} and intent.question_type == "activity":
   place="해당 지역" if not intent.dongs else "·".join(intent.dongs)
   return f"{place}의 어느 기간 변화를 확인할까요? 예: 2025년 하반기 또는 2025년 11월~12월"
  if missing == {"기간"}:
   return "어느 기간을 기준으로 볼까요? 예: 2025년 하반기 또는 2025년 11월~12월"
  if missing == {"지표"}:
   return "어떤 활동 지표를 볼까요? 통화 상대 수, 문자 상대 수, 평일 이동, 휴일 이동 중에서 선택해 주세요."
  labels={"행정동":"행정동", "기간":"기간", "지표":"활동 지표", "조회 목적":"확인할 내용"}
  return "정확한 조회를 위해 " + "·".join(labels.get(item,item) for item in needs) + "을 알려주세요."

 @staticmethod
 def _clarification_choices(needs):
  if tuple(needs) == ("기간",):
   return ("2025년 하반기", "2025년 11월~12월", "전체 기간")
  if tuple(needs) == ("지표",):
   return ("통화 상대 수", "문자 상대 수", "평일 이동", "휴일 이동")
  return ("행정동 선택",)
