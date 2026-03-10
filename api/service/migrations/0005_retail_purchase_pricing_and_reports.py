from django.db import migrations


SQL = r"""
ALTER TABLE retail_settings
  ADD COLUMN IF NOT EXISTS purchase_default_markup_pct NUMERIC(6,2);

UPDATE retail_settings
SET purchase_default_markup_pct = 100.00
WHERE purchase_default_markup_pct IS NULL OR purchase_default_markup_pct < 0;

ALTER TABLE retail_settings
  ALTER COLUMN purchase_default_markup_pct SET DEFAULT 100.00;

ALTER TABLE retail_settings
  ALTER COLUMN purchase_default_markup_pct SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_settings_purchase_markup'
  ) THEN
    ALTER TABLE retail_settings
      ADD CONSTRAINT chk_retail_settings_purchase_markup
      CHECK (purchase_default_markup_pct >= 0);
  END IF;
END $$;

ALTER TABLE retail_purchase_items
  ADD COLUMN IF NOT EXISTS suggested_markup_pct NUMERIC(6,2);

ALTER TABLE retail_purchase_items
  ADD COLUMN IF NOT EXISTS unit_price_suggested_ars NUMERIC(14,2);

ALTER TABLE retail_purchase_items
  ADD COLUMN IF NOT EXISTS unit_price_final_ars NUMERIC(14,2);

ALTER TABLE retail_purchase_items
  ADD COLUMN IF NOT EXISTS real_margin_pct NUMERIC(8,2);

UPDATE retail_purchase_items
SET suggested_markup_pct = 100.00
WHERE suggested_markup_pct IS NULL OR suggested_markup_pct < 0;

UPDATE retail_purchase_items
SET unit_price_suggested_ars = ROUND((unit_cost_ars * (1 + suggested_markup_pct / 100.0))::numeric, 2)
WHERE unit_price_suggested_ars IS NULL OR unit_price_suggested_ars < 0;

ALTER TABLE retail_purchase_items
  ALTER COLUMN suggested_markup_pct SET DEFAULT 100.00;

ALTER TABLE retail_purchase_items
  ALTER COLUMN unit_price_suggested_ars SET DEFAULT 0;

ALTER TABLE retail_purchase_items
  ALTER COLUMN suggested_markup_pct SET NOT NULL;

ALTER TABLE retail_purchase_items
  ALTER COLUMN unit_price_suggested_ars SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_purchase_item_suggested_markup'
  ) THEN
    ALTER TABLE retail_purchase_items
      ADD CONSTRAINT chk_purchase_item_suggested_markup
      CHECK (suggested_markup_pct >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_purchase_item_suggested_price'
  ) THEN
    ALTER TABLE retail_purchase_items
      ADD CONSTRAINT chk_purchase_item_suggested_price
      CHECK (unit_price_suggested_ars >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_purchase_item_final_price'
  ) THEN
    ALTER TABLE retail_purchase_items
      ADD CONSTRAINT chk_purchase_item_final_price
      CHECK (unit_price_final_ars IS NULL OR unit_price_final_ars >= 0);
  END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0004_retail_promotion_variants'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
