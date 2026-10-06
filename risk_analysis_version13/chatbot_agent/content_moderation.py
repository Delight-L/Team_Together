"""한국어 사용자 입력만 OpenAI Moderation API로 검사한다."""
from __future__ import annotations
import logging
import os
from pathlib import Path
from .schemas import GuardResult

MODEL = "omni-moderation-latest"
UNAVAILABLE = "입력 안전 검사를 완료하지 못했습니다. 잠시 후 다시 시도해 주세요. 설정 담당자는 OPENAI_API_KEY와 API 연결을 확인해 주세요."
BLOCKED = "요청에 안전상 처리하기 어려운 내용이 포함되어 있습니다. 지역 변화 신호나 복지 지원에 관한 질문으로 바꿔 주세요."
logger = logging.getLogger(__name__)

class InputModerator:
    def __init__(self, project_root: Path, client=None):
        self.project_root = Path(project_root)
        self.client = client

    def check(self, question: str) -> GuardResult:
        try:
            client = self.client
            if client is None:
                from dotenv import dotenv_values
                # 운영 환경 변수가 우선, 프로젝트 루트 .env는 보조.
                key = os.getenv("OPENAI_API_KEY") or dotenv_values(self.project_root / ".env").get("OPENAI_API_KEY")
                if not key:
                    return GuardResult(False, UNAVAILABLE)
                from openai import OpenAI
                client = OpenAI(api_key=key, timeout=10.0, max_retries=0)
                self.client = client
            response = client.moderations.create(model=MODEL, input=question)
            result = response.results[0]
            if not isinstance(result.flagged, bool):
                raise ValueError("Invalid moderation result")
            if result.flagged:
                categories = result.categories.model_dump(by_alias=True)
                if any(categories.get(name) for name in ("self-harm", "self-harm/intent", "self-harm/instructions")):
                    return GuardResult(False, "자해 관련 내용이 감지되어 일반 데이터 답변 대신 안전 안내를 드립니다. 본인이나 다른 사람이 당장 위험하다면 119 또는 112에 연락하고, 가까운 사람에게 도움을 요청해 주세요. 지역의 예방·지원 자료는 구체적인 위해 표현 없이 질문해 주세요.")
                return GuardResult(False, BLOCKED)
            return GuardResult(True)
        except Exception as exc:
            # API 오류 원문에는 질문·인증정보가 포함될 수 있으므로 기록하지 않는다.
            logger.warning("Input moderation unavailable (%s)", type(exc).__name__)
            return GuardResult(False, UNAVAILABLE)
