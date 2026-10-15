from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)
    @field_validator("content")
    @classmethod
    def nonempty_content(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("메시지는 비어 있을 수 없습니다.")
        return value

class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    @model_validator(mode="after")
    def validate_last(self):
        if self.messages[-1].role != "user" or not self.messages[-1].content.strip():
            raise ValueError("마지막 메시지는 비어 있지 않은 사용자 질문이어야 합니다.")
        return self
