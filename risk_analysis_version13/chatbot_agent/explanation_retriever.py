"""신호별 설명 기준 문서에서 LLM에게 줄 관련 조각만 찾는다."""
from __future__ import annotations

from pathlib import Path

from .schemas import Evidence, QueryIntent

GUIDE = Path(__file__).with_name("explanation_guide.md")


def _sections(text: str) -> dict[str, str]:
    chunks: dict[str, list[str]] = {}
    current = "intro"
    chunks[current] = []
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            chunks[current] = [line]
        else:
            chunks[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in chunks.items()}


def retrieve_explanation(intent: QueryIntent, evidence: Evidence) -> str:
    """실제 조회 결과의 신호 유형에 맞는 설명 규칙만 반환한다."""
    if not GUIDE.is_file():
        return ""
    sections = _sections(GUIDE.read_text(encoding="utf-8"))
    signal_values = " ".join(str(row.get("signal_type", "")) for row in evidence.rows).lower()
    wanted = ["Robust Z 설명", "보조 정보", "출력 원칙"]
    if intent.signal == "mobility" or "mobility" in signal_values:
        wanted.insert(0, "이동 신호")
    if intent.signal == "communication" or "communication" in signal_values:
        wanted.insert(0, "통신 신호")
    if intent.signal == "combined" or "combined" in signal_values:
        wanted = ["이동 신호", "통신 신호", *wanted]
    return "\n\n".join(sections[name] for name in dict.fromkeys(wanted) if name in sections)
