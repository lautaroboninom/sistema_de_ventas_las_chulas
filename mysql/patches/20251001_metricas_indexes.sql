-- Índices para métricas y timelines
-- Ejecutar de forma idempotente en MySQL 8+

-- ingreso_events por (ingreso_id, a_estado, ts)
CREATE INDEX IF NOT EXISTS ix_events_ingreso_estado_ts
  ON ingreso_events (ingreso_id, a_estado, ts);

-- ingresos por asignado/estado
CREATE INDEX IF NOT EXISTS ix_ingresos_asignado_estado
  ON ingresos (asignado_a, estado);

-- quotes por fechas
CREATE INDEX IF NOT EXISTS ix_quotes_emitido
  ON quotes (fecha_emitido);
CREATE INDEX IF NOT EXISTS ix_quotes_aprobado
  ON quotes (fecha_aprobado);

