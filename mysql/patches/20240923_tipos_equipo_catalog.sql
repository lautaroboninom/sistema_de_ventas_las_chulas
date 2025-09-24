-- mysql/patches/20240923_tipos_equipo_catalog.sql
-- Catálogo GENERAL de Tipos de Equipo (no por marca)
-- Idempotente

CREATE TABLE IF NOT EXISTS catalogo_tipos_equipo (
  id INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(160) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_catalogo_tipos_equipo_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Sembrar desde valores existentes (si no hay datos todavía)
INSERT INTO catalogo_tipos_equipo (nombre, activo)
SELECT x.nombre, TRUE
FROM (
  SELECT DISTINCT TRIM(m.tipo_equipo) AS nombre
  FROM models m
  WHERE COALESCE(TRIM(m.tipo_equipo),'') <> ''

  UNION DISTINCT

  SELECT DISTINCT TRIM(nombre) AS nombre
  FROM marca_tipos_equipo
  WHERE activo = TRUE
) x
LEFT JOIN catalogo_tipos_equipo c ON UPPER(c.nombre) = UPPER(x.nombre)
WHERE COALESCE(TRIM(x.nombre),'') <> '' AND c.id IS NULL;

