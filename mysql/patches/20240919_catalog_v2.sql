-- mysql/patches/20240919_catalog_v2.sql
-- Introduce hierarchical equipment catalog (brand -> type -> series -> variant) and model mapping.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS marca_tipos_equipo (
  id INT AUTO_INCREMENT PRIMARY KEY,
  marca_id INT NOT NULL,
  nombre VARCHAR(160) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_marca_tipos_equipo (marca_id, nombre),
  KEY idx_marca_tipos_equipo_marca (marca_id),
  CONSTRAINT fk_marca_tipos_equipo_marca
    FOREIGN KEY (marca_id) REFERENCES marcas(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS marca_series (
  id INT AUTO_INCREMENT PRIMARY KEY,
  marca_id INT NOT NULL,
  tipo_id INT NOT NULL,
  nombre VARCHAR(160) NOT NULL,
  alias VARCHAR(160) NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_marca_series (marca_id, tipo_id, nombre),
  KEY idx_marca_series_tipo (tipo_id),
  CONSTRAINT fk_marca_series_marca
    FOREIGN KEY (marca_id) REFERENCES marcas(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_marca_series_tipo
    FOREIGN KEY (tipo_id) REFERENCES marca_tipos_equipo(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS marca_series_variantes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  marca_id INT NOT NULL,
  tipo_id INT NOT NULL,
  serie_id INT NOT NULL,
  nombre VARCHAR(160) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_marca_series_variantes (marca_id, tipo_id, serie_id, nombre),
  KEY idx_marca_series_variantes_tipo (tipo_id),
  KEY idx_marca_series_variantes_serie (serie_id),
  CONSTRAINT fk_msv_marca
    FOREIGN KEY (marca_id) REFERENCES marcas(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_msv_tipo
    FOREIGN KEY (tipo_id) REFERENCES marca_tipos_equipo(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_msv_serie
    FOREIGN KEY (serie_id) REFERENCES marca_series(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS model_hierarchy (
  id INT AUTO_INCREMENT PRIMARY KEY,
  model_id INT NOT NULL,
  marca_id INT NOT NULL,
  tipo_id INT NOT NULL,
  serie_id INT NOT NULL,
  variante_id INT NULL,
  full_name VARCHAR(240) NOT NULL,
  variant_key INT GENERATED ALWAYS AS (IFNULL(variante_id, 0)) STORED,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_model_hierarchy_model (model_id),
  UNIQUE KEY uq_model_hierarchy_combo (marca_id, tipo_id, serie_id, variant_key),
  KEY idx_model_hierarchy_tipo (tipo_id),
  KEY idx_model_hierarchy_serie (serie_id),
  KEY idx_model_hierarchy_variante (variante_id),
  CONSTRAINT fk_model_hierarchy_model
    FOREIGN KEY (model_id) REFERENCES models(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_model_hierarchy_marca
    FOREIGN KEY (marca_id) REFERENCES marcas(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_model_hierarchy_tipo
    FOREIGN KEY (tipo_id) REFERENCES marca_tipos_equipo(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_model_hierarchy_serie
    FOREIGN KEY (serie_id) REFERENCES marca_series(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE marca_tipos_equipo CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE marca_series CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE marca_series_variantes CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE model_hierarchy CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE OR REPLACE VIEW vw_model_hierarchy_detail AS
SELECT
    mh.model_id,
    mh.marca_id,
    mh.tipo_id,
    mh.serie_id,
    mh.variante_id,
    mh.full_name,
    mt.nombre AS tipo_nombre,
    ms.nombre AS serie_nombre,
    mv.nombre AS variante_nombre
FROM model_hierarchy mh
JOIN marca_tipos_equipo mt ON mt.id = mh.tipo_id
JOIN marca_series ms ON ms.id = mh.serie_id
LEFT JOIN marca_series_variantes mv ON mv.id = mh.variante_id;

-- ==============================
-- Seed data for BMC hierarchy
-- ==============================
INSERT INTO marcas (nombre) VALUES ('BMC')
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
SET @bmc_id := (SELECT id FROM marcas WHERE UPPER(nombre) = 'BMC' LIMIT 1);

INSERT INTO marca_tipos_equipo (marca_id, nombre)
SELECT @bmc_id, t.nombre
FROM (SELECT 'CPAP' AS nombre UNION ALL SELECT 'AUTO CPAP' UNION ALL SELECT 'BPAP') AS t
WHERE NOT EXISTS (
  SELECT 1 FROM marca_tipos_equipo mte
  WHERE mte.marca_id = @bmc_id AND UPPER(mte.nombre) = UPPER(t.nombre)
);

SET @tipo_cpap := (SELECT id FROM marca_tipos_equipo WHERE marca_id = @bmc_id AND UPPER(nombre) = 'CPAP' LIMIT 1);
SET @tipo_auto := (SELECT id FROM marca_tipos_equipo WHERE marca_id = @bmc_id AND UPPER(nombre) = 'AUTO CPAP' LIMIT 1);
SET @tipo_bpap := (SELECT id FROM marca_tipos_equipo WHERE marca_id = @bmc_id AND UPPER(nombre) = 'BPAP' LIMIT 1);

INSERT INTO marca_series (marca_id, tipo_id, nombre)
SELECT @bmc_id, @tipo_cpap, s.nombre
FROM (
  SELECT 'G1' AS nombre UNION ALL
  SELECT 'G2' UNION ALL
  SELECT 'G2S' UNION ALL
  SELECT 'G3'
) AS s
WHERE NOT EXISTS (
  SELECT 1 FROM marca_series ms
  WHERE ms.marca_id = @bmc_id AND ms.tipo_id = @tipo_cpap AND UPPER(ms.nombre) = UPPER(s.nombre)
);

INSERT INTO marca_series (marca_id, tipo_id, nombre)
SELECT @bmc_id, @tipo_auto, s.nombre
FROM (
  SELECT 'G1' AS nombre UNION ALL
  SELECT 'G2' UNION ALL
  SELECT 'G2S' UNION ALL
  SELECT 'G3'
) AS s
WHERE NOT EXISTS (
  SELECT 1 FROM marca_series ms
  WHERE ms.marca_id = @bmc_id AND ms.tipo_id = @tipo_auto AND UPPER(ms.nombre) = UPPER(s.nombre)
);

INSERT INTO marca_series (marca_id, tipo_id, nombre)
SELECT @bmc_id, @tipo_bpap, s.nombre
FROM (
  SELECT 'G1' AS nombre UNION ALL
  SELECT 'G2' UNION ALL
  SELECT 'G2S' UNION ALL
  SELECT 'G3'
) AS s
WHERE NOT EXISTS (
  SELECT 1 FROM marca_series ms
  WHERE ms.marca_id = @bmc_id AND ms.tipo_id = @tipo_bpap AND UPPER(ms.nombre) = UPPER(s.nombre)
);

SET @serie_auto_g2  := (SELECT ms.id FROM marca_series ms WHERE ms.marca_id = @bmc_id AND ms.tipo_id = @tipo_auto AND UPPER(ms.nombre) = 'G2' LIMIT 1);
SET @serie_auto_g2s := (SELECT ms.id FROM marca_series ms WHERE ms.marca_id = @bmc_id AND ms.tipo_id = @tipo_auto AND UPPER(ms.nombre) = 'G2S' LIMIT 1);
SET @serie_auto_g3  := (SELECT ms.id FROM marca_series ms WHERE ms.marca_id = @bmc_id AND ms.tipo_id = @tipo_auto AND UPPER(ms.nombre) = 'G3' LIMIT 1);

-- Variantes para AUTO CPAP G2
INSERT INTO marca_series_variantes (marca_id, tipo_id, serie_id, nombre)
SELECT @bmc_id, @tipo_auto, @serie_auto_g2, v.nombre
FROM (SELECT '25' AS nombre UNION ALL SELECT '25T' UNION ALL SELECT '25S') v
WHERE NOT EXISTS (
  SELECT 1 FROM marca_series_variantes msv
  WHERE msv.marca_id = @bmc_id AND msv.tipo_id = @tipo_auto
    AND msv.serie_id = @serie_auto_g2 AND UPPER(msv.nombre) = UPPER(v.nombre)
);

-- Variantes para AUTO CPAP G2S
INSERT INTO marca_series_variantes (marca_id, tipo_id, serie_id, nombre)
SELECT @bmc_id, @tipo_auto, @serie_auto_g2s, v.nombre
FROM (SELECT '25' AS nombre UNION ALL SELECT '25T' UNION ALL SELECT '25S') v
WHERE NOT EXISTS (
  SELECT 1 FROM marca_series_variantes msv
  WHERE msv.marca_id = @bmc_id AND msv.tipo_id = @tipo_auto
    AND msv.serie_id = @serie_auto_g2s AND UPPER(msv.nombre) = UPPER(v.nombre)
);

-- Variantes para AUTO CPAP G3
INSERT INTO marca_series_variantes (marca_id, tipo_id, serie_id, nombre)
SELECT @bmc_id, @tipo_auto, @serie_auto_g3, v.nombre
FROM (SELECT 'V30BT' AS nombre) v
WHERE NOT EXISTS (
  SELECT 1 FROM marca_series_variantes msv
  WHERE msv.marca_id = @bmc_id AND msv.tipo_id = @tipo_auto
    AND msv.serie_id = @serie_auto_g3 AND UPPER(msv.nombre) = UPPER(v.nombre)
);

INSERT INTO models (marca_id, nombre)
SELECT @bmc_id, CONCAT('AUTO CPAP ', s.nombre)
FROM marca_series s
WHERE s.marca_id = @bmc_id AND s.tipo_id = @tipo_auto
  AND NOT EXISTS (
    SELECT 1 FROM models m WHERE m.marca_id = @bmc_id AND UPPER(m.nombre) = UPPER(CONCAT('AUTO CPAP ', s.nombre))
  );

INSERT INTO models (marca_id, nombre)
SELECT @bmc_id, CONCAT('AUTO CPAP ', s.nombre, ' ', v.nombre)
FROM marca_series s
JOIN marca_series_variantes v ON v.marca_id = s.marca_id AND v.tipo_id = s.tipo_id AND v.serie_id = s.id
WHERE s.marca_id = @bmc_id AND s.tipo_id = @tipo_auto
  AND NOT EXISTS (
    SELECT 1 FROM models m WHERE m.marca_id = @bmc_id AND UPPER(m.nombre) = UPPER(CONCAT('AUTO CPAP ', s.nombre, ' ', v.nombre))
  );

INSERT INTO model_hierarchy (model_id, marca_id, tipo_id, serie_id, variante_id, full_name)
SELECT m.id, @bmc_id, s.tipo_id, s.id, NULL, CONCAT('BMC AUTO CPAP ', s.nombre)
FROM marca_series s
JOIN models m ON m.marca_id = @bmc_id AND UPPER(m.nombre) = UPPER(CONCAT('AUTO CPAP ', s.nombre))
WHERE s.marca_id = @bmc_id AND s.tipo_id = @tipo_auto
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);

INSERT INTO model_hierarchy (model_id, marca_id, tipo_id, serie_id, variante_id, full_name)
SELECT m.id, @bmc_id, s.tipo_id, s.id, v.id, CONCAT('BMC AUTO CPAP ', s.nombre, ' ', v.nombre)
FROM marca_series s
JOIN marca_series_variantes v ON v.marca_id = s.marca_id AND v.tipo_id = s.tipo_id AND v.serie_id = s.id
JOIN models m ON m.marca_id = @bmc_id AND UPPER(m.nombre) = UPPER(CONCAT('AUTO CPAP ', s.nombre, ' ', v.nombre))
WHERE s.marca_id = @bmc_id AND s.tipo_id = @tipo_auto
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name);
