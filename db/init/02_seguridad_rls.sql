-- =========================================
-- RLS + políticas usando variables de sesión
--   SET app.user_id  = '123';
--   SET app.user_role = 'tecnico'|'jefe'|'jefe_veedor'|'admin'|'recepcion'|'auditor';
-- =========================================

-- Función central de visibilidad por ingreso
CREATE OR REPLACE FUNCTION can_view_ingreso(tid int)
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM ingresos t
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

-- Activar RLS
ALTER TABLE ingresos            ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes              ENABLE ROW LEVEL SECURITY;
ALTER TABLE quote_items         ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_sheets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipos_derivados   ENABLE ROW LEVEL SECURITY;
ALTER TABLE handoffs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE proveedores_externos ENABLE ROW LEVEL SECURITY;

-- =========================================
-- Políticas: INGRESOS
-- =========================================
DROP POLICY IF EXISTS p_ingresos_select ON ingresos;
CREATE POLICY p_ingresos_select ON ingresos
FOR SELECT
USING (can_view_ingreso(id));

DROP POLICY IF EXISTS p_ingresos_insert ON ingresos;
CREATE POLICY p_ingresos_insert ON ingresos
FOR INSERT
WITH CHECK (current_setting('app.user_role', true) IN ('recepcion','admin','jefe','jefe_veedor'));

DROP POLICY IF EXISTS p_ingresos_update_admin ON ingresos;
CREATE POLICY p_ingresos_update_admin ON ingresos
FOR UPDATE
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
WITH CHECK (true);

DROP POLICY IF EXISTS p_ingresos_update_tecnico ON ingresos;
CREATE POLICY p_ingresos_update_tecnico ON ingresos
FOR UPDATE
USING (
  current_setting('app.user_role', true) = 'tecnico'
  AND asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
)
WITH CHECK (
  asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
);

DROP POLICY IF EXISTS p_ingresos_delete ON ingresos;
CREATE POLICY p_ingresos_delete ON ingresos
FOR DELETE
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- =========================================
-- Políticas: QUOTES
-- =========================================
DROP POLICY IF EXISTS p_quotes_select ON quotes;
CREATE POLICY p_quotes_select ON quotes
FOR SELECT
USING (can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_quotes_all_admin ON quotes;
CREATE POLICY p_quotes_all_admin ON quotes
FOR ALL
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- =========================================
-- Políticas: QUOTE_ITEMS
-- =========================================
DROP POLICY IF EXISTS p_quote_items_select ON quote_items;
CREATE POLICY p_quote_items_select ON quote_items
FOR SELECT
USING (
  EXISTS (SELECT 1 FROM quotes q WHERE q.id = quote_id AND can_view_ingreso(q.ingreso_id))
);

DROP POLICY IF EXISTS p_quote_items_all_admin ON quote_items;
CREATE POLICY p_quote_items_all_admin ON quote_items
FOR ALL
USING (
  current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor')
  AND EXISTS (SELECT 1 FROM quotes q WHERE q.id = quote_id AND can_view_ingreso(q.ingreso_id))
)
WITH CHECK (
  current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor')
  AND EXISTS (SELECT 1 FROM quotes q WHERE q.id = quote_id AND can_view_ingreso(q.ingreso_id))
);

-- =========================================
-- Políticas: SERVICE_SHEETS
-- =========================================
DROP POLICY IF EXISTS p_service_sheets_select ON service_sheets;
CREATE POLICY p_service_sheets_select ON service_sheets
FOR SELECT
USING (can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_service_sheets_all ON service_sheets;
CREATE POLICY p_service_sheets_all ON service_sheets
FOR ALL
USING (
  current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor','tecnico')
  AND (
    current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor')
    OR EXISTS (
      SELECT 1 FROM ingresos t
      WHERE t.id = service_sheets.ingreso_id
        AND t.asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
    )
  )
)
WITH CHECK (
  current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor')
  OR EXISTS (
    SELECT 1 FROM ingresos t
    WHERE t.id = service_sheets.ingreso_id
      AND t.asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
  )
);

-- =========================================
-- Políticas: EQUIPOS_DERIVADOS (nuevo)
-- =========================================
DROP POLICY IF EXISTS p_equipos_derivados_select ON equipos_derivados;
CREATE POLICY p_equipos_derivados_select ON equipos_derivados
FOR SELECT
USING (can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_equipos_derivados_all_admin ON equipos_derivados;
CREATE POLICY p_equipos_derivados_all_admin ON equipos_derivados
FOR ALL
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- =========================================
-- Políticas: PROVEEDORES_EXTERNOS (catálogo)
-- =========================================
DROP POLICY IF EXISTS p_prov_ext_select ON proveedores_externos;
CREATE POLICY p_prov_ext_select ON proveedores_externos
FOR SELECT
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor','tecnico','recepcion','auditor'));

DROP POLICY IF EXISTS p_prov_ext_admin ON proveedores_externos;
CREATE POLICY p_prov_ext_admin ON proveedores_externos
FOR ALL
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- =========================================
-- Políticas: HANDOFFS
-- =========================================
DROP POLICY IF EXISTS p_handoffs_select ON handoffs;
CREATE POLICY p_handoffs_select ON handoffs
FOR SELECT
USING (can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_handoffs_admin ON handoffs;
CREATE POLICY p_handoffs_admin ON handoffs
FOR ALL
USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));
