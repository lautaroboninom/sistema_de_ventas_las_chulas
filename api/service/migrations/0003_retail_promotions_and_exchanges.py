from django.db import migrations


SQL = r"""
CREATE TABLE IF NOT EXISTS retail_promotions (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name                      TEXT NOT NULL,
  promo_type                TEXT NOT NULL,
  active                    BOOLEAN NOT NULL DEFAULT TRUE,
  channel_scope             TEXT NOT NULL DEFAULT 'both',
  activation_mode           TEXT NOT NULL DEFAULT 'automatic',
  coupon_code               TEXT,
  priority                  INTEGER NOT NULL DEFAULT 100,
  combinable                BOOLEAN NOT NULL DEFAULT TRUE,
  bogo_mode                 TEXT,
  buy_qty                   INTEGER,
  pay_qty                   INTEGER,
  discount_pct              NUMERIC(6,2),
  applies_to_all_products   BOOLEAN NOT NULL DEFAULT TRUE,
  valid_from                TIMESTAMPTZ,
  valid_until               TIMESTAMPTZ,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_promo_type CHECK (promo_type IN ('percent_off', 'x_for_y')),
  CONSTRAINT chk_retail_promo_channel CHECK (channel_scope IN ('local', 'online', 'both')),
  CONSTRAINT chk_retail_promo_activation CHECK (activation_mode IN ('automatic', 'coupon', 'both')),
  CONSTRAINT chk_retail_promo_bogo_mode CHECK (bogo_mode IS NULL OR bogo_mode IN ('sku', 'mix')),
  CONSTRAINT chk_retail_promo_coupon_mode CHECK (
    activation_mode = 'automatic' OR
    (coupon_code IS NOT NULL AND LENGTH(TRIM(coupon_code)) > 0)
  ),
  CONSTRAINT chk_retail_promo_window CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from),
  CONSTRAINT chk_retail_promo_percent CHECK (
    (promo_type <> 'percent_off') OR
    (discount_pct IS NOT NULL AND discount_pct > 0 AND discount_pct <= 100)
  ),
  CONSTRAINT chk_retail_promo_x_for_y CHECK (
    (promo_type <> 'x_for_y') OR
    (
      bogo_mode IS NOT NULL AND
      buy_qty IS NOT NULL AND buy_qty > 0 AND
      pay_qty IS NOT NULL AND pay_qty >= 0 AND pay_qty < buy_qty
    )
  )
);

DROP TRIGGER IF EXISTS trg_retail_promotions_updated_at ON retail_promotions;
CREATE TRIGGER trg_retail_promotions_updated_at
BEFORE UPDATE ON retail_promotions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_promotions_coupon_ci
ON retail_promotions ((LOWER(coupon_code)))
WHERE coupon_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS retail_promotion_products (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  promotion_id     BIGINT NOT NULL REFERENCES retail_promotions(id) ON DELETE CASCADE,
  product_id       BIGINT NOT NULL REFERENCES retail_products(id) ON DELETE RESTRICT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_promotion_product UNIQUE (promotion_id, product_id)
);

ALTER TABLE IF EXISTS retail_sales
ADD COLUMN IF NOT EXISTS promotion_discount_total_ars NUMERIC(14,2) NOT NULL DEFAULT 0;

ALTER TABLE IF EXISTS retail_sales
ADD COLUMN IF NOT EXISTS pricing_source TEXT NOT NULL DEFAULT 'local_engine';

ALTER TABLE IF EXISTS retail_sale_items
ADD COLUMN IF NOT EXISTS promotion_discount_ars NUMERIC(14,2) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS retail_sale_promotion_applications (
  id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id              BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE CASCADE,
  promotion_id         BIGINT REFERENCES retail_promotions(id) ON DELETE SET NULL,
  source               TEXT NOT NULL,
  promotion_name       TEXT NOT NULL,
  promo_type           TEXT NOT NULL,
  priority             INTEGER NOT NULL DEFAULT 100,
  coupon_code          TEXT,
  discount_amount_ars  NUMERIC(14,2) NOT NULL DEFAULT 0,
  metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_sale_promo_source CHECK (source IN ('local_engine', 'tiendanube')),
  CONSTRAINT chk_sale_promo_type CHECK (promo_type IN ('percent_off', 'x_for_y', 'external')),
  CONSTRAINT chk_sale_promo_discount CHECK (discount_amount_ars >= 0)
);

CREATE TABLE IF NOT EXISTS retail_sale_item_promotion_applications (
  id                              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_item_id                    BIGINT NOT NULL REFERENCES retail_sale_items(id) ON DELETE CASCADE,
  sale_promotion_application_id   BIGINT REFERENCES retail_sale_promotion_applications(id) ON DELETE CASCADE,
  promotion_id                    BIGINT REFERENCES retail_promotions(id) ON DELETE SET NULL,
  source                          TEXT NOT NULL,
  applied_qty                     INTEGER NOT NULL DEFAULT 0,
  discount_amount_ars             NUMERIC(14,2) NOT NULL DEFAULT 0,
  metadata                        JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_sale_item_promo_source CHECK (source IN ('local_engine', 'tiendanube')),
  CONSTRAINT chk_sale_item_promo_qty CHECK (applied_qty >= 0),
  CONSTRAINT chk_sale_item_promo_discount CHECK (discount_amount_ars >= 0)
);

CREATE TABLE IF NOT EXISTS retail_exchanges (
  id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id                BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE RESTRICT,
  status                 TEXT NOT NULL DEFAULT 'confirmed',
  reason                 TEXT,
  processed_by           INTEGER REFERENCES users(id) ON DELETE SET NULL,
  warranty_type          TEXT NOT NULL DEFAULT 'none',
  warranty_override      BOOLEAN NOT NULL DEFAULT FALSE,
  warranty_snapshot      JSONB,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_exchange_status CHECK (status IN ('confirmed', 'cancelled')),
  CONSTRAINT chk_exchange_warranty_type CHECK (warranty_type IN ('none', 'size', 'breakage'))
);

DROP TRIGGER IF EXISTS trg_retail_exchanges_updated_at ON retail_exchanges;
CREATE TRIGGER trg_retail_exchanges_updated_at
BEFORE UPDATE ON retail_exchanges
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_exchange_items (
  id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  exchange_id            BIGINT NOT NULL REFERENCES retail_exchanges(id) ON DELETE CASCADE,
  sale_item_id           BIGINT NOT NULL REFERENCES retail_sale_items(id) ON DELETE RESTRICT,
  variant_from_id        BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  variant_to_id          BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  quantity               INTEGER NOT NULL,
  unit_price_from_ars    NUMERIC(14,2) NOT NULL,
  unit_price_to_ars      NUMERIC(14,2) NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_exchange_item_qty CHECK (quantity > 0),
  CONSTRAINT chk_exchange_item_prices CHECK (unit_price_from_ars >= 0 AND unit_price_to_ars >= 0)
);

CREATE INDEX IF NOT EXISTS idx_retail_promotions_active_window
ON retail_promotions(active, channel_scope, priority, valid_from, valid_until);
CREATE INDEX IF NOT EXISTS idx_retail_promotion_products_promotion ON retail_promotion_products(promotion_id);
CREATE INDEX IF NOT EXISTS idx_retail_promotion_products_product ON retail_promotion_products(product_id);
CREATE INDEX IF NOT EXISTS idx_retail_sale_promo_sale ON retail_sale_promotion_applications(sale_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_sale_promo_promotion ON retail_sale_promotion_applications(promotion_id);
CREATE INDEX IF NOT EXISTS idx_retail_sale_item_promo_sale_item ON retail_sale_item_promotion_applications(sale_item_id);
CREATE INDEX IF NOT EXISTS idx_retail_sale_item_promo_promotion ON retail_sale_item_promotion_applications(promotion_id);
CREATE INDEX IF NOT EXISTS idx_retail_exchanges_sale ON retail_exchanges(sale_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_exchange_items_exchange ON retail_exchange_items(exchange_id);
CREATE INDEX IF NOT EXISTS idx_retail_exchange_items_sale_item ON retail_exchange_items(sale_item_id);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0002_add_retail_product_image_path'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
