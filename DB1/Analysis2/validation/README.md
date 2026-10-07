# 과거 재현·민감도 검증 재실행

운영 모델을 바꾸지 않는 2025년까지의 사후 검증 스냅샷이다. DB1 루트에서 실행한다. 분석 스크립트는 DB의 feature/raw 데이터를 읽고 별도 검증 산출물만 쓴다. 진단 시나리오를 운영 탐지표로 가져오지 않는다.

```powershell
python Analysis2/validation/run_validation.py
python Analysis2/validation/sns_review.py
python Analysis2/validation/build_report.py
```

`python Analysis2/validation/inspect_layout.py`는 원천 컬럼 설명서를 다시 읽는 선택 단계이며 DB1 상위의 서울시 공공데이터 폴더가 필요하다. 설명서는 수정하지 않는다. pandas/numpy는 기존 Analysis2 실행 환경을 사용한다. 설명서 추출에는 openpyxl이 필요하다.

출력은 `outputs/validation/retrospective_20261007/`다. 재실행은 이 검증 스냅샷 파일들을 갱신한다. docs의 배포 보고서·인계 문서는 검토 후 별도로 갱신해야 한다. 자동 scan/watch에는 연결하지 않았으며 현재 운영 모델·점수·신호는 그대로 유지한다.

검증 범위는 모델 계산의 시간 순서·재현성과 기준 민감도이며 고립 정답 정확도·당시 공개일 기준 실시간 이용 가능성을 검증하지 않는다.
