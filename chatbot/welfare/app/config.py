from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # chat_test2의 설정 구조를 사용하며 팀 프로젝트 루트의 .env를 읽습니다.
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore")
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    cors_origins: list[str] = ["http://localhost:8503", "http://127.0.0.1:8503", "http://localhost:5173", "http://127.0.0.1:5173"]

settings = Settings()
