-- Agrega triggers de auditoría (change_log) para catálogos y usuarios
-- Ejecutar en PostgreSQL. Idempotente.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_marcas') THEN
    CREATE TRIGGER trg_audit_marcas
    AFTER INSERT OR UPDATE OR DELETE ON marcas
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_models') THEN
    CREATE TRIGGER trg_audit_models
    AFTER INSERT OR UPDATE OR DELETE ON models
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_customers') THEN
    CREATE TRIGGER trg_audit_customers
    AFTER INSERT OR UPDATE OR DELETE ON customers
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_users') THEN
    CREATE TRIGGER trg_audit_users
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_audit_proveedores_externos') THEN
    CREATE TRIGGER trg_audit_proveedores_externos
    AFTER INSERT OR UPDATE OR DELETE ON proveedores_externos
    FOR EACH ROW EXECUTE FUNCTION audit.log_row_change();
  END IF;
END $$;

