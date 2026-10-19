# 팀 문서 안내

| 문서 | 내용 |
|---|---|
| [프로젝트 소개·실행](../README.md) | 전체 개요와 최초 실행 |
| [프런트엔드](../frontend/README.md) | 화면 개발·빌드·지도 출처 |
| [백엔드](../backend/README.md) | API·보미·에이전트 |
| [파이프라인](../pipelines/README.md) | 전처리·분석·수집 |
| [DB1 상세 안내](../pipelines/db1/README.md) | 분석별 실행·해석·검증 |
| [폴더 구성](folder-organization.md) | 폴더 역할과 이동 이력 |
| [코드 읽기·가독성 기준](code-reading-guide.md) | 초급 개발자의 읽기 순서·DB 조회 흐름·파일 정리 기준 |
| [2026-10-19 코드·파일 정리](repository-cleanup-2026-10-19.md) | 정리 대상·이동 내역·검증·남은 기능 문제 |
| [DB1 서비스 통합](db1-integration.md) | 검사·서비스 DB 반영 |
| [디자인 규칙](design-rules.md) | 화면 디자인 기준 |
| [보고서 에이전트](report-agent.md) | 보고서 생성과 검토 |
| [보미 챗봇 구조](bomi-architecture.md) | 요청 흐름·규제·이벤트 계약·v16 저장소 |

| [PostgreSQL 저장소](postgresql-storage.md) | 분석·전처리·서비스 스키마와 원문 보존·복원 |

## README 관리 기준

README는 루트와 주요 작업 영역에 둡니다. 작은 하위 폴더 설명은 해당 영역 README에 합치고, 긴 설계·검증 문서는 목적에 맞는 이름의 문서로 관리합니다. 같은 실행 절차를 여러 곳에 복사하기보다 담당 문서로 연결합니다. 데이터 출처·라이선스와 분석 해석 제한은 통합할 때도 보존합니다.

## 문서 목차

- [발표용 시스템 아키텍처](#architecture)

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
분석 작업 영역과 서비스 저장소는 모두 PostgreSQL입니다. 현재 스키마 경계는 [저장소 안내](postgresql-storage.md)를 참고하세요.
외부 AI는 선택 기능이며 기본 꺼짐입니다. 보미는 AI를 끄면 자료 검색·규칙 기반 안내를 제공합니다.
구체적인 파일 위치는 [폴더 구성 안내](folder-organization.md)를 참고하세요.

### 그림 수정·다시 만들기

`system_architecture.svg`를 수정한 뒤 프로젝트 루트에서 실행합니다.

```powershell
.\scripts\render_architecture.ps1
```

설치된 Chrome으로 SVG를 렌더링하여 PNG를 만듭니다. 기본 배율은 2배입니다.
Chrome 경로가 다르면 `-ChromePath`로 지정합니다.
