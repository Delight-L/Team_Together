# v16 평가 자료와 검토 도구

이 폴더는 질문 데이터셋과 과거 평가·사용자 검토 기록을 보관합니다.
2026-10-14의 64개 결과와 10-15의 32개 데이터셋은 현재 병합된 보미의 검증 결과가 아닙니다.
당시 실행기의 선행 대화·화면 선택 누락 등은 [평가 상태 기록](EVALUATION_STATUS.md)을 보세요.

## 현재 사용할 수 있는 도구

아래 명령은 프로젝트 루트 기준입니다. 결과 변환은 입력 파일을 읽고 지정한 출력만 만듭니다.

```powershell
python backend/agents/regional_analysis/evaluation/validate_dataset.py backend/agents/regional_analysis/evaluation/datasets/v16_questions_32.jsonl
python backend/agents/regional_analysis/evaluation/make_human_report.py --help
python backend/agents/regional_analysis/evaluation/make_case_guide.py --help
python backend/agents/regional_analysis/evaluation/report32.py --help
python backend/agents/regional_analysis/evaluation/summarize_human_review.py --help
```

`validate_dataset.py`는 단계·필수 필드·사례 구성을 검사합니다. 실제 답변의 정확성을 검증하거나
공유 DB와 데이터셋의 근거가 같은지 보장하지 않습니다.

## 과거 실행기·메타데이터

현재 실행 경로와 연결되지 않는 실행기와 예전 데이터셋 메타데이터는 PostgreSQL `db1_regional_archive.source_archive`에 원문·해시를 보존한 뒤 제거했습니다. `python scripts/read_source_archive.py --list`로 목록을 확인할 수 있습니다.

## 결과 해석

- `datasets/`, `DATASET32_DB_AUDIT.*`, `results/` 및 휴먼 리뷰는 그대로 보존합니다.
- BLEU·ROUGE는 표현 유사도이며 정답률이 아닙니다.
- 과거 사용자 판정은 새 답변에 자동으로 승계하지 않습니다.
- 브라우저·HTTP·대화 상태까지 포함한 현재 서비스 검증과 과거 구성요소 평가를 구분합니다.
