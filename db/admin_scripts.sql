-- =====================================================
-- Admin SQL scripts (idempotentes)
-- Ubicación: db/admin_scripts.sql
--
-- Contiene:
--  A) Sincronización presupuesto (quotes -> ingresos)
--  B) Vista de liberados con fecha_listo
--  C) Backfill de eventos reparado/liberado
--  D) Consultas útiles de auditoría / verificación
-- =====================================================

-- =========================
-- A) Sync presupuesto + triggers
-- =========================
BEGIN;

-- A.1) Asegurar valor 'presupuestado' en quote_state
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname='quote_state') THEN
    BEGIN
      EXECUTE 'ALTER TYPE quote_state ADD VALUE IF NOT EXISTS ''presupuestado''';
    EXCEPTION WHEN duplicate_object THEN NULL; END;
  END IF;
END $$;

-- A.2) Función de sincronización centralizada
CREATE OR REPLACE FUNCTION public.sync_quote_with_ingreso()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  cur_estado ticket_state;
BEGIN
  SELECT estado INTO cur_estado
    FROM public.ingresos
   WHERE id = NEW.ingreso_id
   FOR UPDATE;

  UPDATE public.ingresos
     SET presupuesto_estado = CASE NEW.estado
                                WHEN 'emitido'       THEN 'presupuestado'::quote_state
                                WHEN 'presupuestado' THEN 'presupuestado'::quote_state
                                WHEN 'aprobado'      THEN 'aprobado'::quote_state
                                WHEN 'rechazado'     THEN 'rechazado'::quote_state
                                ELSE 'pendiente'::quote_state
                              END,
        estado = CASE
                   WHEN NEW.estado = 'aprobado'
                        AND cur_estado IN ('ingresado','diagnosticado','presupuestado')
                   THEN 'reparar'::ticket_state
                   WHEN NEW.estado IN ('emitido','presupuestado') THEN cur_estado
                   ELSE cur_estado
                 END
   WHERE id = NEW.ingreso_id;

  RETURN NEW;
END
$$;

-- A.3) Re-enganchar triggers de quotes
DROP TRIGGER IF EXISTS trg_quote_sync_ins ON public.quotes;
CREATE TRIGGER trg_quote_sync_ins
  AFTER INSERT ON public.quotes
  FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

DROP TRIGGER IF EXISTS trg_quote_sync_upd ON public.quotes;
CREATE TRIGGER trg_quote_sync_upd
  AFTER UPDATE OF estado, subtotal, fecha_emitido, fecha_aprobado ON public.quotes
  FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

-- A.4) Limpiar guards viejos y funciones de sync anteriores (si existieran)
DROP TRIGGER  IF EXISTS trg_ingreso_state_guard   ON public.ingresos;
DROP TRIGGER  IF EXISTS trg_ingresos_estado_guard ON public.ingresos;
DROP FUNCTION IF EXISTS public.ingreso_state_guard();
DROP FUNCTION IF EXISTS public.validate_ingreso_transition();
DROP FUNCTION IF EXISTS public.sync_ingreso_with_quote();

-- A.5) Normalizar datos legados (emitido -> presupuestado)
UPDATE public.ingresos
   SET presupuesto_estado = 'presupuestado'
 WHERE presupuesto_estado::text = 'emitido';

COMMIT;


-- =========================
-- B) Vista de liberados con fecha_listo
-- =========================
BEGIN;

-- B.1) Asegurar tabla de eventos (por si faltara)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='ingreso_events'
  ) THEN
    CREATE TABLE public.ingreso_events(
      id serial PRIMARY KEY,
      ingreso_id int NOT NULL REFERENCES public.ingresos(id) ON DELETE CASCADE,
      de_estado ticket_state NULL,
      a_estado  ticket_state NOT NULL,
      usuario_id int NULL REFERENCES public.users(id),
      ts timestamptz NOT NULL DEFAULT now(),
      comentario text
    );
    CREATE INDEX IF NOT EXISTS idx_events_ingreso ON public.ingreso_events(ingreso_id);
  END IF;
END $$;

-- B.2) Recrear vista con fecha_listo (desde ingreso_events)
DROP VIEW IF EXISTS vw_listos_para_retiro;
CREATE VIEW vw_listos_para_retiro AS
SELECT
  t.id, t.estado, t.presupuesto_estado,
  c.razon_social,
  d.numero_serie,
  COALESCE(b.nombre,'') AS marca,
  COALESCE(m.nombre,'') AS modelo,
  t.fecha_ingreso,
  t.ubicacion_id,
  COALESCE(l.nombre,'') AS ubicacion_nombre,
  ev.fecha_listo
FROM ingresos t
JOIN devices   d ON d.id = t.device_id
JOIN customers c ON c.id = d.customer_id
LEFT JOIN marcas    b ON b.id = d.marca_id
LEFT JOIN models    m ON m.id = d.model_id
LEFT JOIN locations l ON l.id = t.ubicacion_id
LEFT JOIN LATERAL (
  SELECT e.ts AS fecha_listo
  FROM ingreso_events e
  WHERE e.ingreso_id = t.id AND e.a_estado = 'liberado'
  ORDER BY e.ts DESC, e.id DESC
  LIMIT 1
) ev ON TRUE
WHERE t.estado = 'liberado'
ORDER BY COALESCE(ev.fecha_listo, t.fecha_ingreso) DESC;

COMMIT;


-- =========================
-- C) Backfill de eventos reparado/liberado (solo si faltan)
-- =========================
BEGIN;

INSERT INTO public.ingreso_events(ingreso_id, de_estado, a_estado, usuario_id, ts, comentario)
SELECT t.id, NULL, 'reparado', NULL, now(), 'Backfill fecha reparado'
FROM public.ingresos t
WHERE t.estado = 'reparado'
  AND NOT EXISTS (
    SELECT 1 FROM public.ingreso_events e
    WHERE e.ingreso_id = t.id AND e.a_estado = 'reparado'
  );

INSERT INTO public.ingreso_events(ingreso_id, de_estado, a_estado, usuario_id, ts, comentario)
SELECT t.id, NULL, 'liberado', NULL, now(), 'Backfill fecha liberado'
FROM public.ingresos t
WHERE t.estado = 'liberado'
  AND NOT EXISTS (
    SELECT 1 FROM public.ingreso_events e
    WHERE e.ingreso_id = t.id AND e.a_estado = 'liberado'
  );

COMMIT;


-- =========================
-- D) Consultas útiles (copiar/pegar)
-- =========================
-- Últimos 200 eventos de estado
-- SELECT * FROM ingreso_events ORDER BY ts DESC, id DESC LIMIT 200;

-- Historial de estado por ingreso
-- SELECT ts, de_estado, a_estado, usuario_id FROM ingreso_events
--  WHERE ingreso_id = 123 ORDER BY ts DESC, id DESC;

-- Auditoría de cambios de campos (si está creada)
-- SELECT ts, user_id, user_role, table_name, record_id, column_name, old_value, new_value
--   FROM audit.change_log
--  WHERE ingreso_id = 123
--  ORDER BY ts DESC, id DESC;

-- Actividad HTTP (si AUDIT_LOG_ENABLED=1)
-- SELECT ts, user_id, role, method, path, status_code FROM public.audit_log
--  ORDER BY ts DESC LIMIT 200;

-- Verificar triggers activos
-- SELECT tgname FROM pg_trigger WHERE tgname IN (
--   'trg_ingreso_state_log_insert','trg_ingreso_state_log_update',
--   'trg_quote_sync_ins','trg_quote_sync_upd'
-- );

