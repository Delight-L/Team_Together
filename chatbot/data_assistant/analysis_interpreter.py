from __future__ import annotations

from pathlib import Path
import pandas as pd


def _col(df: pd.DataFrame, *names: str) -> str | None:
    return next((name for name in names if name in df.columns), None)


def explain_all_signals(project_root: Path) -> str:
    path = project_root / "agents" / "regional_analysis" / "Analysis2" / "outputs" / "gangnam_analysis2_evidence_card_2022_2025.csv"
    if not path.is_file():
        return f"Evidence Card 파일을 찾을 수 없습니다: {path}"
    df = pd.read_csv(path, encoding="utf-8-sig")
    code_col = _col(df, "행정동코드", "area_code")
    name_col = _col(df, "행정동", "행정동명", "area_name")
    # 일부 Windows 환경에서 기존 CSV의 한글 헤더가 깨져도 고정된 Analysis2 열 순서를 보존한다.
    if code_col is None and len(df.columns) > 1:
        code_col = df.columns[1]
    if name_col is None and len(df.columns) > 2:
        name_col = df.columns[2]
    type_col = _col(df, "signal_type")
    status_col = _col(df, "signal_status")
    rz_cols = [c for c in df.columns if c.endswith("_rz") or "expanding_rz" in c]
    lines = [f"Evidence Card 전체 {len(df)}건의 신호입니다.", "아래는 각 신호가 왜 표시됐는지 쉬운 말로 풀어 쓴 내용입니다.", "판정 기준: 해당 지표의 Robust Z가 -2.0 이하이면 평소보다 크게 낮은 변화로 봅니다."]
    for i, row in df.iterrows():
        signal = str(row.get(type_col, "확인 불가")) if type_col else "확인 불가"
        status = str(row.get(status_col, "확인 불가")) if status_col else "확인 불가"
        place = str(row.get(name_col, "")) if name_col else ""
        code = str(row.get(code_col, "")) if code_col else ""
        selected = rz_cols
        if signal.lower() == "communication":
            selected = [c for c in rz_cols if "call" in c or "text" in c]
        elif signal.lower() == "mobility":
            selected = [c for c in rz_cols if "move" in c]
        labels = {"call_contacts_residual_change_expanding_rz": "통화 접촉 변화", "text_contacts_residual_change_expanding_rz": "문자 접촉 변화", "weekday_move_count_residual_change_expanding_rz": "평일 이동 변화", "weekend_move_count_residual_change_expanding_rz": "주말 이동 변화"}
        rz = ", ".join(f"{labels.get(c, c)} {float(row[c]):.2f}" for c in selected if pd.notna(row[c]))
        supports = []
        if bool(row.get("mobility_distance_support", False)): supports.append("이동거리 보조 근거 있음")
        if bool(row.get("communication_interest_support", False)): supports.append("관심집단 보조 근거 있음")
        if bool(row.get("interest_structural_issue", False)): supports.append("관심집단 구조 이슈 있음")
        type_ko = {"communication": "통신량 감소", "mobility": "이동량 감소", "combined": "통신·이동 동시 감소"}.get(signal.lower(), signal)
        status_ko = {"new": "이번 기간에 새로 포착", "continuing": "이전 기간부터 계속 포착"}.get(status.lower(), status)
        reason = f"{rz}가 기준(-2.0) 이하" if rz else "관련 지표 확인 필요"
        lines.append(f"{i + 1}. {row.get('date', '날짜 확인 불가')} {place}({code}) — {type_ko}, {status_ko}. {reason}." + (f" 보조 근거: {', '.join(supports)}." if supports else ""))
    lines.append("\n해석 주의: 이 신호는 과거 행동 패턴보다 이례적인 변화가 있었다는 뜻이며 사회적 고립을 확정하지 않습니다.")
    lines.append("근거 파일: Analysis2/outputs/gangnam_analysis2_evidence_card_2022_2025.csv")
    return "\n".join(lines)


def summarize_dongs(project_root: Path) -> str:
    path = project_root / "agents" / "regional_analysis" / "Analysis2" / "outputs" / "gangnam_analysis2_evidence_card_2022_2025.csv"
    if not path.is_file():
        return "Evidence Card 결과 파일을 찾을 수 없습니다."
    df = pd.read_csv(path, encoding="utf-8-sig")
    name_col = _col(df, "행정동", "행정동명", "area_name") or (df.columns[2] if len(df.columns) > 2 else None)
    type_col = _col(df, "signal_type")
    if not name_col:
        return "행정동 이름을 결과에서 확인할 수 없습니다."
    grouped = []
    for name, part in df.groupby(name_col, sort=False):
        kinds = []
        if type_col:
            for value in part[type_col].dropna().astype(str):
                label = {"communication": "통신", "mobility": "이동", "combined": "통신·이동"}.get(value.lower(), value)
                if label not in kinds:
                    kinds.append(label)
        grouped.append(f"- {name}: {len(part)}건" + (f" ({', '.join(kinds)} 신호)" if kinds else ""))
    return (f"총 {len(df)}건의 이상 신호가 {len(grouped)}개 행정동에서 발견되었습니다.\n"
            "한 동에서 여러 달 또는 여러 신호 유형이 발생할 수 있어 건수와 동 수가 다릅니다.\n\n" + "\n".join(grouped))
