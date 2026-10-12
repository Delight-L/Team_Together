-- 복원 후 welfind_admin으로 실행합니다(migrate_to_oracle.ps1이 자동 실행).
-- 팀원 계정(welfind_reader)은 db1·db2 조회만 가능합니다.
GRANT USAGE ON SCHEMA db1, db2 TO welfind_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA db1, db2 TO welfind_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA db1, db2 TO welfind_reader;
-- 이후 관리자 반영·DB2 수집으로 새 테이블이 생겨도 자동으로 조회 권한을 줍니다.
ALTER DEFAULT PRIVILEGES FOR ROLE welfind_admin IN SCHEMA db1, db2 GRANT SELECT ON TABLES TO welfind_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE welfind_admin IN SCHEMA db1, db2 GRANT SELECT ON SEQUENCES TO welfind_reader;
