-- Tareas que deben ejecutarse una sola vez en la instalacion del cliente
-- despues de aplicar una actualizacion (reparaciones de datos, republicaciones, etc).
-- El runner (service/post_update_tasks.py) las toma desde aca.

CREATE TABLE IF NOT EXISTS retail_post_update_tasks (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code          TEXT NOT NULL UNIQUE,
  title         TEXT NOT NULL DEFAULT '',
  status        TEXT NOT NULL DEFAULT 'pending',
  attempts      INTEGER NOT NULL DEFAULT 0,
  max_attempts  INTEGER NOT NULL DEFAULT 3,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  result        JSONB,
  last_error    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at    TIMESTAMPTZ,
  finished_at   TIMESTAMPTZ,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_post_update_tasks_status
    CHECK (status IN ('pending', 'running', 'done', 'failed', 'skipped')),
  CONSTRAINT chk_retail_post_update_tasks_attempts
    CHECK (attempts >= 0 AND max_attempts > 0)
);

DROP TRIGGER IF EXISTS trg_retail_post_update_tasks_updated_at ON retail_post_update_tasks;
CREATE TRIGGER trg_retail_post_update_tasks_updated_at
BEFORE UPDATE ON retail_post_update_tasks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_retail_post_update_tasks_status
  ON retail_post_update_tasks(status);

-- Tarea de esta version: republicar en Tienda Nube los productos que quedaron
-- sin publicar por el borrado en cascada de variantes.
INSERT INTO retail_post_update_tasks(code, title, payload)
VALUES (
  'tiendanube_republish_orphan_products_2026_08',
  'Volver a publicar en Tienda Nube los productos que quedaron sin publicar',
  '{"max_products": 200}'::jsonb
)
ON CONFLICT (code) DO NOTHING;
