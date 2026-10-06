"""대화 문맥을 읽는 LLM 목적체크. 결과값은 코드 허용목록으로 다시 검증한다."""
from __future__ import annotations
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from .conversation_memory import ConversationMemory
from .intent_parser import parse_intent
from .schemas import QueryIntent

PURPOSES={"find_region","track_change","plan_review"}
KINDS={"signals","rank_regions","anomaly","activity","reason","previous","context","support"}
SIGNALS={"any","communication","mobility","combined"}
METRICS={None,"call_contacts","text_contacts","weekday_move_count","weekend_move_count"}


def _explicit_districts(question: str, districts: set[str]) -> tuple[str, ...]:
    """질문에 새 지역명이 있으면 LLM의 문맥 추정보다 우선한다.

    `개포동`처럼 번호가 생략된 표현은 개포1·2·4동 전체를 뜻하는
    지역 묶음으로 해석한다. 따라서 직전 조회에 있던 다른 동이 다시
    섞이지 않는다.
    """
    exact = tuple(sorted((name for name in districts if name in question), key=len, reverse=True))
    if exact:
        return exact
    roots = {re.sub(r"[0-9]+동$", "", name) for name in districts}
    matches = []
    for root in roots:
        if root and f"{root}동" in question:
            matches.extend(sorted(name for name in districts if name.startswith(root)))
    return tuple(dict.fromkeys(matches))

def _api_key(project_root: Path) -> str | None:
    value=os.getenv("GEMINI_API_KEY","").strip()
    if value: return value
    path=project_root/"chatbot_agent"/"api_key.txt"
    if path.is_file():
        value=path.read_text(encoding="utf-8-sig").strip()
        if value and not value.startswith("여기에_"): return value
    return None

def _json_object(text: str) -> dict:
    match=re.search(r"\{.*\}",text,re.S)
    if not match: raise ValueError("LLM 목적분류 결과에 JSON 객체가 없습니다.")
    value=json.loads(match.group(0))
    if not isinstance(value,dict): raise ValueError("목적분류 결과가 객체가 아닙니다.")
    return value

class IntentResolver:
    def __init__(self, project_root: Path, model: str, available_period: tuple[str, str] | None = None):
        self.project_root=project_root
        self.model=model
        self.available_period=available_period

    def resolve(self, question: str, districts: set[str], memory: ConversationMemory) -> QueryIntent:
        explicit_names = _explicit_districts(question, districts)
        key=_api_key(self.project_root)
        if not key:
            return self._apply_explicit_districts(parse_intent(question,districts), explicit_names)
        try:
            from google import genai
            prompt=f'''당신은 강남구 지역 변화 신호 챗봇의 자연어 조회 계획자입니다.
현재 질문뿐 아니라 이전 대화 결과를 읽고 사용자가 가리키는 실제 행정동과 목적을 해석하세요.
예: 그 동들, 위 지역, 앞의 세 곳, 두 번째 동, 아까 나온 곳은 대화 문맥의 districts를 기준으로 해석합니다.
단, 현재 질문에 새 행정동 또는 지역명이 직접 쓰였다면 그것이 최우선입니다. 이전 districts를 그대로
반환하거나 함께 섞지 마세요. 예: 이전 결과가 삼성2동·압구정동이고 현재 질문이 "개포동만"이면
districts는 개포로 시작하는 동만 반환해야 합니다.
사람이 쓰는 기간 표현(하반기, 연말, 작년 겨울 등)은 일반적인 달력 의미와 데이터 범위를 보고 스스로
start_month/end_month(YYYY-MM)로 변환하세요. 기간을 하나로 정할 근거가 정말 없을 때만 needs에 기간을 넣으세요.
질문에 대상·기간이 생략됐고 이전 대화에 하나의 확정 범위가 있으면 그것을 이어받으세요.
기간이 필수인 조회인데 현재 질문과 확정된 후속 문맥으로도 기간을 정할 수 없으면, 절대로 전체 기간을
조회하지 마세요. needs에 기간을 넣고 clarifying_question에 자연스러운 되물음 문장을 넣으세요.
예: "세곡동의 어느 기간 변화를 확인할까요? 예: 2025년 하반기 또는 2025년 11월~12월"
use_previous_scope는 사용자가 "그 동", "위 결과", "아까 것", "개포동만"처럼 직전 조회를 분명히
이어가는 경우에만 true로 하세요. 새 질문이면 false입니다.

허용 purpose: find_region, track_change, plan_review
허용 question_type: signals, rank_regions, anomaly, activity, reason, previous, context, support
허용 signal: any, communication, mobility, combined
허용 metric: call_contacts, text_contacts, weekday_move_count, weekend_move_count 또는 null
사용 가능한 행정동: {sorted(districts)}
실제 탐지 데이터 기간: {self.available_period or '알 수 없음'}
이전 대화: {json.dumps(memory.as_prompt_data(),ensure_ascii=False)}
현재 질문: {question}

JSON만 반환하세요:
{{"purpose":"...","question_type":"...","districts":[],"start_month":null,"end_month":null,
"signal":"any","metric":null,"limit":null,"needs":[],"use_previous_scope":false,
"all_available_period":false,"clarifying_question":null}}'''
            response=genai.Client(api_key=key).models.generate_content(model=self.model,contents=prompt)
            raw=_json_object(getattr(response,"text","") or "")
            return self._apply_explicit_districts(self._validate(raw,districts), explicit_names)
        except Exception:
            return self._apply_explicit_districts(parse_intent(question,districts), explicit_names)

    @staticmethod
    def _apply_explicit_districts(intent: QueryIntent, names: tuple[str, ...]) -> QueryIntent:
        """명시 지역은 대화 메모리를 대신하는 조회 범위다."""
        if not names:
            return intent
        needs=tuple(item for item in intent.needs if item != "행정동")
        return replace(intent, dong=names[0] if len(names)==1 else None,
                       dongs=names, needs=needs)

    def _validate(self, raw: dict, allowed_districts: set[str]) -> QueryIntent:
        purpose=raw.get("purpose") if raw.get("purpose") in PURPOSES else "find_region"
        kind=raw.get("question_type") if raw.get("question_type") in KINDS else "signals"
        names=tuple(dict.fromkeys(str(x) for x in raw.get("districts",[]) if str(x) in allowed_districts))
        signal=raw.get("signal") if raw.get("signal") in SIGNALS else "any"
        metric=raw.get("metric") if raw.get("metric") in METRICS else None
        limit=raw.get("limit")
        limit=max(1,min(int(limit),22)) if isinstance(limit,(int,float)) else None
        needs=tuple(str(x) for x in raw.get("needs",[]) if str(x) in {"행정동","기간","지표","조회 목적"})
        clarification=raw.get("clarifying_question")
        clarification=clarification.strip()[:300] if isinstance(clarification,str) else None
        if kind in {"activity","reason","previous","context","support"} and not names and "행정동" not in needs:
            needs=(*needs,"행정동")
        return QueryIntent(purpose,kind,names[0] if len(names)==1 else None,
                           raw.get("start_month"),raw.get("end_month"),signal,metric,needs,limit,names,
                           bool(raw.get("use_previous_scope")), bool(raw.get("all_available_period")), clarification)
