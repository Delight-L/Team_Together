#!/bin/bash
# WELFIND 공용 DB(PostgreSQL 18) 설치 스크립트 — Oracle Cloud Ubuntu 22.04/24.04 인스턴스용
#
# 사용법: 인스턴스 생성 화면 > 고급 옵션 표시 > 관리 > "Cloud-init 스크립트 붙여넣기"에
#         이 파일 전체를 붙여 넣습니다. 붙여 넣기 전에 아래 두 비밀번호를 반드시 바꾸세요.
#         (영문·숫자만 20자 이상 권장. 따옴표/$/\ 문자는 쓰지 마세요.)
# 확인:   인스턴스 부팅 5~10분 후, PC에서 python -m backend.db.connection 으로 접속을 확인합니다.
# 로그:   인스턴스 안의 /var/log/cloud-init-output.log
set -euxo pipefail

ADMIN_PASSWORD='CHANGE_ME_ADMIN_PASSWORD'    # 관리자(데이터 반영·DB2 수집) 계정
READER_PASSWORD='CHANGE_ME_READER_PASSWORD'  # 팀원 화면 조회용 읽기 전용 계정
DB_NAME='team_together'
PG_VERSION='18'   # 로컬 PostgreSQL 18.x와 맞춰 덤프 호환성을 보장합니다.

if [[ "$ADMIN_PASSWORD" == CHANGE_ME* || "$READER_PASSWORD" == CHANGE_ME* ]]; then
  echo "비밀번호를 바꾸지 않아 설치를 중단합니다." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl ca-certificates postgresql-common
/usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
apt-get install -y "postgresql-${PG_VERSION}"

# 다른 버전이 이미 있으면 18/main 클러스터가 자동 생성되지 않으므로 직접 만듭니다.
pg_lsclusters --no-header | awk '{print $1"/"$2}' | grep -qx "${PG_VERSION}/main" \
  || pg_createcluster "${PG_VERSION}" main
CONF_DIR="/etc/postgresql/${PG_VERSION}/main"
mkdir -p "${CONF_DIR}/conf.d"
cat > "${CONF_DIR}/conf.d/welfind.conf" <<CONF
listen_addresses = '*'
ssl = on
password_encryption = 'scram-sha-256'
max_connections = 40
shared_buffers = 256MB
log_connections = on
log_disconnections = on
timezone = 'Asia/Seoul'
CONF

# 원격 접속은 SSL + 두 앱 계정 + team_together DB만 허용합니다(postgres 슈퍼유저 원격 접속 불가).
cat >> "${CONF_DIR}/pg_hba.conf" <<HBA
# WELFIND remote access
hostssl ${DB_NAME} welfind_admin,welfind_reader 0.0.0.0/0 scram-sha-256
HBA

systemctl enable postgresql
systemctl restart postgresql

sudo -u postgres psql --cluster "${PG_VERSION}/main" -v ON_ERROR_STOP=1 <<SQL
CREATE ROLE welfind_admin LOGIN PASSWORD '${ADMIN_PASSWORD}';
CREATE ROLE welfind_reader LOGIN PASSWORD '${READER_PASSWORD}' CONNECTION LIMIT 20;
CREATE DATABASE ${DB_NAME} OWNER welfind_admin ENCODING 'UTF8' TEMPLATE template0
  LC_COLLATE 'C.UTF-8' LC_CTYPE 'C.UTF-8';
REVOKE ALL ON DATABASE ${DB_NAME} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${DB_NAME} TO welfind_admin, welfind_reader;
ALTER ROLE welfind_reader SET default_transaction_read_only = on;
ALTER ROLE welfind_reader SET statement_timeout = '30s';
SQL

# Oracle 제공 Ubuntu 이미지는 iptables에 REJECT 규칙이 있어 VCN 보안 목록만 열면 접속되지 않습니다.
# REJECT 위치가 이미지마다 달라(5번·6번 등) 번호를 고정하지 않고 맨 앞에 넣습니다.
iptables -I INPUT -m state --state NEW -p tcp --dport 5432 -j ACCEPT
netfilter-persistent save || (apt-get install -y iptables-persistent && netfilter-persistent save)

echo "WELFIND PostgreSQL 설치 완료"
