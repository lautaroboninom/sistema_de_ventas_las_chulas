-- migrate_product_base_prices_supplier_names.sql
-- Precio base por producto + nombre/descripcion del proveedor por item de compra.
-- Idempotente para PostgreSQL.

ALTER TABLE retail_products
  ADD COLUMN IF NOT EXISTS default_price_store_ars NUMERIC(14,2);

ALTER TABLE retail_products
  ADD COLUMN IF NOT EXISTS default_price_online_ars NUMERIC(14,2);

UPDATE retail_products p
SET default_price_store_ars = COALESCE(
      NULLIF(p.default_price_store_ars, 0),
      (
        SELECT v.price_store_ars
        FROM retail_product_variants v
        WHERE v.product_id=p.id AND v.active=TRUE
        ORDER BY v.id
        LIMIT 1
      ),
      0
    ),
    default_price_online_ars = COALESCE(
      NULLIF(p.default_price_online_ars, 0),
      (
        SELECT v.price_online_ars
        FROM retail_product_variants v
        WHERE v.product_id=p.id AND v.active=TRUE
        ORDER BY v.id
        LIMIT 1
      ),
      NULLIF(p.default_price_store_ars, 0),
      0
    )
WHERE p.default_price_store_ars IS NULL
   OR p.default_price_online_ars IS NULL
   OR p.default_price_store_ars = 0
   OR p.default_price_online_ars = 0;

ALTER TABLE retail_products
  ALTER COLUMN default_price_store_ars SET DEFAULT 0;

ALTER TABLE retail_products
  ALTER COLUMN default_price_online_ars SET DEFAULT 0;

ALTER TABLE retail_products
  ALTER COLUMN default_price_store_ars SET NOT NULL;

ALTER TABLE retail_products
  ALTER COLUMN default_price_online_ars SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_products_default_prices'
  ) THEN
    ALTER TABLE retail_products
      ADD CONSTRAINT chk_retail_products_default_prices
      CHECK (default_price_store_ars >= 0 AND default_price_online_ars >= 0);
  END IF;
END $$;

ALTER TABLE retail_purchase_items
  ADD COLUMN IF NOT EXISTS supplier_product_name TEXT;
