-- schema.sql
-- Las Chulas - Esquema retail puro (PostgreSQL 12+)

SET TIME ZONE 'America/Argentina/Buenos_Aires';
CREATE EXTENSION IF NOT EXISTS citext;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION audit_log_append_only()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION audit_row_change()
RETURNS TRIGGER AS $$
DECLARE
  v_actor_user_id INTEGER;
  v_record_pk TEXT;
BEGIN
  BEGIN
    v_actor_user_id := NULLIF(current_setting('app.user_id', true), '')::INTEGER;
  EXCEPTION WHEN OTHERS THEN
    v_actor_user_id := NULL;
  END;

  IF TG_OP = 'DELETE' THEN
    v_record_pk := COALESCE((to_jsonb(OLD)->>'id'), '');
    INSERT INTO audit_log(actor_user_id, table_name, record_pk, action, old_data, new_data)
    VALUES (v_actor_user_id, TG_TABLE_NAME, v_record_pk, 'delete', to_jsonb(OLD), NULL);
    RETURN OLD;
  ELSIF TG_OP = 'UPDATE' THEN
    v_record_pk := COALESCE((to_jsonb(NEW)->>'id'), COALESCE((to_jsonb(OLD)->>'id'), ''));
    INSERT INTO audit_log(actor_user_id, table_name, record_pk, action, old_data, new_data)
    VALUES (v_actor_user_id, TG_TABLE_NAME, v_record_pk, 'update', to_jsonb(OLD), to_jsonb(NEW));
    RETURN NEW;
  ELSE
    v_record_pk := COALESCE((to_jsonb(NEW)->>'id'), '');
    INSERT INTO audit_log(actor_user_id, table_name, record_pk, action, old_data, new_data)
    VALUES (v_actor_user_id, TG_TABLE_NAME, v_record_pk, 'insert', NULL, to_jsonb(NEW));
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- =============================
-- Auth / users / audit
-- =============================
CREATE TABLE IF NOT EXISTS users (
  id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nombre           TEXT NOT NULL,
  email            CITEXT NOT NULL UNIQUE,
  hash_pw          TEXT,
  rol              TEXT NOT NULL DEFAULT 'empleado',
  activo           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_users_rol CHECK (rol IN ('admin', 'empleado'))
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash       TEXT NOT NULL UNIQUE,
  expires_at       TIMESTAMPTZ NOT NULL,
  used_at          TIMESTAMPTZ,
  ip               TEXT,
  user_agent       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_permission_overrides (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  permission_code  TEXT NOT NULL,
  effect           TEXT NOT NULL,
  updated_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_user_permission_overrides UNIQUE (user_id, permission_code),
  CONSTRAINT chk_user_permission_effect CHECK (effect IN ('allow', 'deny'))
);

CREATE TABLE IF NOT EXISTS audit_log (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor_user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  table_name       TEXT NOT NULL,
  record_pk        TEXT,
  action           TEXT NOT NULL,
  old_data         JSONB,
  new_data         JSONB,
  request_id       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_audit_action CHECK (action IN ('insert', 'update', 'delete', 'login', 'other'))
);

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Usuario admin de prueba (solo desarrollo local)
INSERT INTO users(nombre, email, hash_pw, rol, activo)
VALUES (
  'Admin Las Chulas',
  'admin@laschulas.local',
  'argon2$argon2id$v=19$m=102400,t=2,p=8$bDlGUkxQNEp1MG9nUXBYZUJ6VXJ4eg$qzISs1g3Q2+BxqgwqSxaht+Al02E6W2cq4TBg7uBUPg',
  'admin',
  TRUE
)
ON CONFLICT (email) DO UPDATE
SET nombre = EXCLUDED.nombre,
    hash_pw = EXCLUDED.hash_pw,
    rol = 'admin',
    activo = TRUE;

DROP TRIGGER IF EXISTS trg_user_permission_overrides_updated_at ON user_permission_overrides;
CREATE TRIGGER trg_user_permission_overrides_updated_at
BEFORE UPDATE ON user_permission_overrides
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_audit_log_no_update ON audit_log;
CREATE TRIGGER trg_audit_log_no_update
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();

-- =============================
-- Retail configuration
-- =============================
CREATE TABLE IF NOT EXISTS retail_settings (
  id                            SMALLINT PRIMARY KEY DEFAULT 1,
  business_name                 TEXT NOT NULL DEFAULT 'Las Chulas',
  currency_code                 TEXT NOT NULL DEFAULT 'ARS',
  iva_condition                 TEXT,
  arca_env                      TEXT NOT NULL DEFAULT 'homologacion',
  arca_cuit                     TEXT,
  arca_pto_vta_store            INTEGER,
  arca_pto_vta_online           INTEGER,
  arca_cert_path                TEXT,
  arca_key_path                 TEXT,
  arca_wsaa_service             TEXT DEFAULT 'wsfe',
  tiendanube_store_id           BIGINT,
  tiendanube_client_id          TEXT,
  tiendanube_client_secret      TEXT,
  tiendanube_access_token       TEXT,
  tiendanube_webhook_secret     TEXT,
  ticket_printer_name           TEXT,
  label_printer_name            TEXT,
  auto_invoice_online_paid      BOOLEAN NOT NULL DEFAULT TRUE,
  return_warranty_size_days     INTEGER NOT NULL DEFAULT 30,
  return_warranty_breakage_days INTEGER NOT NULL DEFAULT 90,
  ui_page_settings              JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_settings_singleton CHECK (id = 1),
  CONSTRAINT chk_retail_settings_currency CHECK (currency_code = 'ARS'),
  CONSTRAINT chk_retail_settings_env CHECK (arca_env IN ('homologacion', 'produccion')),
  CONSTRAINT chk_retail_settings_return_warranty_size CHECK (return_warranty_size_days > 0),
  CONSTRAINT chk_retail_settings_return_warranty_breakage CHECK (return_warranty_breakage_days > 0)
);

DROP TRIGGER IF EXISTS trg_retail_settings_updated_at ON retail_settings;
CREATE TRIGGER trg_retail_settings_updated_at
BEFORE UPDATE ON retail_settings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO retail_settings(id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS retail_payment_accounts (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code             TEXT NOT NULL UNIQUE,
  label            TEXT NOT NULL,
  payment_method   TEXT,
  provider         TEXT,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order       INTEGER NOT NULL DEFAULT 100,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_payment_method CHECK (payment_method IS NULL OR payment_method IN ('cash', 'debit', 'transfer', 'credit'))
);

DROP TRIGGER IF EXISTS trg_retail_payment_accounts_updated_at ON retail_payment_accounts;
CREATE TRIGGER trg_retail_payment_accounts_updated_at
BEFORE UPDATE ON retail_payment_accounts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO retail_payment_accounts(code, label, payment_method, provider, active, sort_order)
VALUES
  ('cash', 'Caja', 'cash', 'cash', TRUE, 10),
  ('bbva', 'BBVA', 'transfer', 'bbva', TRUE, 20),
  ('pbs', 'PBS', 'transfer', 'pbs', TRUE, 30),
  ('payway', 'Payway', 'credit', 'payway', TRUE, 40),
  ('transfer_1', 'Transferencia Cuenta 1', 'transfer', 'bank', TRUE, 50),
  ('transfer_2', 'Transferencia Cuenta 2', 'transfer', 'bank', TRUE, 60)
ON CONFLICT (code) DO UPDATE
SET label = EXCLUDED.label,
    payment_method = EXCLUDED.payment_method,
    provider = EXCLUDED.provider,
    active = TRUE,
    sort_order = EXCLUDED.sort_order;

CREATE TABLE IF NOT EXISTS retail_cash_sessions (
  id                           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  status                       TEXT NOT NULL DEFAULT 'open',
  opened_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  opened_by                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  opening_note                 TEXT,
  opening_amount_cash_ars      NUMERIC(14,2) NOT NULL DEFAULT 0,
  closed_at                    TIMESTAMPTZ,
  closed_by                    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  closing_note                 TEXT,
  closing_expected_total_ars   NUMERIC(14,2),
  closing_counted_total_ars    NUMERIC(14,2),
  difference_total_ars         NUMERIC(14,2),
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_cash_session_status CHECK (status IN ('open', 'closed')),
  CONSTRAINT chk_opening_amount CHECK (opening_amount_cash_ars >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_cash_sessions_updated_at ON retail_cash_sessions;
CREATE TRIGGER trg_retail_cash_sessions_updated_at
BEFORE UPDATE ON retail_cash_sessions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_cash_session_single_open
ON retail_cash_sessions ((status))
WHERE status = 'open';

CREATE TABLE IF NOT EXISTS retail_cash_session_movements (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  cash_session_id     BIGINT NOT NULL REFERENCES retail_cash_sessions(id) ON DELETE CASCADE,
  movement_type       TEXT NOT NULL,
  direction           TEXT NOT NULL,
  payment_method      TEXT,
  payment_account_id  BIGINT REFERENCES retail_payment_accounts(id) ON DELETE RESTRICT,
  amount_ars          NUMERIC(14,2) NOT NULL,
  reference_type      TEXT,
  reference_id        BIGINT,
  notes               TEXT,
  created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_cash_movement_type CHECK (movement_type IN ('opening', 'sale', 'return', 'expense', 'income', 'manual_adjustment', 'closing')),
  CONSTRAINT chk_cash_direction CHECK (direction IN ('in', 'out')),
  CONSTRAINT chk_cash_movement_method CHECK (payment_method IS NULL OR payment_method IN ('cash', 'debit', 'transfer', 'credit')),
  CONSTRAINT chk_cash_amount CHECK (amount_ars >= 0)
);

-- =============================
-- Retail catalog
-- =============================
CREATE TABLE IF NOT EXISTS retail_customers (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  full_name        TEXT NOT NULL,
  doc_type         TEXT,
  doc_number       TEXT,
  tax_id           TEXT,
  email            TEXT,
  phone            TEXT,
  address          TEXT,
  city             TEXT,
  province         TEXT,
  notes            TEXT,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_retail_customers_updated_at ON retail_customers;
CREATE TRIGGER trg_retail_customers_updated_at
BEFORE UPDATE ON retail_customers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_suppliers (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name             TEXT NOT NULL UNIQUE,
  tax_id           TEXT,
  email            TEXT,
  phone            TEXT,
  notes            TEXT,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_retail_suppliers_updated_at ON retail_suppliers;
CREATE TRIGGER trg_retail_suppliers_updated_at
BEFORE UPDATE ON retail_suppliers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_categories (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name             TEXT NOT NULL,
  parent_id        BIGINT REFERENCES retail_categories(id) ON DELETE SET NULL,
  active           BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order       INTEGER NOT NULL DEFAULT 100,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_retail_categories_updated_at ON retail_categories;
CREATE TRIGGER trg_retail_categories_updated_at
BEFORE UPDATE ON retail_categories
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE UNIQUE INDEX IF NOT EXISTS uq_retail_categories_name_ci
ON retail_categories ((LOWER(name)));

CREATE TABLE IF NOT EXISTS retail_products (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name                TEXT NOT NULL,
  description         TEXT,
  category_id         BIGINT REFERENCES retail_categories(id) ON DELETE SET NULL,
  brand               TEXT NOT NULL DEFAULT 'Las Chulas',
  season              TEXT,
  active              BOOLEAN NOT NULL DEFAULT TRUE,
  sku_prefix          TEXT,
  image_path          TEXT,
  default_cost_ars    NUMERIC(14,2) NOT NULL DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_products_cost CHECK (default_cost_ars >= 0)
);

ALTER TABLE retail_products
ADD COLUMN IF NOT EXISTS image_path TEXT;

DROP TRIGGER IF EXISTS trg_retail_products_updated_at ON retail_products;
CREATE TRIGGER trg_retail_products_updated_at
BEFORE UPDATE ON retail_products
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_retail_products_name_ci
ON retail_products ((LOWER(name)));

CREATE TABLE IF NOT EXISTS retail_variant_attributes (
  id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name                    TEXT NOT NULL,
  code                    TEXT NOT NULL,
  applies_to_category_id  BIGINT REFERENCES retail_categories(id) ON DELETE SET NULL,
  active                  BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order              INTEGER NOT NULL DEFAULT 100,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_variant_attributes_name UNIQUE (name),
  CONSTRAINT uq_retail_variant_attributes_code UNIQUE (code)
);

DROP TRIGGER IF EXISTS trg_retail_variant_attributes_updated_at ON retail_variant_attributes;
CREATE TRIGGER trg_retail_variant_attributes_updated_at
BEFORE UPDATE ON retail_variant_attributes
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_product_variants (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_id            BIGINT NOT NULL REFERENCES retail_products(id) ON DELETE CASCADE,
  option_signature      TEXT NOT NULL,
  display_name          TEXT,
  sku                   TEXT NOT NULL,
  barcode_internal      TEXT NOT NULL,
  price_store_ars       NUMERIC(14,2) NOT NULL,
  price_online_ars      NUMERIC(14,2) NOT NULL,
  cost_avg_ars          NUMERIC(14,2) NOT NULL DEFAULT 0,
  stock_on_hand         INTEGER NOT NULL DEFAULT 0,
  stock_reserved        INTEGER NOT NULL DEFAULT 0,
  stock_min             INTEGER NOT NULL DEFAULT 0,
  tiendanube_product_id BIGINT,
  tiendanube_variant_id BIGINT,
  active                BOOLEAN NOT NULL DEFAULT TRUE,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_variant_signature UNIQUE (product_id, option_signature),
  CONSTRAINT uq_retail_variant_sku UNIQUE (sku),
  CONSTRAINT uq_retail_variant_barcode UNIQUE (barcode_internal),
  CONSTRAINT chk_retail_variant_prices CHECK (price_store_ars >= 0 AND price_online_ars >= 0),
  CONSTRAINT chk_retail_variant_cost CHECK (cost_avg_ars >= 0),
  CONSTRAINT chk_retail_variant_stock CHECK (stock_reserved >= 0 AND stock_min >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_product_variants_updated_at ON retail_product_variants;
CREATE TRIGGER trg_retail_product_variants_updated_at
BEFORE UPDATE ON retail_product_variants
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_variant_option_values (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  variant_id       BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE CASCADE,
  attribute_id     BIGINT NOT NULL REFERENCES retail_variant_attributes(id) ON DELETE RESTRICT,
  option_value     TEXT NOT NULL,
  sort_order       INTEGER NOT NULL DEFAULT 100,
  CONSTRAINT uq_variant_attribute UNIQUE (variant_id, attribute_id)
);

-- =============================
-- Purchases / stock
-- =============================
CREATE TABLE IF NOT EXISTS retail_purchases (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  supplier_id      BIGINT NOT NULL REFERENCES retail_suppliers(id) ON DELETE RESTRICT,
  invoice_number   TEXT,
  purchase_date    DATE NOT NULL DEFAULT CURRENT_DATE,
  currency_code    TEXT NOT NULL DEFAULT 'ARS',
  fx_rate_ars      NUMERIC(14,4),
  notes            TEXT,
  created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_purchase_currency CHECK (currency_code IN ('ARS', 'USD')),
  CONSTRAINT chk_retail_purchase_fx CHECK ((currency_code = 'ARS' AND fx_rate_ars IS NULL) OR (currency_code = 'USD' AND fx_rate_ars IS NOT NULL AND fx_rate_ars > 0))
);

DROP TRIGGER IF EXISTS trg_retail_purchases_updated_at ON retail_purchases;
CREATE TRIGGER trg_retail_purchases_updated_at
BEFORE UPDATE ON retail_purchases
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_purchase_items (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  purchase_id         BIGINT NOT NULL REFERENCES retail_purchases(id) ON DELETE CASCADE,
  variant_id          BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  quantity            INTEGER NOT NULL,
  unit_cost_currency  NUMERIC(14,4) NOT NULL,
  unit_cost_ars       NUMERIC(14,4) NOT NULL,
  line_total_ars      NUMERIC(14,2) NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_purchase_item_qty CHECK (quantity > 0),
  CONSTRAINT chk_purchase_item_costs CHECK (unit_cost_currency >= 0 AND unit_cost_ars >= 0 AND line_total_ars >= 0)
);

CREATE TABLE IF NOT EXISTS retail_stock_movements (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  variant_id               BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  movement_kind            TEXT NOT NULL,
  qty_signed               INTEGER NOT NULL,
  stock_after              INTEGER,
  cost_unit_snapshot_ars   NUMERIC(14,4),
  reference_type           TEXT,
  reference_id             BIGINT,
  note                     TEXT,
  created_by               INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_stock_movement_kind CHECK (movement_kind IN ('purchase', 'sale', 'cancel_sale', 'return', 'manual_adjustment', 'online_sale', 'online_cancel')),
  CONSTRAINT chk_stock_qty_nonzero CHECK (qty_signed <> 0),
  CONSTRAINT chk_stock_cost_nonnegative CHECK (cost_unit_snapshot_ars IS NULL OR cost_unit_snapshot_ars >= 0)
);

-- =============================
-- Sales / returns / invoices
-- =============================
CREATE TABLE IF NOT EXISTS retail_sales (
  id                           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_number                  TEXT NOT NULL,
  channel                      TEXT NOT NULL,
  status                       TEXT NOT NULL DEFAULT 'confirmed',
  payment_method               TEXT NOT NULL,
  payment_account_id           BIGINT NOT NULL REFERENCES retail_payment_accounts(id) ON DELETE RESTRICT,
  cash_session_id              BIGINT REFERENCES retail_cash_sessions(id) ON DELETE RESTRICT,
  customer_id                  BIGINT REFERENCES retail_customers(id) ON DELETE SET NULL,
  customer_snapshot            JSONB,
  subtotal_ars                 NUMERIC(14,2) NOT NULL,
  price_adjustment_pct         NUMERIC(6,2) NOT NULL,
  price_adjustment_amount_ars  NUMERIC(14,2) NOT NULL,
  total_ars                    NUMERIC(14,2) NOT NULL,
  currency_code                TEXT NOT NULL DEFAULT 'ARS',
  requires_invoice             BOOLEAN NOT NULL DEFAULT FALSE,
  notes                        TEXT,
  source_order_id              TEXT,
  price_override_by            INTEGER REFERENCES users(id) ON DELETE SET NULL,
  price_override_reason        TEXT,
  cancelled_at                 TIMESTAMPTZ,
  cancelled_by                 INTEGER REFERENCES users(id) ON DELETE SET NULL,
  cancel_reason                TEXT,
  created_by                   INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_sales_number UNIQUE (sale_number),
  CONSTRAINT uq_retail_sales_source_order UNIQUE (source_order_id),
  CONSTRAINT chk_retail_sales_channel CHECK (channel IN ('local', 'online')),
  CONSTRAINT chk_retail_sales_status CHECK (status IN ('confirmed', 'cancelled', 'partial_return', 'returned')),
  CONSTRAINT chk_retail_sales_payment_method CHECK (payment_method IN ('cash', 'debit', 'transfer', 'credit')),
  CONSTRAINT chk_retail_sales_currency CHECK (currency_code = 'ARS'),
  CONSTRAINT chk_retail_sales_amounts CHECK (subtotal_ars >= 0 AND total_ars >= 0),
  CONSTRAINT chk_retail_sales_override_reason CHECK ((price_override_by IS NULL) OR (price_override_reason IS NOT NULL AND LENGTH(TRIM(price_override_reason)) > 0))
);

DROP TRIGGER IF EXISTS trg_retail_sales_updated_at ON retail_sales;
CREATE TRIGGER trg_retail_sales_updated_at
BEFORE UPDATE ON retail_sales
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_sale_items (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id                  BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE CASCADE,
  variant_id               BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  quantity                 INTEGER NOT NULL,
  unit_price_list_ars      NUMERIC(14,2) NOT NULL,
  unit_price_final_ars     NUMERIC(14,2) NOT NULL,
  unit_cost_snapshot_ars   NUMERIC(14,4) NOT NULL,
  line_subtotal_ars        NUMERIC(14,2) NOT NULL,
  line_total_ars           NUMERIC(14,2) NOT NULL,
  returned_qty             INTEGER NOT NULL DEFAULT 0,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_sale_item_qty CHECK (quantity > 0),
  CONSTRAINT chk_sale_item_amounts CHECK (
    unit_price_list_ars >= 0 AND
    unit_price_final_ars >= 0 AND
    unit_cost_snapshot_ars >= 0 AND
    line_subtotal_ars >= 0 AND
    line_total_ars >= 0
  ),
  CONSTRAINT chk_sale_item_returned_qty CHECK (returned_qty >= 0 AND returned_qty <= quantity)
);

CREATE TABLE IF NOT EXISTS retail_returns (
  id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id                BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE RESTRICT,
  status                 TEXT NOT NULL DEFAULT 'confirmed',
  reason                 TEXT,
  processed_by           INTEGER REFERENCES users(id) ON DELETE SET NULL,
  total_refund_ars       NUMERIC(14,2) NOT NULL DEFAULT 0,
  requires_credit_note   BOOLEAN NOT NULL DEFAULT FALSE,
  credit_note_status     TEXT NOT NULL DEFAULT 'not_required',
  warranty_type          TEXT NOT NULL DEFAULT 'none',
  warranty_override      BOOLEAN NOT NULL DEFAULT FALSE,
  warranty_snapshot      JSONB,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_return_status CHECK (status IN ('pending', 'confirmed', 'cancelled')),
  CONSTRAINT chk_return_refund CHECK (total_refund_ars >= 0),
  CONSTRAINT chk_return_credit_status CHECK (credit_note_status IN ('not_required', 'pending', 'issued', 'manual_review')),
  CONSTRAINT chk_return_warranty_type CHECK (warranty_type IN ('none', 'size', 'breakage'))
);

DROP TRIGGER IF EXISTS trg_retail_returns_updated_at ON retail_returns;
CREATE TRIGGER trg_retail_returns_updated_at
BEFORE UPDATE ON retail_returns
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_return_items (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  return_id                BIGINT NOT NULL REFERENCES retail_returns(id) ON DELETE CASCADE,
  sale_item_id             BIGINT NOT NULL REFERENCES retail_sale_items(id) ON DELETE RESTRICT,
  variant_id               BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  quantity                 INTEGER NOT NULL,
  unit_price_refund_ars    NUMERIC(14,2) NOT NULL,
  unit_cost_snapshot_ars   NUMERIC(14,4) NOT NULL,
  line_refund_total_ars    NUMERIC(14,2) NOT NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_return_item_qty CHECK (quantity > 0),
  CONSTRAINT chk_return_item_amounts CHECK (unit_price_refund_ars >= 0 AND unit_cost_snapshot_ars >= 0 AND line_refund_total_ars >= 0)
);

CREATE TABLE IF NOT EXISTS retail_invoices (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id             BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE CASCADE,
  status              TEXT NOT NULL DEFAULT 'pending',
  invoice_type        TEXT,
  invoice_mode        TEXT NOT NULL DEFAULT 'arca',
  pto_vta             INTEGER,
  cbte_tipo           INTEGER,
  cbte_nro            BIGINT,
  cae                 TEXT,
  cae_due_date        DATE,
  currency_code       TEXT NOT NULL DEFAULT 'ARS',
  amount_total_ars    NUMERIC(14,2) NOT NULL DEFAULT 0,
  request_payload     JSONB,
  response_payload    JSONB,
  error_code          TEXT,
  error_message       TEXT,
  attempts            INTEGER NOT NULL DEFAULT 0,
  last_attempt_at     TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_invoices_sale UNIQUE (sale_id),
  CONSTRAINT chk_retail_invoices_status CHECK (status IN ('pending', 'authorized', 'rejected', 'retry', 'manual_review', 'not_required')),
  CONSTRAINT chk_retail_invoices_mode CHECK (invoice_mode IN ('arca', 'internal')),
  CONSTRAINT chk_retail_invoice_currency CHECK (currency_code = 'ARS'),
  CONSTRAINT chk_retail_invoice_amount CHECK (amount_total_ars >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_invoices_updated_at ON retail_invoices;
CREATE TRIGGER trg_retail_invoices_updated_at
BEFORE UPDATE ON retail_invoices
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_invoice_credit_notes (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id             BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE RESTRICT,
  return_id           BIGINT REFERENCES retail_returns(id) ON DELETE SET NULL,
  invoice_id          BIGINT REFERENCES retail_invoices(id) ON DELETE SET NULL,
  status              TEXT NOT NULL DEFAULT 'pending',
  pto_vta             INTEGER,
  cbte_tipo           INTEGER,
  cbte_nro            BIGINT,
  cae                 TEXT,
  cae_due_date        DATE,
  amount_total_ars    NUMERIC(14,2) NOT NULL DEFAULT 0,
  request_payload     JSONB,
  response_payload    JSONB,
  error_code          TEXT,
  error_message       TEXT,
  attempts            INTEGER NOT NULL DEFAULT 0,
  created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_credit_note_status CHECK (status IN ('pending', 'authorized', 'rejected', 'retry', 'manual_review')),
  CONSTRAINT chk_credit_note_amount CHECK (amount_total_ars >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_invoice_credit_notes_updated_at ON retail_invoice_credit_notes;
CREATE TRIGGER trg_retail_invoice_credit_notes_updated_at
BEFORE UPDATE ON retail_invoice_credit_notes
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================
-- Integrations
-- =============================
CREATE TABLE IF NOT EXISTS retail_webhook_events (
  id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider           TEXT NOT NULL,
  event_type         TEXT NOT NULL,
  event_id           TEXT NOT NULL,
  external_order_id  TEXT,
  signature          TEXT,
  payload            JSONB NOT NULL,
  processed          BOOLEAN NOT NULL DEFAULT FALSE,
  processed_at       TIMESTAMPTZ,
  error_message      TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_webhook_provider_event UNIQUE (provider, event_id)
);

CREATE TABLE IF NOT EXISTS integration_jobs (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider         TEXT NOT NULL,
  job_type         TEXT NOT NULL,
  status           TEXT NOT NULL DEFAULT 'pending',
  priority         INTEGER NOT NULL DEFAULT 100,
  payload          JSONB,
  attempts         INTEGER NOT NULL DEFAULT 0,
  max_attempts     INTEGER NOT NULL DEFAULT 6,
  next_retry_at    TIMESTAMPTZ,
  last_error       TEXT,
  locked_at        TIMESTAMPTZ,
  locked_by        TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_integration_jobs_status CHECK (status IN ('pending', 'running', 'done', 'failed', 'dead_letter')),
  CONSTRAINT chk_integration_attempts CHECK (attempts >= 0 AND max_attempts > 0)
);

DROP TRIGGER IF EXISTS trg_integration_jobs_updated_at ON integration_jobs;
CREATE TRIGGER trg_integration_jobs_updated_at
BEFORE UPDATE ON integration_jobs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================
-- Indexes
-- =============================
CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_expires ON password_reset_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_permission_overrides_user ON user_permission_overrides(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_table_record ON audit_log(table_name, record_pk);

CREATE INDEX IF NOT EXISTS idx_retail_customers_name_ci ON retail_customers ((LOWER(full_name)));
CREATE INDEX IF NOT EXISTS idx_retail_customers_doc ON retail_customers(doc_number);
CREATE INDEX IF NOT EXISTS idx_retail_suppliers_name_ci ON retail_suppliers ((LOWER(name)));

CREATE INDEX IF NOT EXISTS idx_retail_variants_product ON retail_product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_retail_variants_sku_ci ON retail_product_variants ((LOWER(sku)));
CREATE INDEX IF NOT EXISTS idx_retail_variants_barcode_ci ON retail_product_variants ((LOWER(barcode_internal)));
CREATE INDEX IF NOT EXISTS idx_retail_variants_active_stock ON retail_product_variants(active, stock_on_hand);
CREATE INDEX IF NOT EXISTS idx_retail_variant_options_attr_value ON retail_variant_option_values(attribute_id, option_value);

CREATE INDEX IF NOT EXISTS idx_retail_purchases_date ON retail_purchases(purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_retail_purchases_supplier ON retail_purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_retail_purchase_items_purchase ON retail_purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_retail_purchase_items_variant ON retail_purchase_items(variant_id);
CREATE INDEX IF NOT EXISTS idx_retail_stock_mov_variant_created ON retail_stock_movements(variant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_stock_mov_ref ON retail_stock_movements(reference_type, reference_id);

CREATE INDEX IF NOT EXISTS idx_retail_sales_created ON retail_sales(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_sales_channel_status ON retail_sales(channel, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_sales_payment ON retail_sales(payment_method, payment_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_sales_cash_session ON retail_sales(cash_session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_sale_items_sale ON retail_sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_retail_sale_items_variant ON retail_sale_items(variant_id);
CREATE INDEX IF NOT EXISTS idx_retail_returns_sale ON retail_returns(sale_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_return_items_return ON retail_return_items(return_id);
CREATE INDEX IF NOT EXISTS idx_retail_invoices_status ON retail_invoices(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_invoices_cbte ON retail_invoices(pto_vta, cbte_tipo, cbte_nro);
CREATE INDEX IF NOT EXISTS idx_retail_credit_notes_status ON retail_invoice_credit_notes(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_retail_cash_sessions_status ON retail_cash_sessions(status, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_cash_mov_session ON retail_cash_session_movements(cash_session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_cash_mov_payment ON retail_cash_session_movements(payment_method, payment_account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_retail_webhook_provider_created ON retail_webhook_events(provider, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_webhook_order ON retail_webhook_events(provider, external_order_id);
CREATE INDEX IF NOT EXISTS idx_integration_jobs_status_retry ON integration_jobs(status, next_retry_at, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_integration_jobs_provider_type ON integration_jobs(provider, job_type, created_at DESC);

-- =============================
-- Audit triggers on core retail tables
-- =============================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_products') THEN
    CREATE TRIGGER trg_audit_retail_products AFTER INSERT OR UPDATE OR DELETE ON retail_products
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_product_variants') THEN
    CREATE TRIGGER trg_audit_retail_product_variants AFTER INSERT OR UPDATE OR DELETE ON retail_product_variants
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_stock_movements') THEN
    CREATE TRIGGER trg_audit_retail_stock_movements AFTER INSERT OR UPDATE OR DELETE ON retail_stock_movements
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_sales') THEN
    CREATE TRIGGER trg_audit_retail_sales AFTER INSERT OR UPDATE OR DELETE ON retail_sales
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_sale_items') THEN
    CREATE TRIGGER trg_audit_retail_sale_items AFTER INSERT OR UPDATE OR DELETE ON retail_sale_items
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_returns') THEN
    CREATE TRIGGER trg_audit_retail_returns AFTER INSERT OR UPDATE OR DELETE ON retail_returns
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_retail_invoices') THEN
    CREATE TRIGGER trg_audit_retail_invoices AFTER INSERT OR UPDATE OR DELETE ON retail_invoices
    FOR EACH ROW EXECUTE FUNCTION audit_row_change();
  END IF;
END $$;

