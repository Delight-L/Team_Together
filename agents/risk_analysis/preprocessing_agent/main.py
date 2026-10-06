"""raw_data 원본 파일 → Analysis1 입력 CSV 변환 실행점."""
import argparse
from pathlib import Path
from preprocessor import preprocess_raw_dir, save, PreprocessError

parser = argparse.ArgumentParser(description="Analysis1 원본 파일 전처리 에이전트")
parser.add_argument("--raw-dir", default="raw_data", help="원본 CSV/XLSX를 넣은 폴더 (기본: raw_data)")
parser.add_argument("--output-dir", default="outputs/analysis1_preprocessed", help="전처리 결과 폴더")
args = parser.parse_args()

try:
    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        raise PreprocessError(f"원본 폴더가 없습니다: {raw_dir}. 프로젝트 안에 raw_data 폴더를 만들고 원본 파일을 넣으세요.")
    base, profile, report = preprocess_raw_dir(raw_dir)
    save(base, profile, report, Path(args.output_dir))
    print("[전처리 완료]")
    print(f"- 분석1 입력: {args.output_dir}/analysis1_input.csv")
    print(f"- 지역 프로필: {args.output_dir}/analysis1_profile.csv")
    print(f"- 검증: 강남구 {report['rows']}개 동, 결측 없음")
except PreprocessError as exc:
    print(f"[전처리 중단] {exc}")
    raise SystemExit(2)
