-- Insert/update quotes and quote_items from staging, mapping enums and dates
START TRANSACTION;

-- Quotes
INSERT INTO quotes (
  id, ingreso_id, estado, moneda, subtotal, autorizado_por, forma_pago, fecha_emitido, fecha_aprobado, pdf_url
)
SELECT
  CAST(s.id AS UNSIGNED) AS id,
  CAST(COALESCE(NULLIF(s.ingreso_id,''), NULLIF(s.ticket_id,'')) AS UNSIGNED) AS ingreso_id,
  CASE LOWER(s.estado)
    WHEN 'enviado' THEN 'emitido'
    ELSE s.estado
  END AS estado,
  COALESCE(NULLIF(s.moneda,''), 'ARS') AS moneda,
  CAST(NULLIF(s.subtotal,'') AS DECIMAL(12,2)) AS subtotal,
  NULLIF(s.autorizado_por,'') AS autorizado_por,
  NULLIF(s.forma_pago,'') AS forma_pago,
  CASE WHEN s.fecha_emitido IS NULL OR s.fecha_emitido = '' THEN NULL ELSE STR_TO_DATE(LEFT(s.fecha_emitido, 19), '%Y-%m-%d %H:%i:%s') END AS fecha_emitido,
  CASE WHEN s.fecha_aprobado IS NULL OR s.fecha_aprobado = '' THEN NULL ELSE STR_TO_DATE(LEFT(s.fecha_aprobado, 19), '%Y-%m-%d %H:%i:%s') END AS fecha_aprobado,
  NULLIF(s.pdf_url,'') AS pdf_url
FROM stg_quotes s
WHERE s.id REGEXP '^[0-9]+$' AND (s.ingreso_id REGEXP '^[0-9]+$' OR s.ticket_id REGEXP '^[0-9]+$')
ON DUPLICATE KEY UPDATE
  ingreso_id=VALUES(ingreso_id), estado=VALUES(estado), moneda=VALUES(moneda), subtotal=VALUES(subtotal),
  autorizado_por=VALUES(autorizado_por), forma_pago=VALUES(forma_pago), fecha_emitido=VALUES(fecha_emitido),
  fecha_aprobado=VALUES(fecha_aprobado), pdf_url=VALUES(pdf_url);

-- Quote items
INSERT INTO quote_items (
  id, quote_id, tipo, descripcion, qty, precio_u, repuesto_id
)
SELECT
  CAST(i.id AS UNSIGNED) AS id,
  CAST(i.quote_id AS UNSIGNED) AS quote_id,
  i.tipo,
  i.descripcion,
  CAST(NULLIF(i.qty,'') AS DECIMAL(10,2)) AS qty,
  CAST(NULLIF(i.precio_u,'') AS DECIMAL(12,2)) AS precio_u,
  CASE WHEN i.repuesto_id REGEXP '^[0-9]+$' THEN CAST(i.repuesto_id AS UNSIGNED) ELSE NULL END AS repuesto_id
FROM stg_quote_items i
WHERE i.id REGEXP '^[0-9]+$' AND i.quote_id REGEXP '^[0-9]+$'
ON DUPLICATE KEY UPDATE
  quote_id=VALUES(quote_id), tipo=VALUES(tipo), descripcion=VALUES(descripcion), qty=VALUES(qty), precio_u=VALUES(precio_u), repuesto_id=VALUES(repuesto_id);

COMMIT;
