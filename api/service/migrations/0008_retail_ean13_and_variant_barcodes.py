from django.db import migrations


SQL = r"""
ALTER TABLE retail_settings
  ADD COLUMN IF NOT EXISTS ean_country_prefix TEXT;

ALTER TABLE retail_settings
  ADD COLUMN IF NOT EXISTS ean_generic_supplier_code TEXT;

UPDATE retail_settings
SET ean_country_prefix = COALESCE(NULLIF(TRIM(ean_country_prefix), ''), '779'),
    ean_generic_supplier_code = COALESCE(NULLIF(TRIM(ean_generic_supplier_code), ''), '0000')
WHERE id = 1;

ALTER TABLE retail_settings
  ALTER COLUMN ean_country_prefix SET DEFAULT '779';

ALTER TABLE retail_settings
  ALTER COLUMN ean_generic_supplier_code SET DEFAULT '0000';

ALTER TABLE retail_settings
  ALTER COLUMN ean_country_prefix SET NOT NULL;

ALTER TABLE retail_settings
  ALTER COLUMN ean_generic_supplier_code SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_settings_ean_country_prefix'
  ) THEN
    ALTER TABLE retail_settings
      ADD CONSTRAINT chk_retail_settings_ean_country_prefix
      CHECK (ean_country_prefix ~ '^[0-9]{3}$');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_settings_ean_generic_supplier'
  ) THEN
    ALTER TABLE retail_settings
      ADD CONSTRAINT chk_retail_settings_ean_generic_supplier
      CHECK (ean_generic_supplier_code ~ '^[0-9]{4}$');
  END IF;
END $$;

ALTER TABLE retail_suppliers
  ADD COLUMN IF NOT EXISTS ean_supplier_code TEXT;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_suppliers_ean_supplier_code'
  ) THEN
    ALTER TABLE retail_suppliers
      ADD CONSTRAINT chk_retail_suppliers_ean_supplier_code
      CHECK (ean_supplier_code IS NULL OR ean_supplier_code ~ '^[0-9]{4}$');
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_suppliers_ean_supplier_code
ON retail_suppliers(ean_supplier_code)
WHERE ean_supplier_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS retail_ean13_supplier_sequences (
  supplier_code    TEXT PRIMARY KEY,
  last_item_code   INTEGER NOT NULL DEFAULT 0,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_ean13_supplier_code CHECK (supplier_code ~ '^[0-9]{4}$'),
  CONSTRAINT chk_retail_ean13_last_item_code CHECK (last_item_code >= 0 AND last_item_code <= 99999)
);

DROP TRIGGER IF EXISTS trg_retail_ean13_sequences_updated_at ON retail_ean13_supplier_sequences;
CREATE TRIGGER trg_retail_ean13_sequences_updated_at
BEFORE UPDATE ON retail_ean13_supplier_sequences
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_variant_barcodes (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  variant_id       BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE CASCADE,
  barcode          TEXT NOT NULL,
  is_primary       BOOLEAN NOT NULL DEFAULT FALSE,
  supplier_id      BIGINT REFERENCES retail_suppliers(id) ON DELETE SET NULL,
  source           TEXT NOT NULL DEFAULT 'manual',
  created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_retail_variant_barcodes_updated_at ON retail_variant_barcodes;
CREATE TRIGGER trg_retail_variant_barcodes_updated_at
BEFORE UPDATE ON retail_variant_barcodes
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO retail_variant_barcodes(variant_id, barcode, is_primary, source, created_at, updated_at)
SELECT v.id, v.barcode_internal, TRUE, 'legacy_backfill', COALESCE(v.created_at, NOW()), COALESCE(v.updated_at, NOW())
FROM retail_product_variants v
WHERE v.barcode_internal IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM retail_variant_barcodes b
    WHERE LOWER(b.barcode) = LOWER(v.barcode_internal)
  );

UPDATE retail_variant_barcodes
SET is_primary = FALSE;

WITH ranked AS (
  SELECT id,
         ROW_NUMBER() OVER (PARTITION BY variant_id ORDER BY id) AS rn
  FROM retail_variant_barcodes
)
UPDATE retail_variant_barcodes b
SET is_primary = TRUE
FROM ranked r
WHERE b.id = r.id
  AND r.rn = 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_variant_barcodes_code_ci
ON retail_variant_barcodes ((LOWER(barcode)));

CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_variant_barcodes_primary_per_variant
ON retail_variant_barcodes (variant_id)
WHERE is_primary;

CREATE INDEX IF NOT EXISTS idx_retail_variant_barcodes_variant
ON retail_variant_barcodes(variant_id, is_primary DESC, id);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0007_retail_pos_drafts_split_payments'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]

