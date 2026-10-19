"""4단계 챗봇 오케스트레이터. 단계 구현은 각각의 전용 모듈에 둔다."""
from __future__ import annotations
import re
from pathlib import Path
from dataclasses import replace
from threading import RLock
from .schemas import AnswerResult, Evidence
from .guardrails import validate_input
from .content_moderation import InputModerator
from .db1_repository import Db1Repository
from .query_service import execute
from .knowledge_retriever import retrieve
from .explanation_retriever import retrieve_explanation
from .answer_generator import template_answer, try_gemini, age_capabilities_answer, consumption_criteria_answer
from .answer_validator import validate_answer
from .conversation_memory import ConversationMemory
from .llm_intent_resolver import IntentResolver
from .query_planner import complete_and_validate
from .dialogue_router import DIALOGUE_REPLIES
from .analysis2_knowledge import methodology_answer
from .observation_period import observation_period

class Chatbot:
 def __init__(self, project_root: Path, model: str="gemini-2.5-flash-lite", intent_resolver=None, moderator=None, repository: Db1Repository=None):
  self.project_root=project_root
  if repository is None:raise ValueError('Chatbot에는 repository(Db1Repository)를 주입해야 합니다. PostgreSQL 저장소는 pg_repository.PostgresDb1Repository입니다.')
  self.repo=repository; self.model=model
  self.memory=ConversationMemory()
  self.moderator=moderator if moderator is not None else InputModerator(project_root)
  self.intent_resolver=intent_resolver or IntentResolver(project_root,model,self.repo.available_period())
  self.dashboard_scope=None; self.dashboard_segment_id=None
  self.allow_ai_generation=True
  self._operation_lock=RLock()
 def activate_dashboard_context(self, scope, segment_id):
  self.dashboard_scope=scope; self.dashboard_segment_id=segment_id
  self.memory=ConversationMemory()
 def answer(self, question: str) -> AnswerResult:
  with self._operation_lock:
   return self._answer(question)
 def _answer(self, question: str) -> AnswerResult:
  # 1. 인풋 필터링
  guard=validate_input(question)
  if not guard.allowed: return AnswerResult(guard.message, Evidence("입력 안내",guard.message))
  guard=self.moderator.check(question.strip())
  if not guard.allowed: return AnswerResult(guard.message, Evidence("입력 안전 안내",guard.message))
  # 지역·연령 집계는 개인의 상태를 판정할 수 없으므로, 이 요청에는
  # 신호·보조자료를 먼저 나열하지 않고 제한을 직접 답한다.
  if re.search(r"고립.*(?:확정|판단)|(?:확정|판단).*고립", question):
   text='확정할 수 없습니다. 화면의 신호는 지역 집단에서 관찰된 행동 변화에 관한 정보이며, 해당 동 주민이나 특정 개인의 고립을 판단하는 근거가 아닙니다.'
   return AnswerResult(text,Evidence("해석 범위 안내",text))
  # 기준월과 실제 관측월을 혼동하지 않도록, 직전 확정 조회의 기간을
  # 바로 설명한다. 처리 이력·전체 데이터 범위는 이 질문에 포함하지 않는다.
  previous=self.memory.last_scope()
  if previous and previous.start_month and previous.start_month==previous.end_month and re.search(r"실제.*(?:어느|몇).*(?:달|월)|관측.*(?:기간|달|월)",question):
   start,end=observation_period(previous.start_month) or (None,None)
   if start and end:
    text=f"{previous.start_month[:4]}년 {int(previous.start_month[5:])}월은 자료의 기준월입니다. 실제 관측기간은 {start[:4]}년 {int(start[5:])}~{int(end[5:])}월입니다."
    return AnswerResult(text,Evidence("관측기간 안내",text))
  # 2. 목적 체크와 메뉴 필터링
  self.intent_resolver.available_period=self.repo.available_period()
  # 클러스터명을 직접 물은 경우에는 화면에서 선택한 동을 자동으로
  # 끼워 넣지 않고, DB에 저장된 해당 클러스터를 먼저 찾는다.
  if '클러스터' in question:
   matched=next((name for name in self.repo.cluster_types() if name in question), None)
   if matched:
    dongs=self.repo.cluster_districts(matched)
    text=(f'“{matched}”은 비슷한 지역 구조를 묶은 클러스터 유형입니다. '
          '개인의 위험도나 이상신호 원인을 뜻하지 않습니다.'
          + (f' 현재 이 유형에 해당하는 행정동은 {", ".join(dongs[:10])}'
             + (f' 등 총 {len(dongs)}곳입니다.' if len(dongs)>10 else '입니다.')
             if dongs else ' 해당 유형의 행정동 자료를 찾지 못했습니다.'))
    return AnswerResult(text,Evidence('클러스터 설명',text),
                        ('다른 클러스터도 설명해줘', '이 클러스터에 속한 동을 알려줘'))
  intent=self.intent_resolver.resolve(question,self.repo.districts(),self.memory)
  if intent.question_type in {'capabilities','consumption_criteria'}:
   text=age_capabilities_answer() if intent.question_type=='capabilities' else consumption_criteria_answer()
   return AnswerResult(text,Evidence('연령별 조회 안내' if intent.question_type=='capabilities' else '소비 증감 비교 기준',text))
  if intent.question_type == "methodology":
   text=methodology_answer(question)
   return AnswerResult(text,Evidence("이상신호 판정 기준",text),
                       ("삼성1동은 왜 확인 대상인가요?", "연령별 기준도 다른가요?"))
  if self.dashboard_scope and intent.question_type not in {'signals','rank_regions'} and not intent.dong and not intent.dongs:
   intent=replace(intent,dong=self.dashboard_scope['dong'],start_month=intent.start_month or self.dashboard_scope['label_month'],end_month=intent.end_month or self.dashboard_scope['label_month'],age_band=intent.age_band if intent.age_scope_explicit or intent.question_type=='age_activity' else intent.age_band or self.dashboard_scope.get('age_band'),needs=tuple(x for x in intent.needs if x not in {'행정동','기간'}))
  if intent.purpose == "dialogue":
   text=DIALOGUE_REPLIES.get(intent.question_type,DIALOGUE_REPLIES["off_topic"])
   return AnswerResult(text,Evidence("대화 안내",text))
  start,end=self.repo.available_period()
  # The initial history calibrates the model. It is intentionally not exposed
  # as a period with operational detection results.
  if (intent.question_type in {"signals","rank_regions"} and intent.start_month and intent.end_month
      and intent.end_month < start):
   text=(f"{intent.start_month}~{intent.end_month}은 신호가 나온 지역을 조회하는 기간이 아닙니다. "
         "이 기간은 판정 기준을 만들기 위한 초기 이력으로만 사용합니다. "
         f"현재 신호 조회는 {start}~{end}에서 가능합니다.")
   return AnswerResult(text,Evidence("조회 범위 안내",text),
                       ("2025년 하반기 확인할 지역 알려줘", "이상신호 기준은 무엇인가요?"))
  if intent.question_type=='consumption':start,end=self.repo.consumption_period()
  intent=complete_and_validate(intent,self.memory,start,end)
  if intent.needs:
   self.memory.set_pending(question,intent)
   if '연령' in intent.needs:
    text='연령별 변화 비교는 20대·30대·40대·50대·60세 이상을 각각 볼 수 있습니다. 이상신호 판정 조회는 한 묶음씩 지원하며, 전체 연령도 선택할 수 있습니다.'
    return AnswerResult(text,Evidence('연령 확인',text))
   text=intent.clarifying_question or self._clarify(intent.needs, intent)
   if '기간' in intent.needs:
    text+=(f' 소비자료 조회 범위는 {start}~{end}입니다.' if intent.question_type=='consumption'
           else f' 현재 탐지 결과는 {start}~{end}이며, 2025년 6월까지는 초기 이력입니다.')
   return AnswerResult(text,Evidence("추가 조건 필요",text),self._clarification_choices(intent.needs))
  # 3. 정확한 데이터 조회 + RAG + 답변 생성
  try:
   evidence=execute(self.repo,intent)
  except (ValueError,FileNotFoundError) as exc: return AnswerResult(str(exc),Evidence("조회 안내",str(exc)))
  self.memory.add(question,intent,evidence)
  knowledge=retrieve(question,intent.question_type)
  if intent.age_band and knowledge:
   knowledge='연령별 탐지는 2025년 6월까지의 초기 이력으로 보정한 기준을 고정하고, 동·연령 자체 변화와 강남구 공통변화를 뺀 변화에서 통화·문자 또는 평일·휴일 이동의 짝 지표를 확인합니다. 각 수치의 기준은 조회 결과에 포함되어 있습니다.'
  explanation=retrieve_explanation(intent,evidence)
  # These answers are displayed first in the dashboard. Keep their structure
  # predictable and concise even when an optional language model is configured.
  concise_types={"signals","rank_regions","reason","support","age_activity","consumption","provenance"}
  text=(template_answer(intent,evidence,knowledge,explanation) if intent.question_type in concise_types or not self.allow_ai_generation
        else try_gemini(question,intent,evidence,knowledge,explanation,self.model,self.project_root) or template_answer(intent,evidence,knowledge,explanation))
  # 4. 답변 필터링. 실패하면 검증된 템플릿으로 되돌린다.
  passed,_=validate_answer(text,evidence)
  if not passed: text=template_answer(intent,evidence,knowledge,explanation)
  return AnswerResult(text,evidence,self._follow_ups(intent,evidence))

 @staticmethod
 def _follow_ups(intent: QueryIntent, evidence: Evidence) -> tuple[str, ...]:
  """Offer the next useful question for the answer just shown, with its scope."""
  if not evidence.rows and intent.question_type in {"reason", "support", "previous"}:
   return (
    "2025년 다른 이상신호 지역 찾아줘",
    "2025년 하반기 이상신호 탐지 지역 알려줘",
    "이상신호 기준은 무엇인가요?",
   )
  first = evidence.rows[0] if evidence.rows else {}
  dong = first.get("행정동") or intent.dong
  prefix = f"{dong}" if dong else "선택한 지역"
  # 전체 사례 조회는 첫 번째 행(예: 개포3동)을 현재 선택 지역으로
  # 간주하면 안 된다. 결과 전체를 탐색할 수 있는 후속 질문을 제공한다.
  if intent.question_type in {"signals", "rank_regions"} and intent.age_scope_explicit and len({r.get("행정동") for r in evidence.rows}) > 1:
   return (
    "이상신호가 탐지된 모든 동을 자세히 설명해줘",
    "각 이상신호의 탐지 기준과 변화 수치 알려줘",
    "2025년 이상신호가 없는 지역도 알려줘",
   )
  if intent.question_type in {"signals", "rank_regions"} and dong:
   return (
    f"왜 {prefix}이 확인 대상인가요?",
    f"{prefix}의 지역 배경 정보 보여줘",
    "이상신호 기준은 무엇인가요?",
    "연령별 이상신호 전체 탐지 보기",
   )
  if intent.question_type == "reason" and dong:
   return (
    f"{prefix}의 지역 배경 정보 보여줘",
    f"{prefix}의 연령대별 변화는 어떻게 돼요?",
    f"{prefix}은 전월에도 탐지됐나요?",
   )
  if intent.question_type == "support" and dong:
   return (
    f"왜 {prefix}이 확인 대상인가요?",
    f"이 기간 {prefix}에서 거래가 많이 늘어난 소비 분야는?",
    f"{prefix}은 전월에도 탐지됐나요?",
   )
  if intent.question_type == 'age_activity' and dong:
   return (f'{prefix}의 30대 월별 변화 보여줘', f'{prefix}의 지역 배경 정보 보여줘', '연령별 이상신호 기준은 무엇인가요?')
  if intent.question_type == 'consumption':
   return ('소비 급증을 판단하는 기준이 필요한가요?', '이상신호 기준은 무엇인가요?')
  return ("이상신호 기준은 무엇인가요?", "왜 신호로 잡혔나요?", "전월에도 탐지됐나요?")

 @staticmethod
 def _clarify(needs, intent):
  missing=set(needs)
  if intent.question_type=='age_activity':
   details='·'.join({'행정동':'지역','기간':'기간'}.get(item,item) for item in needs)
   return age_capabilities_answer()+' '+details+'을 알려주시면 실제 변화율을 비교해 드릴게요.'
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
