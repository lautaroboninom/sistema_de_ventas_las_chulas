#!/bin/sh
set -e
export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
mysql -uroot -D servicio_tecnico < /tmp/ingresos_triage.sql
