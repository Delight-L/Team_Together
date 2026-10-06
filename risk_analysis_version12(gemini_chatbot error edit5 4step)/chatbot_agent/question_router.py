"""기존 호출 호환용 라우터. 새 구현은 intent_parser와 orchestrator를 사용한다."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Route: kind:str; supported:bool
OUT_OF_SCOPE="현재 챗봇의 목적에 맞지 않는 질문입니다. 고립 문제 데이터와 관련된 질문을 해주세요."
def route_question(question:str)->Route:
 q=question.lower()
 if any(x in q for x in ('저녁','맛집','주식')): return Route('out_of_scope',False)
 if 'robust' in q or '임계값' in q: return Route('methodology',True)
 if '35건' in q: return Route('all_signals',True)
 return Route('data_question',True)
