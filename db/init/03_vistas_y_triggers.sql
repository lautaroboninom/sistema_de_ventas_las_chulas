-- =========================================
-- Log de cambios de estado
-- =========================================
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

-- =========================================
-- Guard: validar transiciones (usa 'ingresado')
-- =========================================
CREATE OR REPLACE FUNCTION validate_ingreso_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  ok boolean := false;
BEGIN
  IF TG_OP = 'INSERT' THEN
    RETURN NEW;
  END IF;

  IF NEW.estado IS NOT DISTINCT FROM OLD.estado THEN
    RETURN NEW;
  END IF;

  -- Reglas simples/adaptables:
  IF OLD.estado = 'ingresado'  AND NEW.estado IN ('asignado','derivado','no_se_repara','rechazado') THEN ok := true; END IF;
  IF OLD.estado = 'asignado'   AND NEW.estado IN ('diagnosticado','derivado','no_se_repara','rechazado') THEN ok := true; END IF;
  IF OLD.estado = 'diagnosticado' AND NEW.estado IN ('aprobado','rechazado','derivado','no_se_repara') THEN ok := true; END IF;
  IF OLD.estado = 'aprobado'   AND NEW.estado IN ('reparar','derivado') THEN ok := true; END IF;
  IF OLD.estado = 'reparar'  AND NEW.estado IN ('reparado','derivado') THEN ok := true; END IF;
  IF OLD.estado = 'reparado'   AND NEW.estado IN ('entregado') THEN ok := true; END IF;
  IF OLD.estado = 'derivado'   AND NEW.estado IN ('reparado','entregado','rechazado','no_se_repara') THEN ok := true; END IF;

  IF NOT ok THEN
    RAISE EXCEPTION 'Transición de estado no permitida: % -> %', OLD.estado, NEW.estado;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ingreso_state_guard ON ingresos;
CREATE TRIGGER trg_ingreso_state_guard
BEFORE UPDATE OF estado ON ingresos
FOR EACH ROW EXECUTE FUNCTION validate_ingreso_transition();

-- =========================================
-- Sincronizar presupuesto_estado con quotes
-- (y, opcionalmente, el estado del ingreso)
-- =========================================
CREATE OR REPLACE FUNCTION sync_ingreso_with_quote()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE ingresos
     SET presupuesto_estado = NEW.estado
   WHERE id = NEW.ingreso_id;

  -- Opcional: reflejar "hitos" en el estado del ingreso
  IF NEW.estado = 'emitido' THEN
    UPDATE ingresos
       SET estado = 'diagnosticado'
     WHERE id = NEW.ingreso_id
       AND estado IN ('ingresado','asignado');
  ELSIF NEW.estado = 'aprobado' THEN
    UPDATE ingresos SET estado = 'aprobado'
     WHERE id = NEW.ingreso_id
       AND estado IN ('diagnosticado','asignado','ingresado');
  ELSIF NEW.estado = 'rechazado' THEN
    UPDATE ingresos SET estado = 'rechazado'
     WHERE id = NEW.ingreso_id
       AND estado IN ('diagnosticado','asignado','ingresado');
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_quote_sync_ins ON quotes;
CREATE TRIGGER trg_quote_sync_ins
AFTER INSERT ON quotes
FOR EACH ROW EXECUTE FUNCTION sync_ingreso_with_quote();

DROP TRIGGER IF EXISTS trg_quote_sync_upd ON quotes;
CREATE TRIGGER trg_quote_sync_upd
AFTER UPDATE OF estado, subtotal ON quotes
FOR EACH ROW EXECUTE FUNCTION sync_ingreso_with_quote();

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

-- Listos para retiro / liberados (reparado o entregado)
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
  COALESCE(l.nombre,'') AS ubicacion_nombre
FROM ingresos t
JOIN devices d   ON d.id = t.device_id
JOIN customers c ON c.id = d.customer_id
LEFT JOIN marcas    b ON b.id = d.marca_id
LEFT JOIN models    m ON m.id = d.model_id
LEFT JOIN locations l ON l.id = t.ubicacion_id
WHERE t.estado IN ('reparar','entregado')
ORDER BY t.id DESC;

-- Índice de soporte a vistas
CREATE INDEX IF NOT EXISTS idx_vw_general_cliente_estado ON ingresos(estado, fecha_ingreso);
