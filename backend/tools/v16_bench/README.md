# v16 성능 비교 도구

원본 `backend_old`와 `backend`의 v16 경로를 같은 `db1.sqlite`와 같은 질문으로 비교합니다.
결과 보고서는 [PERFORMANCE_COMPARISON.md](../../PERFORMANCE_COMPARISON.md)입니다.

```bash
# 1) 측정용 복사본 만들기 (원본은 그대로)
python backend/tools/v16_bench/prepare_db.py db1.sqlite  <작업폴더>

# 2) 라운드마다 원본 · PostgreSQL을 번갈아 측정 (3라운드 권장)
python backend/tools/v16_bench/bench.py old <작업폴더>/work/db1-work.sqlite       <작업폴더>/round_old_1.json  15
python backend/tools/v16_bench/bench.py pg  <작업폴더>/snapshots/db1-real.sqlite  <작업폴더>/round_pg_1.json   15

# 3) 보고서 만들기 (make_report.py는 SQLite 서빙이 있던 시절의 4그룹 결과용이라, 이제는 결과 JSON을 직접 비교하세요)
python backend/tools/v16_bench/make_report.py <작업폴더> backend/PERFORMANCE_COMPARISON.md
```

- 의존: 프로젝트 `requirements.txt`의 패키지. PostgreSQL 측정에는 `pip install pgserver`가 더 필요합니다.
- 측정은 질문마다 저장소를 새로 만들고(웹 서비스와 같은 수명), 질문별 출력 해시를 남겨 구현 간 출력이 같은지 함께 확인합니다.
- `old`와 `pg`는 같은 이름의 패키지(`chatbot_agent`)를 쓰므로 반드시 별도 프로세스로 실행합니다(위 명령이 그렇게 되어 있습니다).
- backend의 SQLite 서빙(snapshot·작업 DB 경로)은 제거되어, 과거 보고서 [PERFORMANCE_COMPARISON.md](../../PERFORMANCE_COMPARISON.md)의 해당 열은 **당시 측정값(역사 기록)** 입니다.


## 데이터 준비 메모

받은 `db1.sqlite`는 파이프라인 산출물이라 `pipeline_state`·`ctx_weather`가 없습니다. `prepare_db.py`는 원본을 두고 **복사본에만**
이 둘을 추가하며, `ctx_weather`는 PostgreSQL 게시와 같은 변환 코드(`data_pipeline/db1_compat.py`)로 만듭니다.
`pg` 측정은 이 복사본이 아니라 **받은 원본 파일을 그대로** 게시합니다(원본 `db1.sqlite` 경로를 넘기세요).

> 주의: `old` 측정은 원본 코드가 `backend.…`로 서로를 import하므로, 재현하려면 `backend_old`를 임시로 `backend`라는 이름의 별도 작업 폴더에 두고 실행해야 합니다.
