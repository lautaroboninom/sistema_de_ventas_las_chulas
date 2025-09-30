-- Tabla de feriados (calendario laboral)
CREATE TABLE IF NOT EXISTS feriados (
  fecha DATE PRIMARY KEY,
  nombre TEXT NOT NULL
) ENGINE=InnoDB;

-- Seed específico solicitado
INSERT INTO feriados (fecha, nombre)
VALUES ('2025-09-29', 'Día del Empleado de Comercio')
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);
