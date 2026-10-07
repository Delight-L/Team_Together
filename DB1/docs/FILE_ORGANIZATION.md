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
| outputs/handoff/ | AI 조회 예시와 실제10건 근거 JSON |
| outputs/figures/ | 보관된 그래프 |
| outputs/validation/, outputs/review/ | 검증·신호 검토 산출물 |
| tests/, 각 모듈 tests/ | 회귀 검증과 필요한 fixtures |
| tools/ | 조회·설정·원본 검증 도구 |

과거 변경 백업은 DB1 바깥의 Team_Together/DB1_backups/prepush_cleanup_<시각>/operational_backups로 이동했다. 이동 전후 파일 해시를 확인했다. 정리 기록은 docs/maintenance/prepush_cleanup_20261007.json이다. 캐시를 삭제했고 루트 인수인계 파일은 docs의 본문을 안내하는 링크 파일로 정리했다. 실행·설정 경로는 유지한다. 같은 내용이라도 검증 시나리오별 산출물과 재실행이 필요한 CSV는 보존한다.

## GitHub 전달

운영 DB는 약361MiB여서 일반 Git 파일의100MiB 한도를 넘는다. DB를 포함하려면 Git LFS 설치·초기화가 필요하며 .gitattributes에 LFS 경로를 지정했다. 아직 LFS 초기화·커밋·푸시는 수행하지 않았다. 기존 저장소의 attributes가 DB1/** -text를 지정하면 해당 규칙 뒤에 DB1/outputs/db1.sqlite filter=lfs diff=lfs merge=lfs -text를 적용한다. 실제 커밋 전에 git check-attr filter -- DB1/outputs/db1.sqlite로 lfs 적용을 확인한다.

재현에 필요한 모델·reference·fixture·Context 원본 보관본은 이번 정리에서 제거하지 않았다. 원본 수집 폴더는 기존 프로젝트 경로를 사용하며 다른 팀원의 PC에서는 tools/configure_db1.py로 경로를 설정한다. 현재 결과 조회에는 추가 기상 자료가 필요하지 않다. 신규 월 기상 누락 처리와 신규 반기 설정은 현재 운영 코드에서 아직 반영되지 않은 업데이트 준비 항목이다. 격리된 검토 폴더의 미반영 코드를 운영 DB1로 복사하지 않는다.
