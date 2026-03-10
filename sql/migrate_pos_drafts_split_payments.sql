CREATE TABLE IF NOT EXISTS retail_sale_payments (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  sale_id             BIGINT NOT NULL REFERENCES retail_sales(id) ON DELETE CASCADE,
  payment_method      TEXT NOT NULL,
  payment_account_id  BIGINT NOT NULL REFERENCES retail_payment_accounts(id) ON DELETE RESTRICT,
  amount_ars          NUMERIC(14,2) NOT NULL,
  metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_sale_payment_method CHECK (payment_method IN ('cash', 'debit', 'transfer', 'credit')),
  CONSTRAINT chk_sale_payment_amount CHECK (amount_ars > 0)
);

CREATE INDEX IF NOT EXISTS idx_retail_sale_payments_sale
ON retail_sale_payments(sale_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_retail_sale_payments_method
ON retail_sale_payments(payment_method, payment_account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS retail_pos_drafts (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  draft_number        TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'open',
  channel             TEXT NOT NULL DEFAULT 'local',
  name                TEXT,
  customer_snapshot   JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
  quote_snapshot      JSONB NOT NULL DEFAULT '{}'::jsonb,
  item_count          INTEGER NOT NULL DEFAULT 0,
  total_ars           NUMERIC(14,2) NOT NULL DEFAULT 0,
  last_activity_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_sale_id   BIGINT REFERENCES retail_sales(id) ON DELETE SET NULL,
  confirmed_at        TIMESTAMPTZ,
  created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
  updated_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_pos_draft_number UNIQUE (draft_number),
  CONSTRAINT chk_retail_pos_draft_status CHECK (status IN ('open', 'confirmed', 'cancelled')),
  CONSTRAINT chk_retail_pos_draft_channel CHECK (channel IN ('local', 'online')),
  CONSTRAINT chk_retail_pos_draft_item_count CHECK (item_count >= 0),
  CONSTRAINT chk_retail_pos_draft_total CHECK (total_ars >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_pos_drafts_updated_at ON retail_pos_drafts;
CREATE TRIGGER trg_retail_pos_drafts_updated_at
BEFORE UPDATE ON retail_pos_drafts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_retail_pos_drafts_status
ON retail_pos_drafts(status, last_activity_at DESC);

CREATE INDEX IF NOT EXISTS idx_retail_pos_drafts_customer
ON retail_pos_drafts((LOWER(COALESCE(customer_snapshot->>'name',''))));

CREATE INDEX IF NOT EXISTS idx_retail_pos_drafts_confirmed_sale
ON retail_pos_drafts(confirmed_sale_id);
