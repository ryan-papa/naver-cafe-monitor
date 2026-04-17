#!/bin/bash
set -e

# pg_hba.conf는 command line arg로 직접 지정됨 (-c hba_file=...)
# 그래서 여기서는 유저 생성만 수행

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  CREATE USER rp_readwrite WITH PASSWORD '${RP_READWRITE_PWD}';
  GRANT ALL PRIVILEGES ON DATABASE postgres TO rp_readwrite;
  ALTER USER rp_readwrite CREATEDB;

  CREATE USER rp_readonly WITH PASSWORD '${RP_READONLY_PWD}';
  GRANT CONNECT ON DATABASE postgres TO rp_readonly;

  GRANT ALL ON SCHEMA public TO rp_readwrite;
  GRANT USAGE ON SCHEMA public TO rp_readonly;

  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rp_readwrite;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO rp_readonly;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rp_readwrite;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO rp_readonly;
EOSQL
