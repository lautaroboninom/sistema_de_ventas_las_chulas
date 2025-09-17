-- mysql/04_alter_proveedores.sql

ALTER TABLE proveedores_externos
  ADD COLUMN IF NOT EXISTS telefono TEXT NULL,
  ADD COLUMN IF NOT EXISTS email TEXT NULL,
  ADD COLUMN IF NOT EXISTS direccion TEXT NULL,
  ADD COLUMN IF NOT EXISTS notas TEXT NULL;
