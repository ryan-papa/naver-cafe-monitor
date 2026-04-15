     1|#!/bin/bash
     2|mysql -u root -p"$MYSQL_ROOT_PASSWORD" <<-EOSQL
     3|  -- root: localhost만 허용
     4|  DELETE FROM mysql.user WHERE user='root' AND host='%';
     5|
     6|  CREATE USER IF NOT EXISTS 'REDACTED_USER'@'%' IDENTIFIED BY '${DEV_READWRITE_PWD}' REQUIRE X509;
     7|  GRANT ALL PRIVILEGES ON *.* TO 'REDACTED_USER'@'%';
     8|
     9|  CREATE USER IF NOT EXISTS 'REDACTED_USER'@'%' IDENTIFIED BY '${ALL_READONLY_PWD}' REQUIRE X509;
    10|  GRANT SELECT ON *.* TO 'REDACTED_USER'@'%';
    11|
    12|  FLUSH PRIVILEGES;
    13|EOSQL
    14|