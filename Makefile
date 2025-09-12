staging-verify:
	@docker compose -f docker-compose.mysql.staging.yml exec -T mysql sh -lc 'export MYSQL_PWD=$$MYSQL_PASSWORD; mysql -u"$$MYSQL_USER" -D "$$MYSQL_DATABASE" < /tmp/mysql/99_verify_mysql.sql'

staging-smokes:
	@docker compose -f docker-compose.mysql.staging.yml exec -T mysql sh -lc 'mysql -u"$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE" -e "SELECT NOW()"'
	@echo "Run DB smokes via the existing SQL block (kept in repo scripts)"; exit 0

staging-health:
	@docker compose -f docker-compose.mysql.staging.yml ps
	@docker compose -f docker-compose.mysql.staging.yml exec -T api curl -sS http://localhost:8000/api/health/ || true
