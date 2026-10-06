"""개선된 지역 변화 신호 챗봇 실행 진입점.
직접 실행과 python -m chatbot_agent.main 실행을 모두 지원한다.
"""
from __future__ import annotations
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from chatbot_agent.cli import run_cli
else:
    from .cli import run_cli
if __name__ == "__main__":
    raise SystemExit(run_cli(Path(__file__).resolve().parent.parent))
