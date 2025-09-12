-- mysql/04_procs.sql
-- Procedimientos y funciones auxiliares

DELIMITER $$

-- Inserta evento de estado (equivalente a log_ingreso_state)
DROP PROCEDURE IF EXISTS sp_log_ingreso_state $$
CREATE PROCEDURE sp_log_ingreso_state(
  IN p_ticket_id INT,
  IN p_de_estado VARCHAR(32),
  IN p_a_estado  VARCHAR(32),
  IN p_usuario_id INT,
  IN p_comentario TEXT
)
BEGIN
  INSERT INTO ingreso_events(ticket_id, de_estado, a_estado, usuario_id, comentario)
  VALUES (p_ticket_id, p_de_estado, p_a_estado, p_usuario_id, p_comentario);
END $$

-- Recalcula subtotal de una quote a partir de sus items
DROP PROCEDURE IF EXISTS sp_recalc_quote_subtotal $$
CREATE PROCEDURE sp_recalc_quote_subtotal(IN p_ingreso_id INT)
BEGIN
  DECLARE v_qid INT;
  SELECT id INTO v_qid FROM quotes WHERE ingreso_id = p_ingreso_id LIMIT 1;
  IF v_qid IS NULL THEN
    INSERT INTO quotes(ingreso_id) VALUES (p_ingreso_id)
    ON DUPLICATE KEY UPDATE ingreso_id = VALUES(ingreso_id);
    SELECT id INTO v_qid FROM quotes WHERE ingreso_id = p_ingreso_id LIMIT 1;
  END IF;

  UPDATE quotes q
     SET subtotal = COALESCE((
       SELECT SUM(qi.qty * qi.precio_u)
         FROM quote_items qi
        WHERE qi.quote_id = q.id
     ), 0)
   WHERE q.id = v_qid;
END $$

-- Sincroniza estado de quote hacia ingresos.presupuesto_estado
DROP PROCEDURE IF EXISTS sp_sync_quote_with_ingreso $$
CREATE PROCEDURE sp_sync_quote_with_ingreso(
  IN p_ingreso_id INT,
  IN p_estado VARCHAR(32)
)
BEGIN
  DECLARE v_cur_estado VARCHAR(32);
  SELECT estado INTO v_cur_estado FROM ingresos WHERE id = p_ingreso_id LIMIT 1;

  UPDATE ingresos
     SET presupuesto_estado = (
            CASE p_estado
              WHEN 'emitido' THEN 'presupuestado'
              WHEN 'presupuestado' THEN 'presupuestado'
              WHEN 'aprobado' THEN 'aprobado'
              WHEN 'rechazado' THEN 'rechazado'
              ELSE 'pendiente'
            END
         ),
         estado = (
            CASE
              WHEN p_estado = 'aprobado' AND v_cur_estado IN ('ingresado','diagnosticado','presupuestado') THEN 'reparar'
              ELSE v_cur_estado
            END
         )
   WHERE id = p_ingreso_id;
END $$

-- Append-only de audit_log: bloquear UPDATE y DELETE
DROP TRIGGER IF EXISTS trg_audit_log_no_update $$
CREATE TRIGGER trg_audit_log_no_update
BEFORE UPDATE ON audit_log
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_log is append-only';
END $$

DROP TRIGGER IF EXISTS trg_audit_log_no_delete $$
CREATE TRIGGER trg_audit_log_no_delete
BEFORE DELETE ON audit_log
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_log is append-only';
END $$

DELIMITER ;

