# 평가 데이터셋 위치

이 폴더에 메인 프로젝트 DB를 기준으로 검증된 JSONL 데이터셋을 둡니다.

각 줄은 다음 필드를 가져야 합니다.

```json
{"case_id":"B01","path_id":"PATH-01","task_id":"TASK-01","question":"...","reference_answer":"..."}
```

현재 기존 64개 데이터셋은 다른 DB 스냅샷으로 작성되어 있어 이 폴더에 복사하지 않았습니다. `validate_dataset.py`로 검증한 뒤 넣습니다.
