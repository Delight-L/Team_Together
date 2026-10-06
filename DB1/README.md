# DB1 실행 및 폴더 안내

Analysis1은 반기별 지역유형, Analysis2는 월별 변화 탐지, Analysis3은 분기·월 소비 맥락을 처리합니다. 원본 자료는 프로젝트 바깥의 기존 공모전·서울시 데이터 폴더에서 읽습니다.

## 실행
DB1 폴더의 PowerShell에서 실행합니다.
```powershell
.\run_db1.ps1 -Command status
.\run_db1.ps1 -Command scan
.\run_db1.ps1 -Command export
.\run_tests.ps1
```
`scan`은 새 자료를 전처리하고 DB에 통합한 후 CSV를 갱신합니다. `export`는 저장된 DB 결과를 다시 내보냅니다. `watch`는 실행 중 주기적으로 scan을 반복합니다. Analysis1 특정 반기는 `-Command analysis1 -Period 2026H1`, Analysis2 특정 월은 `-Command analysis2 -Month 2026-01`로 실행합니다. 해당 기간 원본과 공공자료가 준비되어야 합니다.

## 파일 위치
- `config/db1_config.json`: 공통 DB, 원본 및 Analysis1·2 설정.
- `outputs/db1.sqlite`: 세 분석이 공유하는 운영 DB. 유일한 운영 기준입니다.
- `outputs/integrated/`: Analysis1·2 통합 CSV와 Analysis1·2·3 연결 CSV.
- `outputs/figures/`: 기존 분석 그래프 PNG·SVG. CSV 갱신과 별도로 보존된 시각화입니다.
- `Analysis1/data/reference/`: 고정 기준 입력; `models/2025H2/`: 기준 모델.
- `Analysis1/data/processed/<반기>/`: 전처리 입력; `outputs/baseline/`, `outputs/periods/<반기>/`: 분석 결과.
- `Analysis2/data/reference/`: 초기 이력·기준 비교 자료; `outputs/history.csv`, `detection.csv`, `evidence.csv`: DB 결과 내보내기; `outputs/monthly/<월>/`: 월별 특징·탐지 결과.
- `Analysis2/tests/fixtures/`: 테스트에 필요한 작은 원본 예제. 운영 원본 폴더와 구분합니다.
- `Analysis3/config/analysis3_config.json`: 소비 자료·내보내기 설정; `db/schema.sql`: 스키마; `outputs/`: 소비 전처리·분석 결과; `outputs/mappings/`: 동·업종 연결표; `logs/`: 마지막 실행 기록.
- `tests/`, 각 분석의 `tests/`: 검증; `tools/`: 초기 설정·원본 검증 보조 도구; `docs/`: 실행 안내·과거 검증·정리 기록.

이전 중복 DB, 중복 CSV, 구식 일괄 실행기, 대시보드와 보고서는 정리 전 전체 백업에 보관합니다. 과거 검증 문서의 경로는 당시 기록이며 현재 실행 안내는 이 문서입니다. 기준 모델과 운영 DB의 내용은 폴더 정리 과정에서 변경하지 않습니다.
