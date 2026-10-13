# 지역 분석 파이프라인

실행점은 `DB1/run_db1.py`와 서비스 반영 어댑터로 연결됩니다.

```powershell
python main.py --analysis --no-download
python main.py --analysis --publish
```

기본 명령은 전달된 Analysis1 elder v2 / Analysis2 CSV를 검사합니다. `--publish`는
서비스 DB에 새 실행 버전으로 반영합니다. 원본 SQLite와 과거 실행은 보존합니다.
신규 반기나 월 분석은 `--command analysis1 --period ...`, `--command analysis2 --month ...`를 사용합니다.
원천자료 설정과 운영 SQLite를 `--config`, `--db`로 지정할 수 있습니다.

이 폴더의 기존 `Analysis2/reference`와 구 실행기는 과거 결과 재현용으로 보존합니다.
신규 순차 분석은 `DB1/Analysis2`를 사용합니다. 기존 위험신호를 임의로 재계산하거나
연간 독거노인 배경자료를 개인 고립 확정값으로 해석하지 않습니다.

상세 실행과 검증 범위는 [DB1 서비스 통합](../../docs/db1-integration.md)을 참고하세요.
