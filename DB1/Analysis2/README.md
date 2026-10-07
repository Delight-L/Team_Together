# Analysis2

초기 2022-01~2025-06 이력은 data/reference에 보관합니다. 새로운 월은 기존 이력으로 변화를 탐지한 뒤 운영 DB에 통합합니다. outputs/history.csv·detection.csv·evidence.csv와 monthly/<월>은 DB에서 내보낸 결과입니다.

공통 실행은 상위 README.md의 run_db1.ps1을 사용합니다. 테스트는 tests 폴더에서 실행합니다.


## 동·연령대별 전처리 이력

2022-01~2025-12 원본에서 연령별 이력을 재구축했습니다. 기준선/업데이트 구간, DB 표, 신규 월 추가 및 해석 범위는 [AGE_PREPROCESSING.md](AGE_PREPROCESSING.md)를 확인하세요. 연령별 탐지를 추가했습니다. [AGE_DETECTION.md](AGE_DETECTION.md)를 확인하세요.
