-- Staging tables for quotes and quote_items, CSV structure as exported from PG
DROP TABLE IF EXISTS stg_quotes;
CREATE TABLE stg_quotes (
  row_num INT PRIMARY KEY AUTO_INCREMENT,
  id TEXT,
  ticket_id TEXT,
  estado TEXT,
  moneda TEXT,
  subtotal TEXT,
  autorizado_por TEXT,
  forma_pago TEXT,
  fecha_emitido TEXT,
  fecha_aprobado TEXT,
  pdf_url TEXT,
  ingreso_id TEXT
) ENGINE=InnoDB;

DROP TABLE IF EXISTS stg_quote_items;
CREATE TABLE stg_quote_items (
  row_num INT PRIMARY KEY AUTO_INCREMENT,
  id TEXT,
  quote_id TEXT,
  tipo TEXT,
  descripcion TEXT,
  qty TEXT,
  precio_u TEXT,
  repuesto_id TEXT
) ENGINE=InnoDB;

-- Load quotes.csv and quote_items.csv from secure_file_priv
LOAD DATA INFILE '/var/lib/mysql-files/quotes.csv'
INTO TABLE stg_quotes
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(
 id, @ticket_id, estado, moneda, subtotal, autorizado_por, forma_pago, fecha_emitido, fecha_aprobado, pdf_url, @ingreso_id
)
SET ticket_id = NULLIF(@ticket_id,''), ingreso_id = NULLIF(@ingreso_id,'');

LOAD DATA INFILE '/var/lib/mysql-files/quote_items.csv'
INTO TABLE stg_quote_items
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"' ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(
 id, quote_id, tipo, descripcion, qty, precio_u, repuesto_id
);

-- Quick stats
SELECT COUNT(*) AS stg_quotes_rows FROM stg_quotes;
SELECT COUNT(*) AS stg_quote_items_rows FROM stg_quote_items;

-- Missing quote ids compared to existing quotes
SELECT CAST(s.id AS UNSIGNED) AS missing_quote_id
  FROM stg_quotes s
  LEFT JOIN quotes q ON q.id = CAST(s.id AS UNSIGNED)
 WHERE q.id IS NULL
 ORDER BY CAST(s.id AS UNSIGNED)
 LIMIT 50;

-- Missing items by quote
SELECT CAST(i.quote_id AS UNSIGNED) AS missing_item_quote
  FROM stg_quote_items i
  LEFT JOIN quotes q ON q.id = CAST(i.quote_id AS UNSIGNED)
 WHERE q.id IS NULL
 GROUP BY CAST(i.quote_id AS UNSIGNED)
 ORDER BY 1
 LIMIT 50;
