-- 07_policies.sql
-- Row Level Security policies. Uses GUCs app.user_id and app.user_role.

BEGIN;

-- Enable RLS where applicable
ALTER TABLE public.ingresos             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quotes               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quote_items          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.equipos_derivados    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.handoffs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proveedores_externos ENABLE ROW LEVEL SECURITY;

-- Optional: service_sheets if present
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='service_sheets'
  ) THEN
    EXECUTE 'ALTER TABLE public.service_sheets ENABLE ROW LEVEL SECURITY';
  END IF;
END $$;

-- Ingresos
DROP POLICY IF EXISTS p_ingresos_select ON public.ingresos;
CREATE POLICY p_ingresos_select ON public.ingresos
  FOR SELECT USING (public.can_view_ingreso(id));

DROP POLICY IF EXISTS p_ingresos_insert ON public.ingresos;
CREATE POLICY p_ingresos_insert ON public.ingresos
  FOR INSERT
  WITH CHECK (current_setting('app.user_role', true) IN ('recepcion','admin','jefe','jefe_veedor'));

DROP POLICY IF EXISTS p_ingresos_update_admin ON public.ingresos;
CREATE POLICY p_ingresos_update_admin ON public.ingresos
  FOR UPDATE
  USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
  WITH CHECK (true);

DROP POLICY IF EXISTS p_ingresos_update_tecnico ON public.ingresos;
CREATE POLICY p_ingresos_update_tecnico ON public.ingresos
  FOR UPDATE
  USING (
    current_setting('app.user_role', true) = 'tecnico'
    AND asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
  )
  WITH CHECK (
    asignado_a = NULLIF(current_setting('app.user_id', true), '')::int
  );

DROP POLICY IF EXISTS p_ingresos_delete ON public.ingresos;
CREATE POLICY p_ingresos_delete ON public.ingresos
  FOR DELETE
  USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- Quotes
DROP POLICY IF EXISTS p_quotes_select ON public.quotes;
CREATE POLICY p_quotes_select ON public.quotes
  FOR SELECT USING (public.can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_quotes_all_admin ON public.quotes;
CREATE POLICY p_quotes_all_admin ON public.quotes
  FOR ALL
  USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
  WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- Quote items
DROP POLICY IF EXISTS p_quote_items_select ON public.quote_items;
CREATE POLICY p_quote_items_select ON public.quote_items
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.quotes q WHERE q.id = quote_id AND public.can_view_ingreso(q.ingreso_id))
  );

DROP POLICY IF EXISTS p_quote_items_all_admin ON public.quote_items;
CREATE POLICY p_quote_items_all_admin ON public.quote_items
  FOR ALL
  USING (
    current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor')
    AND EXISTS (SELECT 1 FROM public.quotes q WHERE q.id = quote_id AND public.can_view_ingreso(q.ingreso_id))
  )
  WITH CHECK (
    current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor')
    AND EXISTS (SELECT 1 FROM public.quotes q WHERE q.id = quote_id AND public.can_view_ingreso(q.ingreso_id))
  );

-- Equipos derivados
DROP POLICY IF EXISTS p_equipos_derivados_select ON public.equipos_derivados;
CREATE POLICY p_equipos_derivados_select ON public.equipos_derivados
  FOR SELECT USING (public.can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_equipos_derivados_all_admin ON public.equipos_derivados;
CREATE POLICY p_equipos_derivados_all_admin ON public.equipos_derivados
  FOR ALL
  USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
  WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- Proveedores externos (catálogo)
DROP POLICY IF EXISTS p_prov_ext_select ON public.proveedores_externos;
CREATE POLICY p_prov_ext_select ON public.proveedores_externos
  FOR SELECT USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor','tecnico','recepcion','auditor'));

DROP POLICY IF EXISTS p_prov_ext_admin ON public.proveedores_externos;
CREATE POLICY p_prov_ext_admin ON public.proveedores_externos
  FOR ALL
  USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
  WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

-- Handoffs
DROP POLICY IF EXISTS p_handoffs_select ON public.handoffs;
CREATE POLICY p_handoffs_select ON public.handoffs
  FOR SELECT USING (public.can_view_ingreso(ingreso_id));

DROP POLICY IF EXISTS p_handoffs_admin ON public.handoffs;
CREATE POLICY p_handoffs_admin ON public.handoffs
  FOR ALL
  USING (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
  WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

COMMIT;

