-- 06_triggers.sql
-- All triggers (created after functions exist). Order matters.

BEGIN;

-- Quotes -> Ingresos sync
DROP TRIGGER IF EXISTS trg_quote_sync_ins ON public.quotes;
CREATE TRIGGER trg_quote_sync_ins
  AFTER INSERT ON public.quotes
  FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

DROP TRIGGER IF EXISTS trg_quote_sync_upd ON public.quotes;
CREATE TRIGGER trg_quote_sync_upd
  AFTER UPDATE OF estado, subtotal, fecha_emitido, fecha_aprobado ON public.quotes
  FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

-- Ingreso state change logging
DROP TRIGGER IF EXISTS trg_ingreso_state_log_insert ON public.ingresos;
CREATE TRIGGER trg_ingreso_state_log_insert
  AFTER INSERT ON public.ingresos
  FOR EACH ROW EXECUTE FUNCTION public.log_ingreso_state();

DROP TRIGGER IF EXISTS trg_ingreso_state_log_update ON public.ingresos;
CREATE TRIGGER trg_ingreso_state_log_update
  AFTER UPDATE OF estado ON public.ingresos
  FOR EACH ROW EXECUTE FUNCTION public.log_ingreso_state();

-- Legacy guards cleanup (we allow free transitions as per API rules)
DROP TRIGGER IF EXISTS trg_ingreso_state_guard   ON public.ingresos;
DROP TRIGGER IF EXISTS trg_ingresos_estado_guard ON public.ingresos;
DROP FUNCTION IF EXISTS public.ingreso_state_guard();
DROP FUNCTION IF EXISTS public.validate_ingreso_transition();

-- Audit: append-only protections
DROP TRIGGER IF EXISTS trg_change_log_no_update ON audit.change_log;
CREATE TRIGGER trg_change_log_no_update
  BEFORE UPDATE ON audit.change_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_change_log_mod();

DROP TRIGGER IF EXISTS trg_change_log_no_delete ON audit.change_log;
CREATE TRIGGER trg_change_log_no_delete
  BEFORE DELETE ON audit.change_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_change_log_mod();

DROP TRIGGER IF EXISTS trg_audit_log_no_update ON public.audit_log;
CREATE TRIGGER trg_audit_log_no_update
  BEFORE UPDATE ON public.audit_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_audit_log_mod();

DROP TRIGGER IF EXISTS trg_audit_log_no_delete ON public.audit_log;
CREATE TRIGGER trg_audit_log_no_delete
  BEFORE DELETE ON public.audit_log
  FOR EACH ROW EXECUTE FUNCTION audit.prevent_audit_log_mod();

-- Audit: field-level changeloggers
DROP TRIGGER IF EXISTS trg_audit_customers ON public.customers;
CREATE TRIGGER trg_audit_customers
  AFTER UPDATE OF razon_social, cod_empresa, telefono ON public.customers
  FOR EACH ROW EXECUTE FUNCTION audit.log_customer_change();

DROP TRIGGER IF EXISTS trg_audit_devices ON public.devices;
CREATE TRIGGER trg_audit_devices
  AFTER UPDATE OF numero_serie, n_de_control ON public.devices
  FOR EACH ROW EXECUTE FUNCTION audit.log_device_change();

DROP TRIGGER IF EXISTS trg_audit_ingresos ON public.ingresos;
CREATE TRIGGER trg_audit_ingresos
  AFTER UPDATE OF propietario_nombre, propietario_contacto, propietario_doc,
                  descripcion_problema, trabajos_realizados
  ON public.ingresos
  FOR EACH ROW EXECUTE FUNCTION audit.log_ingreso_change();

COMMIT;

