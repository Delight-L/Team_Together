from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    message: str = Field(min_length=1, max_length=1000)


class ResetRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)

class DashboardBriefRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=100)
    selection_revision: int = Field(ge=0)
    snapshot_id: str = Field(min_length=1, max_length=200)
    dong: str = Field(min_length=1, max_length=100)
    label_month: str = Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")
    age_band: Literal["20s", "30s", "40s", "50s", "60plus"] | None = None
