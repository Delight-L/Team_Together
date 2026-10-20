"""JSON 평가 결과를 사람이 검토하기 쉬운 CSV와 Markdown으로 변환한다."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.result.read_text(encoding="utf-8"))
    rows = data["results"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / (args.result.stem + "-review.csv")
    md_path = args.output_dir / (args.result.stem + "-summary.md")

    fields = ["case_id", "path_id", "title", "measurement_goal", "question", "reference_answer", "actual_answer", "bleu1", "rouge1", "rougeL", "human_label", "review_note"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: (row.get("title", "") if field == "measurement_goal" else row.get(field, "")) for field in fields})

    avg = lambda key: sum(float(row.get(key, 0)) for row in rows) / len(rows) if rows else 0
    low = sorted(rows, key=lambda row: float(row.get("rougeL", 0)))[:10]
    lines = [
        "# 챗봇 답변 평가 검토표",
        "",
        f"평가 건수: {len(rows)}개",
        f"BLEU-1 평균: {avg('bleu1'):.4f}",
        f"ROUGE-1 평균: {avg('rouge1'):.4f}",
        f"ROUGE-L 평균: {avg('rougeL'):.4f}",
        "",
        "## 검토 방법",
        "",
        "CSV 파일을 엑셀로 열고 `actual_answer`를 `reference_answer`와 비교하세요.",
        "`human_label` 열에 `정답`, `부분 정답`, `오답`, `평가 불가` 중 하나를 입력하고 `review_note`에 이유를 적습니다.",
        "",
        "## ROUGE-L 점수가 낮은 10개",
        "",
        "| ID | 질문 | ROUGE-L |",
        "|---|---|---:|",
    ]
    for row in low:
        question = str(row.get("question", "")).replace("|", " ")
        lines.append(f"| {row.get('case_id', '')} | {question[:100]} | {float(row.get('rougeL', 0)):.4f} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(csv_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
