"""Chatbot_Test의 LLM 클라이언트 분리 구조를 기존 Gemini 설정에 적용합니다."""
import os


class LLMClient:
    def __init__(self):
        from google import genai
        self._client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])

    def generate(self, prompt):
        response = self._client.models.generate_content(
            model=os.environ['GEMINI_MODEL'], contents=prompt)
        return response.text or ''
