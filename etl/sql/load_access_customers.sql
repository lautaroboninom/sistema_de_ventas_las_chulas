SET FOREIGN_KEY_CHECKS=0;
DROP TEMPORARY TABLE IF EXISTS staging_customers;
CREATE TEMPORARY TABLE staging_customers (
  id INT,
  cod_empresa TEXT,
  razon_social TEXT,
  cuit TEXT,
  contacto TEXT,
  telefono TEXT,
  telefono_2 TEXT,
  email TEXT
);
LOAD DATA LOCAL INFILE '/tmp/etl/customers.csv'
INTO TABLE staging_customers
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
ESCAPED BY '\\'
LINES TERMINATED BY '\n' IGNORE 1 LINES
(id, cod_empresa, razon_social, cuit, contacto, telefono, telefono_2, email);
REPLACE INTO customers (id, cod_empresa, razon_social, cuit, contacto, telefono, telefono_2, email)
SELECT NULLIF(id,''), NULLIF(cod_empresa,''), razon_social, NULLIF(cuit,''), NULLIF(contacto,''), NULLIF(telefono,''), NULLIF(telefono_2,''), NULLIF(email,'')
FROM staging_customers
WHERE NULLIF(razon_social,'') IS NOT NULL;
DROP TEMPORARY TABLE staging_customers;
SET FOREIGN_KEY_CHECKS=1;
