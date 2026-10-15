# 지역 분석 실행 연결

`python main.py --analysis`의 실행점(`main.py`)과, `python main.py --preprocess`가 쓰는 예전 Analysis2 실행기를 둡니다.
분석 코드 본체는 `pipelines/db1`, 보미의 v16 지역 변화 신호 에이전트는 `backend/agents/regional_v16`에 있습니다.

```powershell
python main.py --analysis --no-download
python main.py --analysis --publish
```

기본 명령은 전달된 Analysis1 elder v2 / Analysis2 CSV를 검사합니다. `--publish`는
서비스 DB에 새 실행 버전으로 반영합니다. 원본 SQLite와 과거 실행은 보존합니다.
신규 반기나 월 분석은 `--command analysis1 --period ...`, `--command analysis2 --month ...`를 사용합니다.
원천자료 설정과 운영 SQLite를 `--config`, `--db`로 지정할 수 있습니다.

## 폴더 구성

| 항목 | 역할 |
|---|---|
| `main.py` | `--analysis` 실행점. `pipelines/db1/run_db1.py`와 `scripts/import_db1.py`를 호출 |
| `Analysis2/` | 예전(전체 기간 일괄) Analysis2 실행기. `--preprocess` 증분 갱신(`pipelines/preprocessing/regional_features/auto_update.py`)이 호출 |

예전 Analysis2의 과거 결과(reference CSV)는 `pipelines/db1/Analysis2/data/reference/`에 같은 파일로 보존되어 있어 이 폴더에서는 지웠습니다.
`Analysis2/outputs/`는 실행할 때 다시 만들어지는 결과라 저장소에 두지 않습니다.
신규 순차 분석은 `pipelines/db1/Analysis2`를 사용합니다. 기존 위험신호를 임의로 재계산하거나
연간 독거노인 배경자료를 개인 고립 확정값으로 해석하지 않습니다.

상세 실행과 검증 범위는 [DB1 서비스 통합](../../docs/db1-integration.md)을 참고하세요.
