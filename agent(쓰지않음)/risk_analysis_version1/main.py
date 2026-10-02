"""위험변화 탐지 에이전트 실행 파일 (Windows/macOS 공통)."""
from __future__ import annotations
import argparse
from pathlib import Path
from analyzer import run_risk_analysis
from config import MIN_RELATIVE_CHANGE_PP, ROBUST_Z_THRESHOLD
from data_provider import load_preprocessed_csv


def print_user_alerts(signals, region_alerts) -> None:
    """CSV와 별개로 담당자가 즉시 읽을 수 있는 후보 요약을 화면에 출력한다."""
    print("\n" + "=" * 62)
    print("[사용자용 위험 변화 후보]")
    print("개인 판정이 아닌 동 단위 현장 확인 우선순위 신호입니다.")
    print("=" * 62)

    if signals.empty:
        print("현재 설정값에서 위험 변화 후보가 없습니다.")
        return

    for number, (_, alert) in enumerate(region_alerts.iterrows(), start=1):
        dong_signals = signals[
            (signals["행정동코드"] == alert["행정동코드"])
            & (signals["기준연월"] == alert["기준연월"])
        ]
        print(f"\n{number}. {alert['기준연월']} {alert['행정동명']} — {alert['alert_level']}")
        for _, signal in dong_signals.iterrows():
            print(f"   - {signal['explanation']}")
        if "context_note" in dong_signals.columns and dong_signals["context_note"].notna().any():
            note = dong_signals["context_note"].dropna().iloc[0]
            if note:
                print(f"   - 지역 특징: {note}")
                print(f"     {dong_signals['cluster_profile'].dropna().iloc[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="동별 위험 방향 이상변화 탐지")
    parser.add_argument("--input", required=True, help="전처리 완료 월별 행동 CSV")
    parser.add_argument("--context", help="선택: 지역 유형·맥락 CSV")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--metrics", help="선택: 분석할 숫자 열. 쉼표로 구분")
    parser.add_argument("--min-relative-change", type=float, default=MIN_RELATIVE_CHANGE_PP)
    parser.add_argument("--z-threshold", type=float, default=ROBUST_Z_THRESHOLD, choices=[1.5, 2.5, 3.5])
    args = parser.parse_args()
    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    metrics = [x.strip() for x in args.metrics.split(",") if x.strip()] if args.metrics else None
    result = run_risk_analysis(load_preprocessed_csv(args.input), context=load_preprocessed_csv(args.context) if args.context else None, min_relative_change_pp=args.min_relative_change, z_threshold=args.z_threshold, metric_columns=metrics)
    files = {"전체 지표 판정": "risk_metric_assessment.csv", "위험 변화 후보": "risk_metric_signals.csv", "동별 요약": "risk_region_alerts.csv"}
    for label, filename in files.items():
        frame = {"전체 지표 판정": result.assessment, "위험 변화 후보": result.signals, "동별 요약": result.region_alerts}[label]
        path = output_dir / filename; frame.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{label}: {len(frame)}건 → {path}")
    print_user_alerts(result.signals, result.region_alerts)


if __name__ == "__main__":
    main()
