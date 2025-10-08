-- Script genérico para unificar clientes duplicados manteniendo un ID destino.
-- Uso con psql:
--   psql -v target_id=157 -v source_id=1591 -v ON_ERROR_STOP=1 -f sql/ops/merge_customers.sql
-- En Docker Compose dev:
--   docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v target_id=157 -v source_id=1591 -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/../ops/merge_customers.sql
-- En Docker Compose prod:
--   docker compose -f docker-compose.prod.yml exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v target_id=157 -v source_id=1591 -v ON_ERROR_STOP=1 -f - < sql/ops/merge_customers.sql

\echo '--- merge_customers: iniciando (source_id=' :source_id ', target_id=' :target_id ')'

BEGIN;

-- Locks mínimos para mover referencias de forma atómica
LOCK TABLE devices    IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE customers  IN ROW EXCLUSIVE MODE;

-- Completar datos vacíos del destino con los del source (sin tocar razon_social)
UPDATE customers t
SET
  cod_empresa = COALESCE(NULLIF(t.cod_empresa, ''), NULLIF(s.cod_empresa, '')),
  telefono    = COALESCE(NULLIF(t.telefono, ''),    NULLIF(s.telefono, '')),
  telefono_2  = COALESCE(NULLIF(t.telefono_2, ''),  NULLIF(s.telefono_2, '')),
  email       = COALESCE(NULLIF(t.email, ''),       NULLIF(s.email, ''))
FROM customers s
WHERE t.id = :target_id AND s.id = :source_id;

-- Reapuntar devices
UPDATE devices
   SET customer_id = :target_id
 WHERE customer_id = :source_id;

-- Eliminar el duplicado
DELETE FROM customers WHERE id = :source_id;

COMMIT;

\echo '--- merge_customers: OK (source eliminado y referencias movidas)'
