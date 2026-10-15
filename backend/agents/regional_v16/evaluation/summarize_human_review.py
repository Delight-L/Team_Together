"""사람이 CSV에 입력한 human_label을 자동 집계한다."""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


LABELS = ("정답", "부분 정답", "오답", "평가 불가")


def read_rows(path: Path):
    """Excel에서 저장한 UTF-8/CP949 CSV를 모두 읽는다."""
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with path.open(encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", b"", 0, 1, "지원하지 않는 CSV 인코딩")


def normalize_label(value: str) -> str:
    compact = "".join((value or "").split())
    mapping = {"정답": "정답", "오답": "오답", "부분정답": "부분 정답", "평가불가": "평가 불가", "": ""}
    if compact not in mapping:
        raise ValueError(f"알 수 없는 판정: {value!r}. 정답/부분 정답/오답/평가 불가를 사용하세요.")
    return mapping[compact]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_csv", type=Path)
    args = parser.parse_args()
    rows = read_rows(args.review_csv)
    for row in rows:
        row["human_label"] = normalize_label(row.get("human_label", ""))
    labels = Counter(row.get("human_label", "").strip() for row in rows)
    judged = sum(labels[label] for label in LABELS if label != "평가 불가")
    strict = labels["정답"] / judged if judged else 0
    accepted = (labels["정답"] + labels["부분 정답"]) / judged if judged else 0
    by_task = defaultdict(Counter)
    for row in rows:
        task = row.get("title", "미분류")
        by_task[task][row.get("human_label", "") or "미작성"] += 1
    output = args.review_csv.with_name(args.review_csv.stem + "-human-summary.md")
    lines = ["# 사람 검토 종합 결과", "", f"전체 케이스: {len(rows)}개", f"검토 완료: {sum(labels[label] for label in LABELS)}개", "", "## 판정별 건수", "", "| 판정 | 건수 |", "|---|---:|"]
    for label in (*LABELS, "미작성"):
        count = labels[""] if label == "미작성" else labels[label]
        lines.append(f"| {label} | {count} |")
    lines += ["", f"엄격한 정답률: {strict:.1%}", f"부분 정답 포함 비율: {accepted:.1%}", "", "## 업무별 검토 결과", "", "| 평가 업무 | 정답 | 부분 정답 | 오답 | 평가 불가 | 미작성 |", "|---|---:|---:|---:|---:|---:|"]
    for task, counts in sorted(by_task.items()):
        lines.append(f"| {task} | {counts['정답']} | {counts['부분 정답']} | {counts['오답']} | {counts['평가 불가']} | {counts['미작성']} |")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
