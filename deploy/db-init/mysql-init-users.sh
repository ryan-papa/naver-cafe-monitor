#!/bin/bash
mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
  -- root: localhost만 허용
  DELETE FROM mysql.user WHERE user='root' AND host='%';

  CREATE USER IF NOT EXISTS 'rp_readwrite'@'%' IDENTIFIED BY '${RP_READWRITE_PWD}' REQUIRE X509;
  GRANT ALL PRIVILEGES ON *.* TO 'rp_readwrite'@'%';

  CREATE USER IF NOT EXISTS 'rp_readonly'@'%' IDENTIFIED BY '${RP_READONLY_PWD}' REQUIRE X509;
  GRANT SELECT ON *.* TO 'rp_readonly'@'%';

  FLUSH PRIVILEGES;
EOSQL
