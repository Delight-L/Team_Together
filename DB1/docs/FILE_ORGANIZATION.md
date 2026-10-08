# DB1 폴더 구성 및 GitHub 전달

| 위치 | 기능 |
|---|---|
| 루트 run_db1.py/.ps1, run_tests.ps1, db1_store.py, requirements.txt | 공통 실행·저장·검증 |
| config/ | 운영 설정 |
| Analysis1~3/ | 분석 코드·모델·기준 입력·각 분석 산출물 |
| Context/ | 조사·기상·관측 기간·소비 보충 근거 및 재현용 원본 보관 |
| docs/ | 최신 인수인계·실행·해석·검증 안내 |
| outputs/db1.sqlite | 유일한 운영 DB |
| outputs/integrated/ | 통합 CSV 내보내기 |
| outputs/handoff/ | AI 조회 예시, 실제 10건 근거 및 근거별 확인 상태 JSON |
| outputs/figures/ | 보관된 그래프 |
| outputs/validation/, outputs/review/ | 검증·신호 검토 산출물 |
| tests/, 각 모듈 tests/ | 회귀 검증과 필요한 fixtures |
| tools/ | 조회·설명 생성·설정·원본 검증 도구 |

과거 변경 백업은 DB1 바깥의 Team_Together/DB1_backups/prepush_cleanup_<시각>/operational_backups로 이동했다. 이동 전후 파일 해시를 확인했다. 정리 기록은 docs/maintenance/prepush_cleanup_20261007.json이다. 캐시를 삭제했고 루트 인수인계 파일은 docs의 본문을 안내하는 링크 파일로 정리했다. 실행·설정 경로는 유지한다. 같은 내용이라도 검증 시나리오별 산출물과 재실행이 필요한 CSV는 보존한다.

## GitHub 전달

운영 DB는 약361MiB여서 일반 Git 파일의100MiB 한도를 넘는다. DB를 포함하려면 Git LFS 설치·초기화가 필요하며 .gitattributes에 LFS 경로를 지정했다. Git LFS 초기화와 최초 전달 커밋·푸시를 완료했다(커밋 948cf05, delightL 브랜치). 기존 저장소의 attributes가 DB1/** -text를 지정하면 해당 규칙 뒤에 DB1/outputs/db1.sqlite filter=lfs diff=lfs merge=lfs -text를 적용한다. 실제 커밋 전에 git check-attr filter -- DB1/outputs/db1.sqlite로 lfs 적용을 확인한다.

재현에 필요한 모델·reference·fixture·Context 원본 보관본은 이번 정리에서 제거하지 않았다. 원본 수집 폴더는 기존 프로젝트 경로를 사용하며 다른 팀원의 PC에서는 tools/configure_db1.py로 경로를 설정한다. 현재 결과 조회에는 추가 기상 자료가 필요하지 않다. 신규 월 기상 누락 처리와 신규 반기 설정은 현재 운영 코드에서 아직 반영되지 않은 업데이트 준비 항목이다. 격리된 검토 폴더의 미반영 코드를 운영 DB1로 복사하지 않는다.


## 근거별 설명 파일 정리

- `tools/explain_signals.py`: 기존 신호를 읽기 전용으로 설명하는 생성기.
- `tests/test_explain_signals.py`: 기본 `run_tests.ps1`에 포함되는 설명 규칙 검증.
- `docs/ISOLATION_SIGNAL_EXPLANATIONS.md`: 현재 10건의 상태 비교표와 개별 설명.
- `outputs/handoff/isolation_signal_explanations.json`: AI agent가 사용할 `isolation_explanation_v2` 구조화 결과.
- `docs/ISOLATION_EXPLANATION_USAGE.md`: 실행·갱신 방법과 상태 정의.

자체 과거 기준·지역 비교·지속성·보조 근거는 독립 항목이며 군집이나 탐지 기준을 변경하지 않는다. DB 업데이트 완료 뒤 설명 생성기를 실행해 최신 파일을 생성한다. 이 정리의 변경 전 파일은 DB1 바깥 `DB1_backups/explanation_publish_<시각>/`에 보관한다. 기존 GitHub 과거 자료는 archive에 유지한다.


## 기상 추적 최종 파일 구성

- `Context/weather_tracking.py`: 고정 기준의 월별·3개월 계절 비교.
- `Context/tests/test_weather_tracking.py`: 신규 기간·기준 유지·결측·0 분모 검증.
- `Context/outputs/evidence/ctx_weather_*_tracking.csv`: 기간별 원본 JSON 근거·비교 품질·기준 목록을 보존하는 상세 내보내기.
- `Context/outputs/evidence/weather_*_tracking.csv`: 지표별 숫자를 표로 조회할 수 있는 평탄 CSV. 상세 내보내기와 역할이 달라 둘 다 보존한다.
- `docs/WEATHER_TRACKING_RESULT_20261007.md`: 실제 기상 월 6개·행동 관측 창 6개의 결과와 갱신 안내.
- `outputs/handoff/agent_signal_evidence.json`, `isolation_signal_explanations.json`: 기상 비교가 포함된 최신 10건 근거·설명.

현재 코드·운영 DB는 기상 추적을 포함한다. 기상 값이 누락되었을 때 분석을 허용하는 별도의 미반영 코드와는 구분한다. 기존 예시·검증 기록은 참고·이력으로 보존하며 최신 설명은 ISOLATION_SIGNAL_EXPLANATIONS.md를 사용한다. DB 변경 전 백업은 DB1_backups/weather_tracking_<시각>/에, 이번 문서 정리 전 백업은 DB1_backups/weather_publish_<시각>/에 있다.


## 인계 문서 통합 (2026-10-08)

팀원의 연결·조회·설명 규칙과 예시는 `docs/AI_AGENT_HANDOFF.md` 한 문서에 모았다. 별도 QUICKSTART·EXPLANATION_RULES·EXPLANATION_EXAMPLES 문서는 본문을 통합한 후 제거했다. 루트의 같은 이름 파일은 본문으로 연결하는 안내만 제공한다. 분석 결과·검증 기록·업데이트 안내는 각 기능별 기존 위치를 유지한다. 네 지표 수준 추적의 운영 결과는 `docs/ACTIVITY_TRACKING_RESULT_20261007.md`이며 이전 소통 전용 결과는 과거 이력이다.
