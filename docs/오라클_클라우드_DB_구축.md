# 오라클 클라우드 공용 DB 구축 (db1·db2)

로컬 PostgreSQL의 `team_together` DB(db1·db2 스키마, 약 51MB)를 Oracle Cloud(도쿄 리전) VM의 PostgreSQL 18로 옮기고, 팀원은 `.env`만 바꿔 같은 데이터로 대시보드를 봅니다.

## 왜 이 구성인가

- 대시보드 분석 결과 CSV는 Git에서 제외되어, 새로 clone한 PC는 화면이 비어 있었습니다. 이제 `db1.analysis2_detections`를 우선 읽으므로 DB 접속만 되면 CSV 없이 화면이 채워집니다(CSV와 결과 3,080행 동일 확인).
- 코드가 PostgreSQL 문법(jsonb, `ON CONFLICT`, `pg_dump` 복원)을 사용하므로 Oracle Autonomous DB(Oracle SQL)로는 옮길 수 없습니다. VM에 PostgreSQL을 직접 설치합니다.
- OCI의 관리형 "Database with PostgreSQL"은 Always Free가 아니어서 과금됩니다. 시연 규모(51MB)에는 Always Free VM으로 충분합니다.

| 계정 | 용도 | 권한 |
| --- | --- | --- |
| `welfind_reader` | 팀원 화면 조회 | db1·db2 조회만(쓰기 시도 시 오류) |
| `welfind_admin` | 데이터 이전·관리자 DB1 반영·DB2 수집 | team_together 소유자 |
| `postgres` | VM 내부 관리 | 원격 접속 불가 |

원격 접속은 SSL만 허용합니다(`hostssl`). 위 동작은 실제 덤프로 복원 리허설해 확인했습니다.

## 1. VM 만들기 (OCI 콘솔, 약 10분)

1. 콘솔 > Compute > Instances > **Create instance**. 리전: Japan East (Tokyo).
2. Image: **Canonical Ubuntu 24.04**. Shape: **VM.Standard.A1.Flex, 1 OCPU / 6GB** (Always Free 한도 2 OCPU·12GB 이내). A1 용량 부족 오류가 나면 VM.Standard.E2.1.Micro(AMD, Always Free)로 바꿉니다.
3. Networking: 새 VCN·**public subnet**, "Assign a public IPv4 address" 체크.
4. SSH 키: "Generate a key pair"로 개인키를 내려받아 보관합니다(이후 점검용).
5. **Show advanced options > Management > Paste cloud-init script**에 `deploy/oracle/cloud-init-postgres.sh` 내용을 붙여 넣고, 파일 상단의 두 비밀번호를 바꿉니다(영문·숫자 20자 이상, 따옴표·`$`·`\` 금지).
6. Create. 상태가 Running이 되면 **Public IP**를 기록합니다.

## 2. 5432 포트 열기 (VCN 보안 목록)

인스턴스 상세 > Subnet > Security Lists > Default Security List > **Add Ingress Rules**

- Source CIDR: `0.0.0.0/0` (팀원 IP가 고정이면 그 IP/32만 넣는 것이 더 안전합니다)
- IP Protocol: TCP, Destination Port: `5432`

VM 내부 방화벽(iptables)은 cloud-init 스크립트가 엽니다. 둘 중 하나라도 빠지면 접속 시간 초과가 납니다.

## 3. 로컬 데이터 이전 (관리자 PC, 1회)

부팅 후 5~10분 기다린 뒤 프로젝트 루트 PowerShell에서:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\oracle\migrate_to_oracle.ps1 -RemoteHost <Public IP>
```

로컬 postgres 비밀번호와 원격 welfind_admin 비밀번호를 묻습니다. 덤프 → 원격 복원 → 읽기 권한 → 테이블별 행 수 비교(28개)까지 진행하고, 행 수가 다르면 실패로 표시합니다. 로컬 데이터를 갱신한 뒤 다시 실행하면 원격 db1·db2를 덮어씁니다.

## 4. `.env` 바꾸기

팀원(조회):

```
DB_HOST=<Public IP>
DB_PORT=5432
DB_NAME=team_together
DB_USER=welfind_reader
DB_PASSWORD=<reader 비밀번호>
DB_SSLMODE=require
WELFIND_DATA_SOURCE=auto
```

관리자 DB1 반영·DB2 정기 수집을 클라우드에 직접 쓰려면 `DB_USER=welfind_admin`으로 둡니다. 확인: `.venv\Scripts\python.exe -m backend.db.connection` → `DB 연결 성공: 1`.

`WELFIND_DATA_SOURCE`: `auto`(DB 우선, 실패 시 로컬 CSV) / `db`(DB만, 클라우드 점검용) / `csv`(DB 없이 개발).

## 주의

- **비밀번호를 Git에 올리지 마세요.** `.env`는 `.gitignore`에 포함되어 있습니다. GitHub만 보고 들어온 외부인은 DB 비밀번호가 없으므로 이 방식으로는 화면을 볼 수 없습니다. 심사위원 등 외부인에게 보여주려면 앱 자체를 같은 VM에 배포해 URL로 공유하는 편이 맞습니다(DB 포트도 외부에 열 필요가 없어집니다).
- 5432를 `0.0.0.0/0`에 열면 인터넷 전체의 자동 로그인 시도를 받습니다. SSL·scram·강한 비밀번호·읽기 전용 계정으로 위험을 줄였지만, 시연이 끝나면 보안 목록 규칙을 지우거나 IP를 좁히세요.
- 인증서는 Ubuntu 기본 자체 서명(snakeoil)이라 `require`는 암호화만 하고 서버 신원은 검증하지 않습니다. 필요하면 인증서를 교체하고 `DB_SSLMODE=verify-full`, `DB_SSLROOTCERT`를 사용합니다.
- Always Free 인스턴스는 사용률이 계속 낮으면 Oracle이 회수할 수 있습니다. 로컬 DB를 원본으로 유지하고, 회수되면 1~3단계를 다시 실행합니다.
- 서울-도쿄 왕복 지연 때문에 최신 run_id는 60초마다 한 번 확인하고, 같은 run_id의 결과는 메모리에 캐시합니다.
