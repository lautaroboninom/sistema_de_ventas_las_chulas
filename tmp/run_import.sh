#!/bin/sh
set -e

cat > /tmp/my.cnf <<EOF
[client]
user=$MYSQL_USER
password=$MYSQL_PASSWORD
local-infile=1
EOF

mysql --defaults-extra-file=/tmp/my.cnf -D servicio_tecnico < /tmp/load_all.sql

rm -f /tmp/my.cnf
