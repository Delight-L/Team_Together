"""평가 결과 CSV에 케이스 설명을 보강한 사람이 읽는 안내 파일을 만든다."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review_csv", type=Path)
    args = parser.parse_args()
    output = args.review_csv.with_name(args.review_csv.stem + "-guide.csv")
    fields = [
        "case_id",
        "path_id",
        "title",
        "question",
        "reference_answer",
        "actual_answer",
        "bleu1",
        "rouge1",
        "rougeL",
        "human_label",
        "review_note",
    ]
    with (
        args.review_csv.open(encoding="utf-8-sig", newline="") as source,
        output.open("w", encoding="utf-8-sig", newline="") as target,
    ):
        reader = csv.DictReader(source)
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for row in reader:
            writer.writerow({field: row.get(field, "") for field in fields})
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
