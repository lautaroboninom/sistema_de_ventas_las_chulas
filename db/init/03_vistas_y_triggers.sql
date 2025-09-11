-- Asegurar tabla de eventos antes de referenciarla desde triggers/funciones
DO $$ BEGIN
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

CREATE OR REPLACE FUNCTION log_ingreso_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO ingreso_events(ingreso_id, de_estado, a_estado, usuario_id, comentario)
    VALUES (NEW.id, NULL, NEW.estado,
            COALESCE(NEW.recibido_por, NULLIF(current_setting('app.user_id', true), '')::int),
            'Creación de ingreso');
  ELSIF TG_OP = 'UPDATE' AND NEW.estado IS DISTINCT FROM OLD.estado THEN
    INSERT INTO ingreso_events(ingreso_id, de_estado, a_estado, usuario_id, comentario)
    VALUES (NEW.id, OLD.estado, NEW.estado,
            COALESCE(NULLIF(current_setting('app.user_id', true), '')::int, COALESCE(NEW.asignado_a, OLD.asignado_a)),
            'Cambio de estado');
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ingreso_state_log_insert ON ingresos;
CREATE TRIGGER trg_ingreso_state_log_insert
AFTER INSERT ON ingresos
FOR EACH ROW EXECUTE FUNCTION log_ingreso_state();

DROP TRIGGER IF EXISTS trg_ingreso_state_log_update ON ingresos;
CREATE TRIGGER trg_ingreso_state_log_update
AFTER UPDATE OF estado ON ingresos
FOR EACH ROW EXECUTE FUNCTION log_ingreso_state();

-- No volver a crear guardas de transición: se permite setear libremente
DROP TRIGGER IF EXISTS trg_ingreso_state_guard ON ingresos;
DROP FUNCTION IF EXISTS validate_ingreso_transition();

-- Usar la función nueva centralizada (definida en 01_schema.sql)
DROP TRIGGER IF EXISTS trg_quote_sync_ins ON quotes;
CREATE TRIGGER trg_quote_sync_ins
AFTER INSERT ON quotes
FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

DROP TRIGGER IF EXISTS trg_quote_sync_upd ON quotes;
CREATE TRIGGER trg_quote_sync_upd
AFTER UPDATE OF estado, subtotal, fecha_emitido, fecha_aprobado ON quotes
FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

-- =========================================
-- Vistas operativas (nombres consistentes)
-- =========================================

-- General por cliente
DROP VIEW IF EXISTS vw_general_por_cliente;
CREATE VIEW vw_general_por_cliente AS
SELECT
  t.id,
  d.customer_id,
  c.razon_social,
  d.numero_serie,
  COALESCE(b.nombre,'') AS marca,
  COALESCE(m.nombre,'') AS modelo,
  t.estado,
  t.presupuesto_estado,
  t.fecha_ingreso,
  t.ubicacion_id,
  COALESCE(l.nombre,'') AS ubicacion_nombre,
  GREATEST(
    t.fecha_ingreso,
    COALESCE(q.fecha_emitido,  'epoch'::timestamptz),
    COALESCE(q.fecha_aprobado, 'epoch'::timestamptz)
  ) AS fecha_actualizacion
FROM ingresos t
JOIN devices d   ON d.id = t.device_id
JOIN customers c ON c.id = d.customer_id
LEFT JOIN marcas    b ON b.id = d.marca_id
LEFT JOIN models    m ON m.id = d.model_id
LEFT JOIN locations l ON l.id = t.ubicacion_id
LEFT JOIN quotes q    ON q.ingreso_id = t.id
ORDER BY t.fecha_ingreso DESC;

-- (Opcional) Aprobados/reparar para técnicos
DROP VIEW IF EXISTS vw_aprobados_pendientes;
CREATE VIEW vw_aprobados_pendientes AS
SELECT t.*
FROM ingresos t
WHERE t.estado IN ('aprobado','reparar');

  -- Listos para retiro / liberados
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
JOIN devices d   ON d.id = t.device_id
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
  WHERE t.estado IN ('liberado')
ORDER BY COALESCE(ev.fecha_listo, t.fecha_ingreso) DESC;

-- Índice de soporte a vistas
CREATE INDEX IF NOT EXISTS idx_vw_general_cliente_estado ON ingresos(estado, fecha_ingreso);
