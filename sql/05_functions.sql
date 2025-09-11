-- 05_functions.sql
-- All PL/pgSQL and SQL functions needed by triggers and RLS.

BEGIN;

-- Visibility helper for RLS
CREATE OR REPLACE FUNCTION public.can_view_ingreso(tid int)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.ingresos t
    WHERE t.id = tid
      AND (
        current_setting('app.user_role', true) IN ('jefe','jefe_veedor','admin','recepcion','auditor')
        OR (
          current_setting('app.user_role', true) = 'tecnico'
          AND (
            t.asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
            OR t.estado IN ('aprobado','reparar','derivado')
          )
        )
      )
  );
$$;

-- Recalculate quote subtotal for an ingreso
CREATE OR REPLACE FUNCTION public.recalc_quote_subtotal(p_ingreso_id int)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_qid int;
BEGIN
  SELECT id INTO v_qid FROM public.quotes WHERE ingreso_id = p_ingreso_id;
  IF v_qid IS NULL THEN
    INSERT INTO public.quotes(ingreso_id) VALUES (p_ingreso_id)
    ON CONFLICT (ingreso_id) DO NOTHING;
    SELECT id INTO v_qid FROM public.quotes WHERE ingreso_id = p_ingreso_id;
  END IF;

  UPDATE public.quotes q
     SET subtotal = COALESCE((
       SELECT SUM(qi.qty * qi.precio_u)
         FROM public.quote_items qi
        WHERE qi.quote_id = q.id
     ), 0)
   WHERE q.id = v_qid;
END$$;

-- Keep ingreso.presupuesto_estado in sync with quotes.estado (via ingreso_id)
CREATE OR REPLACE FUNCTION public.sync_quote_with_ingreso()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  cur_estado ticket_state;
BEGIN
  SELECT estado INTO cur_estado FROM public.ingresos WHERE id = NEW.ingreso_id FOR UPDATE;

  UPDATE public.ingresos
     SET presupuesto_estado = CASE NEW.estado
                                WHEN 'emitido' THEN 'presupuestado'::quote_state
                                WHEN 'presupuestado' THEN 'presupuestado'::quote_state
                                WHEN 'aprobado' THEN 'aprobado'::quote_state
                                WHEN 'rechazado' THEN 'rechazado'::quote_state
                                ELSE 'pendiente'::quote_state
                              END,
         estado = CASE
                    WHEN NEW.estado = 'aprobado' AND cur_estado IN ('ingresado','diagnosticado','presupuestado')
                    THEN 'reparar'::ticket_state
                    WHEN NEW.estado IN ('emitido','presupuestado') THEN cur_estado
                    ELSE cur_estado
                  END
   WHERE id = NEW.ingreso_id;
  RETURN NEW;
END$$;

-- Log ingreso state changes into ingreso_events (ingreso_id)
CREATE OR REPLACE FUNCTION public.log_ingreso_state()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO public.ingreso_events(ingreso_id, de_estado, a_estado, usuario_id, comentario)
    VALUES (NEW.id, NULL, NEW.estado,
            COALESCE(NEW.recibido_por, NULLIF(current_setting('app.user_id', true), '')::int),
            'Creación de ingreso');
  ELSIF TG_OP = 'UPDATE' AND NEW.estado IS DISTINCT FROM OLD.estado THEN
    INSERT INTO public.ingreso_events(ingreso_id, de_estado, a_estado, usuario_id, comentario)
    VALUES (NEW.id, OLD.estado, NEW.estado,
            COALESCE(NULLIF(current_setting('app.user_id', true), '')::int, COALESCE(NEW.asignado_a, OLD.asignado_a)),
            'Cambio de estado');
  END IF;
  RETURN NEW;
END;
$$;

-- === Audit helpers (schema audit) ===
-- context getters
CREATE OR REPLACE FUNCTION audit._ctx_user_id() RETURNS text LANGUAGE sql AS $$
  SELECT current_setting('app.user_id', true)
$$;
CREATE OR REPLACE FUNCTION audit._ctx_user_role() RETURNS text LANGUAGE sql AS $$
  SELECT current_setting('app.user_role', true)
$$;
CREATE OR REPLACE FUNCTION audit._ctx_ingreso_id() RETURNS integer LANGUAGE sql AS $$
  SELECT NULLIF(current_setting('app.ingreso_id', true), '')::int
$$;

-- protect audit.change_log and public.audit_log as append-only from SQL clients
CREATE OR REPLACE FUNCTION audit.prevent_change_log_mod()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit.change_log is append-only';
  RETURN NULL;
END$$;

CREATE OR REPLACE FUNCTION audit.prevent_audit_log_mod()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
  RETURN NULL;
END$$;

-- field-level changeloggers
CREATE OR REPLACE FUNCTION audit.log_customer_change()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_ingreso int; v_uid text; v_role text; BEGIN
  v_ingreso := audit._ctx_ingreso_id();
  v_uid := audit._ctx_user_id();
  v_role := audit._ctx_user_role();
  IF TG_OP = 'UPDATE' THEN
    IF NEW.razon_social IS DISTINCT FROM OLD.razon_social THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'customers', OLD.id, 'razon_social', OLD.razon_social::text, NEW.razon_social::text);
    END IF;
    IF NEW.cod_empresa IS DISTINCT FROM OLD.cod_empresa THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'customers', OLD.id, 'cod_empresa', OLD.cod_empresa::text, NEW.cod_empresa::text);
    END IF;
    IF NEW.telefono IS DISTINCT FROM OLD.telefono THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'customers', OLD.id, 'telefono', OLD.telefono::text, NEW.telefono::text);
    END IF;
  END IF;
  RETURN NEW; END$$;

CREATE OR REPLACE FUNCTION audit.log_device_change()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_ingreso int; v_uid text; v_role text; BEGIN
  v_ingreso := audit._ctx_ingreso_id();
  v_uid := audit._ctx_user_id();
  v_role := audit._ctx_user_role();
  IF TG_OP = 'UPDATE' THEN
    IF NEW.numero_serie IS DISTINCT FROM OLD.numero_serie THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'devices', OLD.id, 'numero_serie', OLD.numero_serie::text, NEW.numero_serie::text);
    END IF;
    IF NEW.n_de_control IS DISTINCT FROM OLD.n_de_control THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'devices', OLD.id, 'n_de_control', OLD.n_de_control::text, NEW.n_de_control::text);
    END IF;
  END IF;
  RETURN NEW; END$$;

CREATE OR REPLACE FUNCTION audit.log_ingreso_change()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_ingreso int; v_uid text; v_role text; BEGIN
  v_ingreso := COALESCE(audit._ctx_ingreso_id(), NEW.id);
  v_uid := audit._ctx_user_id();
  v_role := audit._ctx_user_role();
  IF TG_OP = 'UPDATE' THEN
    IF NEW.propietario_nombre IS DISTINCT FROM OLD.propietario_nombre THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'propietario_nombre', OLD.propietario_nombre::text, NEW.propietario_nombre::text);
    END IF;
    IF NEW.propietario_contacto IS DISTINCT FROM OLD.propietario_contacto THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'propietario_contacto', OLD.propietario_contacto::text, NEW.propietario_contacto::text);
    END IF;
    IF NEW.propietario_doc IS DISTINCT FROM OLD.propietario_doc THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'propietario_doc', OLD.propietario_doc::text, NEW.propietario_doc::text);
    END IF;
    IF NEW.descripcion_problema IS DISTINCT FROM OLD.descripcion_problema THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'descripcion_problema', OLD.descripcion_problema::text, NEW.descripcion_problema::text);
    END IF;
    IF NEW.trabajos_realizados IS DISTINCT FROM OLD.trabajos_realizados THEN
      INSERT INTO audit.change_log(ingreso_id, user_id, user_role, table_name, record_id, column_name, old_value, new_value)
      VALUES (v_ingreso, v_uid, v_role, 'ingresos', OLD.id, 'trabajos_realizados', OLD.trabajos_realizados::text, NEW.trabajos_realizados::text);
    END IF;
  END IF;
  RETURN NEW; END$$;

-- === Views used by API ===
-- General por cliente
DROP VIEW IF EXISTS public.vw_general_por_cliente;
CREATE VIEW public.vw_general_por_cliente AS
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
FROM public.ingresos t
JOIN public.devices   d ON d.id = t.device_id
JOIN public.customers c ON c.id = d.customer_id
LEFT JOIN public.marcas    b ON b.id = d.marca_id
LEFT JOIN public.models    m ON m.id = d.model_id
LEFT JOIN public.locations l ON l.id = t.ubicacion_id
LEFT JOIN public.quotes    q ON q.ingreso_id = t.id
ORDER BY t.fecha_ingreso DESC;

-- Aprobados/pasar a reparar (opcional)
DROP VIEW IF EXISTS public.vw_aprobados_pendientes;
CREATE VIEW public.vw_aprobados_pendientes AS
SELECT t.*
FROM public.ingresos t
WHERE t.estado IN ('aprobado','reparar');

-- Listos para retiro / liberados (utilizada por la API)
DROP VIEW IF EXISTS public.vw_listos_para_retiro;
CREATE VIEW public.vw_listos_para_retiro AS
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
FROM public.ingresos t
JOIN public.devices   d ON d.id = t.device_id
JOIN public.customers c ON c.id = d.customer_id
LEFT JOIN public.marcas    b ON b.id = d.marca_id
LEFT JOIN public.models    m ON m.id = d.model_id
LEFT JOIN public.locations l ON l.id = t.ubicacion_id
LEFT JOIN LATERAL (
  SELECT e.ts AS fecha_listo
  FROM public.ingreso_events e
  WHERE e.ingreso_id = t.id AND e.a_estado = 'liberado'
  ORDER BY e.ts DESC, e.id DESC
  LIMIT 1
) ev ON TRUE
WHERE t.estado IN ('liberado')
ORDER BY COALESCE(ev.fecha_listo, t.fecha_ingreso) DESC;

COMMIT;
