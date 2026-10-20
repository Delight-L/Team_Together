"""4단계 답변필터링. 수치 구조는 코드, 과장된 표현은 규칙으로 막는다."""
from __future__ import annotations
from .schemas import Evidence
FORBIDDEN=("고립이 확정", "고립되었습니다", "원인입니다", "때문에 감소", "위험이 악화")
def validate_answer(text: str, evidence: Evidence) -> tuple[bool,str]:
    if not text.strip():
        return False,"빈 답변입니다."
    if any(term in text for term in FORBIDDEN):
        return False,"근거를 넘는 단정 표현이 있습니다."
    if len(text)>7000:
        return False,"답변이 너무 깁니다."
    if evidence.supplementary.get('analysis3_district_shared') and not any(term in text for term in ('강남구','구 단위','구 공통')):
        return False,'구 단위 보조자료의 범위가 표시되지 않았습니다.'
    if any(row.get('age_band') for row in evidence.rows) and not any(term in text for term in ('20대','30대','40대','50대','60세','60대','연령')):
        return False,'연령 조회 범위가 표시되지 않았습니다.'
    if evidence.rows and not any(str(row.get("행정동", "")) in text for row in evidence.rows):
        # 지역명이 없는 지역유형 결과 등은 예외로 둔다.
        return False,"조회된 지역 근거가 답변에 포함되지 않았습니다."
    return True,"통과"
