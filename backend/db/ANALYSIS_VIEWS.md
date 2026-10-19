# 분석 조회 뷰

`analysis_views.sql`은 최신 분석 실행과 동별 최신 지역 유형 조회를 DB에 등록한다.
일반 뷰이므로 분석 결과를 새로 저장하면 다음 조회에 반영되며, 별도 갱신 작업은 없다.
조회 API에서는 테이블 생성이나 뷰 설치를 수행하지 않는다.

## 설치 순서

기존 DB1 테이블이 있는 DB에 설치한다. 프로젝트 루트에서 실행:

```powershell
.venv\Scripts\python.exe scripts/install_analysis_views.py
.venv\Scripts\python.exe scripts/install_analysis_views.py --apply
```

첫 명령은 권한과 기존 데이터 건수만 확인한다. 두 번째 명령은 하나의 트랜잭션으로
뷰를 설치한다. PostgreSQL에서는 `CREATE OR REPLACE VIEW`로 재실행할 수 있다.
기존 테이블과 분석 기록은 변경하지 않는다. 설치 계정은 db1 CREATE 권한과
참조 테이블 SELECT 권한이 필요하다. 뷰 소유권이 다른 경우 소유자 계정으로 적용한다.

반드시 DB 설치 후 변경된 백엔드를 배포한다. 조회 계정이 설치 계정과 다르면
관리자가 해당 계정에 두 뷰의 SELECT 권한을 부여해야 한다.
뷰 정의는 Git에 함께 보관하여 개발·테스트·운영 DB에 같은 정의를 적용한다.

## 적용 범위

- `analysis_repository`: 최신 실행 ID와 최신 지역 유형을 뷰에서 조회.
- `group_repository`: 동일한 최신 지역 유형 뷰를 재사용.
- 이전 파일 저장소 통합 테스트: 동일 SQL로 테스트 DB에 뷰를 설치.

단순 조건 조회와 저장 SQL은 유지한다. 복지 수집 및 보고서 저장을 DB 함수로
옮기는 작업은 이번 변경에 포함하지 않는다.

롤백 시 이전 백엔드를 먼저 배포하면 기존 테이블을 그대로 조회할 수 있다.
추가한 뷰는 남겨 두어도 기존 코드에 영향을 주지 않는다.
