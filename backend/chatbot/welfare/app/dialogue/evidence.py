"""사업별 핵심 사실 검사. 검사 전 AI 원문은 사용자에게 보내지 않습니다."""
import json
import re
from backend.chatbot.guardrails import redact_unverified, UNVERIFIED

# 날짜·나이·비율도 다른 사업에서 가져오지 못하도록 검사합니다.
DETAIL = re.compile(r"20\d{2}(?:[-./]\d{1,2}(?:[-./]\d{1,2})?|년(?:\s*\d{1,2}월(?:\s*\d{1,2}일)?)?)|\d+(?:\.\d+)?\s*(?:세|%|개월)")


def validate_answer(answer, records):
    """[자료 N] 또는 명확한 사업명으로 단락을 귀속. 모호하면 핵심 수치는 보수적으로 가립니다."""
    hidden, checked = [], []
    active = records[0] if len(records) == 1 else None
    for line in answer.splitlines(keepends=True):
        markers = re.findall(r"\[자료 (\d+)\]", line)
        named = [r for r in records if r["name"] in line]
        if markers:
            ids = list(dict.fromkeys(int(i) - 1 for i in markers))
            active = records[ids[0]] if len(ids) == 1 and 0 <= ids[0] < len(records) else None
            # 자료 표기는 서버가 실제 사업명으로 치환합니다.
            line = re.sub(r"\[자료 (\d+)\]", lambda m: (
                "[" + records[int(m[1]) - 1]["name"] + "]" if 0 < int(m[1]) <= len(records)
                else "[근거 미확인]"), line)
            if named and (len(named) != 1 or active is None or named[0]["id"] != active["id"]):
                active = None
        elif named:
            active = named[0] if len(named) == 1 else None
        elif not line.strip():
            active = records[0] if len(records) == 1 else None
        material = json.dumps(active or {}, ensure_ascii=False)
        line, kinds = redact_unverified(line, material)
        hidden.extend(kinds)
        for fact in DETAIL.findall(line):
            if re.sub(r"\s+", "", fact) not in re.sub(r"\s+", "", material):
                line = line.replace(fact, UNVERIFIED)
                hidden.append("기간·대상 수치")
        checked.append(line)
    return "".join(checked), list(dict.fromkeys(hidden))
