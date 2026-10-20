# 팀 문서 안내

처음 참여한 팀원은 **프로젝트 실행 → 개발 안내 → 맡은 영역의 상세 문서** 순서로 읽습니다.
이 폴더의 현재 안내는 아래 8개 파일(이 목차 포함)에서 관리합니다.

| 목적 | 문서 | 내용 |
|---|---|---|
| 문서 찾기 | 이 문서 | 처음 읽을 순서·과거 기록·발표 그림 |
| 코드 수정 | [개발 안내](development-guide.md) | 폴더 역할·읽기 순서·실행·검증·보존 기준 |
| 데이터 운영 | [데이터 운영 안내](data-operations.md) | PostgreSQL 스키마·원자료 갱신·검사·반영·게시·복원 |
| 챗봇 이해 | [보미 챗봇 구조](bomi-architecture.md) | 담당 선택·규제·이벤트·지역 분석 근거 저장소 |
| 화면 수정 | [디자인 규칙](design-rules.md) | 색·상태·글자·스타일 기준 |
| 보고서 수정 | [보고서 작성 안내](report-guide.md) | 근거 선택·AI 대조·저장 차수·Word 템플릿 |
| 복지자료 수집 | [DB2 정기 수집](DB2_지자체복지_정기수집.md) | API 예산·수동 실행·예약 작업·조회 |
| DB 서버 구성 | [클라우드 DB 구축](오라클_클라우드_DB_구축.md) | 기존 OCI 구축 도구·이전·접속 설정 |

## 작업 영역별 상세 안내

[프로젝트 소개·첫 실행](../README.md#13-실행-방법) · [프런트엔드](../frontend/README.md) ·
[백엔드](../backend/README.md) · [파이프라인](../pipelines/README.md) · [DB1 분석 상세](../pipelines/db1/README.md) ·
[Render 배포](../deploy/render.md)

분석별 입력 정의·출처·검증 결과는 `pipelines/db1/`에, 대화 평가 자료는
[지역 분석 평가 폴더](../backend/agents/regional_analysis/evaluation/README.md)에 보존합니다.

## 과거 계획·변경·검증 기록

현재 동작을 설명하는 안내와 당시의 검증 결과를 구분합니다. 아래 문서는 `history/`에서 보존하며
명령·경로·브랜치·테스트 수치는 작성 당시 기준입니다.

- [초기 챗봇 코드 안내](history/chatbot-guide-legacy.md)
- [2026-10-16 변경 기록](history/changes-2026-10-16.md)
- [메뉴 개선 계획과 반영 기록](history/menu-upgrade-plan.md)
- [PostgreSQL 이관·DB1 초기 통합 기록](history/postgresql-migration-2026-10-19.md)
- [2026-10-19 코드·파일 정리](history/repository-cleanup-2026-10-19.md)
- [2026-10-20 코드·이름 정리](history/repository-cleanup-2026-10-20.md)
- [팀원 챗봇 병합 후속 기록](history/shinwon-integration-followups.md)
- [신호 질문 해석 수정 명세](history/spec-fix-signal-query-interpretation.md)
- [자동 연령 변화 패널 제거 명세](history/spec-remove-automatic-age-change-panel.md)

현재 안내는 한 주제당 한 문서에서 관리하고 다른 곳에서는 링크로 연결합니다.
날짜별 작업을 새 최상위 MD로 만들지 않고 위 기록에 추가하거나 `history/`에 보관합니다.
원자료 출처·라이선스·분석 해석 제한은 통합할 때도 유지합니다.

<a id="architecture"></a>

## 발표용 시스템 아키텍처

작업 기준 폴더: `docs/architecture/`

README에서는 **자료 → 분석·수집 → 공유 DB → 대시보드·보미 → 담당자 검토**의 다섯 단계를 보여 줍니다.
슬라이드에 넣을 수 있도록 16:9 비율과 큰 글자로 구성했습니다.

| 파일 | 용도 |
|---|---|
| `system_architecture.png` | README·발표 슬라이드용, 3840 × 2160 |
| `system_architecture.svg` | 편집 가능한 벡터 원본, 1920 × 1080 |

### 발표할 때 설명할 내용

1. 통신·소비·공공자료에서 지역과 인구집단의 변화를 분석합니다.
2. 분석 결과와 복지자원을 공용 PostgreSQL에 저장합니다.
3. 담당자는 대시보드와 보미로 근거를 확인하고, 지원사업과 보고서를 검토합니다.

**분석이 수치를 만들고, 보미가 근거를 설명합니다. 최종 판단은 담당자가 합니다.**

DB1은 분석 결과, DB2는 복지자원, `work`는 업무 기록을 담는 PostgreSQL 스키마입니다.
복지사업 자료는 공공 API와 팀 정리 자료를 함께 표현했습니다. 팀 정리 JSON은 보미가 직접 읽는 참조자료도 포함하므로, 그림은 개별 파일의 저장 경로보다 업무 흐름을 요약합니다.
분석 작업 영역과 서비스 저장소는 모두 PostgreSQL입니다. 현재 스키마 경계는 [저장소 안내](data-operations.md)를 참고하세요.
외부 AI는 선택 기능이며 기본 꺼짐입니다. 보미는 AI를 끄면 자료 검색·규칙 기반 안내를 제공합니다.
구체적인 파일 위치는 [폴더 구성 안내](development-guide.md)를 참고하세요.

### 그림 수정·다시 만들기

`system_architecture.svg`를 수정한 뒤 프로젝트 루트에서 실행합니다.

```powershell
.\scripts\render_architecture.ps1
```

설치된 Chrome으로 SVG를 렌더링하여 PNG를 만듭니다. 기본 배율은 2배입니다.
Chrome 경로가 다르면 `-ChromePath`로 지정합니다.
