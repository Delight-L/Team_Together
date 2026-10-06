# 집에서 DBeaver로 `team_together` PostgreSQL 접속하기

## 현재 확인된 환경

- 프로젝트의 DB 접속 정보는 저장소 루트의 `.env.team_together`에 있습니다.
- DB 종류는 PostgreSQL입니다.
- `PGHOST`는 사설망 IP입니다. 현재 작업 장소에서는 DB 포트에 접속할 수 있지만, 일반적인 가정 인터넷에서는 이 주소에 바로 접속할 수 없습니다.
- `.env.team_together`는 Git에서 제외되어 있습니다. 이 파일과 비밀번호를 Git, 메신저 공개 채널, 이메일에 올리지 마세요.

따라서 집에서는 먼저 현재 DB가 있는 내부망에 안전하게 접속해야 합니다. 권장 순서는 다음과 같습니다.

1. 조직에서 제공하는 VPN 사용
2. VPN이 없다면 관리자와 협의하여 Tailscale 같은 사설 VPN 사용
3. 이미 외부 접속 가능한 SSH 서버가 있다면 DBeaver의 SSH 터널 사용

PostgreSQL 포트를 공유기에서 인터넷에 직접 공개하는 방식은 사용하지 않습니다.

## 준비물

- 집 컴퓨터에 설치한 DBeaver
- PostgreSQL 드라이버(DBeaver가 최초 연결 시 설치 안내)
- `.env.team_together`에 있는 다음 값
  - `PGHOST`: DB 서버 주소
  - `PGPORT`: DB 포트
  - `PGDATABASE`: 데이터베이스 이름
  - `PGUSER`: 사용자 이름
  - `PGPASSWORD`: 비밀번호
  - `PGSSLMODE`: 설정되어 있을 때만 사용
- VPN 계정 또는 SSH 접속 정보
- DB 서버가 켜져 있고 PostgreSQL이 실행 중이어야 함

접속 정보는 담당자에게 안전한 방법으로 전달받습니다. 집 컴퓨터에는 프로젝트 저장소를 복제한 뒤 `.env.team_together`를 직접 새로 만들거나, DBeaver에만 값을 입력해도 됩니다.

## 방법 A: VPN으로 연결하기(권장)

### 1. VPN 연결 확인

조직에서 제공받은 VPN 클라이언트를 설치하고 내부망에 연결합니다. Tailscale을 쓰는 경우 DB 서버와 집 컴퓨터를 같은 Tailnet에 등록하고, `PGHOST`에는 기존 사설 IP 대신 DB 서버의 Tailscale IP 또는 MagicDNS 이름을 사용합니다.

PowerShell에서 다음 명령으로 DB 포트까지 연결되는지 확인합니다. 실제 값은 `.env.team_together`의 값으로 바꿉니다.

```powershell
Test-NetConnection -ComputerName <PGHOST> -Port <PGPORT>
```

`TcpTestSucceeded : True`이면 DBeaver 설정으로 진행합니다. `False`이면 DBeaver 문제가 아니라 VPN 경로, 서버 방화벽, PostgreSQL 실행 상태 중 하나를 먼저 확인해야 합니다.

### 2. DBeaver 연결 생성

1. DBeaver에서 **Database > New Database Connection**을 선택합니다.
2. **PostgreSQL**을 선택합니다.
3. **Main** 탭에 다음 값을 입력합니다.

| DBeaver 항목 | 입력할 값 |
|---|---|
| Host | `.env.team_together`의 `PGHOST` |
| Port | `.env.team_together`의 `PGPORT` |
| Database | `.env.team_together`의 `PGDATABASE` |
| Username | `.env.team_together`의 `PGUSER` |
| Password | `.env.team_together`의 `PGPASSWORD` |

4. `PGSSLMODE` 값이 있다면 **SSL** 설정에서 같은 정책을 적용합니다. 현재 프로젝트 설정에는 별도 SSL 모드가 지정되어 있지 않으므로 VPN 내부 연결을 전제로 합니다.
5. **Test Connection**을 누릅니다.
6. 연결 테스트가 성공하면 **Finish**를 누릅니다.

집 컴퓨터가 개인 전용이고 Windows 로그인이 보호되는 경우에만 비밀번호 저장을 선택하세요.

## 방법 B: DBeaver SSH 터널 사용하기

이 방법은 외부에서 접속 가능한 SSH 서버가 이미 있고, 그 서버에서 PostgreSQL 사설 주소에 접근할 수 있을 때 사용합니다. SSH 서버가 없다면 이 문서만으로 새 공개 서버를 만들지 말고 관리자와 VPN 구성을 먼저 협의하세요.

1. 새 PostgreSQL 연결을 만들고 **Main** 탭에 `.env.team_together`의 DB 정보를 입력합니다.
2. 연결 설정의 **SSH** 탭에서 **Use SSH Tunnel**을 켭니다.
3. 다음 SSH 정보를 입력합니다.

| SSH 항목 | 설명 |
|---|---|
| Host/IP | 외부에서 접속 가능한 SSH 서버 주소 |
| Port | 보통 `22`, 실제 서버 설정을 따름 |
| User name | SSH 사용자 계정 |
| Authentication | 가능하면 개인 키 사용 |

4. SSH 연결 테스트 후 PostgreSQL **Test Connection**을 실행합니다.

SSH 서버에서 DB 서버를 바라볼 때 주소가 다르다면 **Main > Host**에는 SSH 서버 기준으로 접근 가능한 DB 주소를 넣습니다. PostgreSQL과 SSH가 같은 서버에서 실행된다면 보통 `127.0.0.1`을 사용합니다.

## 서버 관리자 확인 사항

VPN에 연결했는데도 접속이 안 되면 서버 담당자가 다음 항목을 확인해야 합니다.

- PostgreSQL 서비스가 실행 중인지
- PostgreSQL `listen_addresses`가 필요한 네트워크 인터페이스를 허용하는지
- `pg_hba.conf`가 해당 DB 사용자와 VPN 대역의 접속을 허용하는지
- 서버 방화벽이 `PGPORT`를 VPN 대역에서만 허용하는지
- DB 사용자가 `team_together` 데이터베이스에 필요한 권한을 가졌는지

설정을 변경한 경우 PostgreSQL reload 또는 restart가 필요할 수 있습니다. 허용 범위는 집의 수시로 바뀌는 공인 IP보다 VPN 대역으로 제한하는 편이 관리하기 쉽습니다.

## 연결 오류별 점검

| 오류 또는 증상 | 확인할 내용 |
|---|---|
| Connection timed out | VPN 연결, `PGHOST`, 방화벽, 서버 전원 확인 |
| Connection refused | PostgreSQL 실행 상태, `PGPORT`, `listen_addresses` 확인 |
| no pg_hba.conf entry | 서버에서 VPN 대역과 DB 사용자를 허용하도록 설정 요청 |
| password authentication failed | `PGUSER`와 `PGPASSWORD` 재확인 |
| database does not exist | `PGDATABASE` 철자 확인 |
| SSL 관련 오류 | `PGSSLMODE`와 DBeaver SSL 설정을 서버 정책에 맞춤 |
| 회사에서는 되지만 집에서는 안 됨 | 사설망 주소에 직접 연결 중인지 확인하고 VPN/SSH 터널부터 연결 |

## 연결 후 확인용 SQL

DBeaver의 SQL Editor에서 다음 쿼리를 실행합니다.

```sql
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
```

`current_database()`와 `current_user`가 의도한 값이면 정상 연결입니다. 쓰기 권한이 꼭 필요한 상황이 아니라면 데이터 변경 쿼리 대신 아래처럼 조회만 먼저 시험합니다.

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name;
```

## 가장 짧은 실행 순서

1. DB 서버를 켜고 PostgreSQL 실행 상태를 확인합니다.
2. 집 컴퓨터에서 VPN에 연결합니다.
3. `Test-NetConnection`으로 DB 포트 접근을 확인합니다.
4. DBeaver에 `.env.team_together`의 값을 입력합니다.
5. **Test Connection**을 실행합니다.
6. 확인용 SQL을 실행합니다.

