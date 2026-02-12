-- Crea restriccion de unicidad: max 1 derivacion abierta por ingreso
-- Nota: limpiar duplicados antes de aplicar (scripts/dedupe_derivaciones.py)

CREATE UNIQUE INDEX IF NOT EXISTS uq_equipos_derivados_ingreso_abierto
  ON equipos_derivados(ingreso_id)
  WHERE estado = 'derivado' AND fecha_entrega IS NULL;

