-- mysql/05_triggers.sql
-- Triggers de auditoría y sincronización

DELIMITER $$

-- Auditoría de estado de ingresos (INSERT)
DROP TRIGGER IF EXISTS trg_ingreso_state_log_insert $$
CREATE TRIGGER trg_ingreso_state_log_insert
AFTER INSERT ON ingresos
FOR EACH ROW
BEGIN
  CALL sp_log_ingreso_state(NEW.id, NULL, NEW.estado, NEW.recibido_por, 'Creación de ingreso');
END $$

-- Auditoría de estado de ingresos (UPDATE de estado)
DROP TRIGGER IF EXISTS trg_ingreso_state_log_update $$
CREATE TRIGGER trg_ingreso_state_log_update
AFTER UPDATE ON ingresos
FOR EACH ROW
BEGIN
  IF (NEW.estado <> OLD.estado) THEN
    CALL sp_log_ingreso_state(NEW.id, OLD.estado, NEW.estado, COALESCE(NEW.asignado_a, OLD.asignado_a), 'Cambio de estado');
  END IF;
END $$

-- Sync de quote → ingreso (insert y update)
DROP TRIGGER IF EXISTS trg_quote_sync_ins $$
CREATE TRIGGER trg_quote_sync_ins
AFTER INSERT ON quotes
FOR EACH ROW
BEGIN
  CALL sp_sync_quote_with_ingreso(NEW.ingreso_id, NEW.estado);
END $$

DROP TRIGGER IF EXISTS trg_quote_sync_upd $$
CREATE TRIGGER trg_quote_sync_upd
AFTER UPDATE ON quotes
FOR EACH ROW
BEGIN
  IF (NEW.estado <> OLD.estado) OR (NEW.subtotal <> OLD.subtotal) OR (NEW.fecha_emitido <> OLD.fecha_emitido) OR (NEW.fecha_aprobado <> OLD.fecha_aprobado) THEN
    CALL sp_sync_quote_with_ingreso(NEW.ingreso_id, NEW.estado);
  END IF;
END $$

DELIMITER ;

