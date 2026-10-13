from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 프로젝트 루트의 .env에서 보미의 AI 연결 설정을 읽습니다.
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore")
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # 답변 한 번의 최대 길이(토큰). 비정상적으로 긴 답변과 비용을 막습니다.
    openai_max_tokens: int = 1500
    # 사용자 질문의 유해 콘텐츠 검사 모델(OpenAI 무료 API). AI 사용 모드에서만 호출합니다.
    openai_moderation_model: str = "omni-moderation-latest"
    cors_origins: list[str] = ["http://localhost:8503", "http://127.0.0.1:8503", "http://localhost:5173", "http://127.0.0.1:5173"]

settings = Settings()
