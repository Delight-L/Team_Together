"""터미널 UI. 메뉴 버튼과 자유 질문 모두 Chatbot.answer로 들어간다."""
from __future__ import annotations
from pathlib import Path
from .menu import render_menu, menu_question
from .orchestrator import Chatbot

def run_cli(project_root: Path) -> int:
 bot=Chatbot(project_root)
 print("지역 변화 신호 챗봇입니다. 종료하려면 종료 또는 exit를 입력하세요.")
 print(render_menu())
 while True:
  raw=input("\n추가 질문> ").strip()
  if raw.lower() in {"종료","exit","quit"}: return 0
  question=menu_question(raw) or raw
  result=bot.answer(question)
  print("\n"+result.text)
  if result.follow_ups: print("\n이어서 확인하기: "+" / ".join(result.follow_ups))
