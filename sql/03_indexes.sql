-- 03_indexes.sql
-- Non-PK indexes to support common UI/API filters and joins.

BEGIN;

-- marcas/models
CREATE INDEX IF NOT EXISTS idx_marcas_tecnico    ON public.marcas(tecnico_id);
CREATE INDEX IF NOT EXISTS idx_models_marca      ON public.models(marca_id);
CREATE INDEX IF NOT EXISTS idx_models_tecnico    ON public.models(tecnico_id);
CREATE INDEX IF NOT EXISTS idx_models_tipo_equipo ON public.models ((COALESCE(tipo_equipo,'')));

-- devices
CREATE INDEX IF NOT EXISTS idx_devices_customer   ON public.devices(customer_id);
CREATE INDEX IF NOT EXISTS idx_devices_marca      ON public.devices(marca_id);
CREATE INDEX IF NOT EXISTS idx_devices_model      ON public.devices(model_id);
CREATE INDEX IF NOT EXISTS idx_devices_nro_serie  ON public.devices(numero_serie);

-- ingresos
CREATE INDEX IF NOT EXISTS idx_ingresos_device     ON public.ingresos(device_id);
CREATE INDEX IF NOT EXISTS idx_ingresos_estado     ON public.ingresos(estado);
CREATE INDEX IF NOT EXISTS idx_ingresos_asignado   ON public.ingresos(asignado_a);
CREATE INDEX IF NOT EXISTS idx_ingresos_ubicacion  ON public.ingresos(ubicacion_id);
CREATE INDEX IF NOT EXISTS idx_vw_general_cliente_estado ON public.ingresos(estado, fecha_ingreso);

-- quotes items
CREATE INDEX IF NOT EXISTS idx_quote_items_quote ON public.quote_items(quote_id);

-- ingreso_events (accelerate last-event lookups per ingreso/state)
CREATE INDEX IF NOT EXISTS idx_events_ingreso ON public.ingreso_events(ingreso_id);
CREATE INDEX IF NOT EXISTS idx_events_ingreso_estado_ts ON public.ingreso_events(ingreso_id, a_estado, ts DESC, id DESC);

-- equipos_derivados
CREATE INDEX IF NOT EXISTS idx_derivados_ingreso   ON public.equipos_derivados(ingreso_id);
CREATE INDEX IF NOT EXISTS idx_derivados_proveedor ON public.equipos_derivados(proveedor_id);
-- prevent duplicates per ingreso/date
CREATE UNIQUE INDEX IF NOT EXISTS uq_equipos_derivados_ingreso_fecha
  ON public.equipos_derivados(ingreso_id, COALESCE(fecha_deriv, DATE '1970-01-01'));

-- handoffs
CREATE INDEX IF NOT EXISTS idx_handoffs_ingreso ON public.handoffs(ingreso_id);

-- password reset tokens
CREATE INDEX IF NOT EXISTS idx_prt_user  ON public.password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_prt_token ON public.password_reset_tokens(token_hash);

-- audit tables
CREATE INDEX IF NOT EXISTS idx_change_log_ingreso ON audit.change_log(ingreso_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_change_log_table   ON audit.change_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_ts       ON public.audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_path     ON public.audit_log(path);
CREATE INDEX IF NOT EXISTS idx_audit_log_user     ON public.audit_log(user_id);

COMMIT;

