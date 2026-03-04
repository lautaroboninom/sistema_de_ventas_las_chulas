-- migrate_warranty_returns.sql
-- Cambios y devoluciones con garantia por ticket
-- Seguro para ejecutar multiples veces en PostgreSQL.

ALTER TABLE retail_settings
  ADD COLUMN IF NOT EXISTS return_warranty_size_days INTEGER;

ALTER TABLE retail_settings
  ADD COLUMN IF NOT EXISTS return_warranty_breakage_days INTEGER;

UPDATE retail_settings
SET return_warranty_size_days = 30
WHERE return_warranty_size_days IS NULL OR return_warranty_size_days <= 0;

UPDATE retail_settings
SET return_warranty_breakage_days = 90
WHERE return_warranty_breakage_days IS NULL OR return_warranty_breakage_days <= 0;

ALTER TABLE retail_settings
  ALTER COLUMN return_warranty_size_days SET DEFAULT 30;

ALTER TABLE retail_settings
  ALTER COLUMN return_warranty_breakage_days SET DEFAULT 90;

ALTER TABLE retail_settings
  ALTER COLUMN return_warranty_size_days SET NOT NULL;

ALTER TABLE retail_settings
  ALTER COLUMN return_warranty_breakage_days SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_settings_return_warranty_size'
  ) THEN
    ALTER TABLE retail_settings
      ADD CONSTRAINT chk_retail_settings_return_warranty_size
      CHECK (return_warranty_size_days > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_settings_return_warranty_breakage'
  ) THEN
    ALTER TABLE retail_settings
      ADD CONSTRAINT chk_retail_settings_return_warranty_breakage
      CHECK (return_warranty_breakage_days > 0);
  END IF;
END $$;

ALTER TABLE retail_returns
  ADD COLUMN IF NOT EXISTS warranty_type TEXT;

ALTER TABLE retail_returns
  ADD COLUMN IF NOT EXISTS warranty_override BOOLEAN;

ALTER TABLE retail_returns
  ADD COLUMN IF NOT EXISTS warranty_snapshot JSONB;

UPDATE retail_returns
SET warranty_type = 'none'
WHERE warranty_type IS NULL;

UPDATE retail_returns
SET warranty_override = FALSE
WHERE warranty_override IS NULL;

ALTER TABLE retail_returns
  ALTER COLUMN warranty_type SET DEFAULT 'none';

ALTER TABLE retail_returns
  ALTER COLUMN warranty_override SET DEFAULT FALSE;

ALTER TABLE retail_returns
  ALTER COLUMN warranty_type SET NOT NULL;

ALTER TABLE retail_returns
  ALTER COLUMN warranty_override SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_return_warranty_type'
  ) THEN
    ALTER TABLE retail_returns
      ADD CONSTRAINT chk_return_warranty_type
      CHECK (warranty_type IN ('none', 'size', 'breakage'));
  END IF;
END $$;
