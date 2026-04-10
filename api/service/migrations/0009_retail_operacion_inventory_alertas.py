from django.db import migrations


SQL = r"""
CREATE TABLE IF NOT EXISTS retail_store_credits (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_id         BIGINT REFERENCES retail_customers(id) ON DELETE SET NULL,
  source_sale_id      BIGINT REFERENCES retail_sales(id) ON DELETE SET NULL,
  source_return_id    BIGINT REFERENCES retail_returns(id) ON DELETE SET NULL,
  status              TEXT NOT NULL DEFAULT 'active',
  amount_total_ars    NUMERIC(14,2) NOT NULL DEFAULT 0,
  amount_balance_ars  NUMERIC(14,2) NOT NULL DEFAULT 0,
  note                TEXT,
  issued_by           INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_store_credits_status CHECK (status IN ('active', 'consumed', 'void')),
  CONSTRAINT chk_retail_store_credits_amounts CHECK (amount_total_ars >= 0 AND amount_balance_ars >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_store_credits_updated_at ON retail_store_credits;
CREATE TRIGGER trg_retail_store_credits_updated_at
BEFORE UPDATE ON retail_store_credits
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_store_credit_movements (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  credit_id        BIGINT NOT NULL REFERENCES retail_store_credits(id) ON DELETE CASCADE,
  movement_type    TEXT NOT NULL,
  amount_ars       NUMERIC(14,2) NOT NULL,
  sale_id          BIGINT REFERENCES retail_sales(id) ON DELETE SET NULL,
  return_id        BIGINT REFERENCES retail_returns(id) ON DELETE SET NULL,
  note             TEXT,
  created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_store_credit_mov_type CHECK (movement_type IN ('issue', 'consume', 'adjustment', 'void')),
  CONSTRAINT chk_retail_store_credit_mov_amount CHECK (amount_ars > 0)
);

ALTER TABLE retail_returns
  ADD COLUMN IF NOT EXISTS refund_mode TEXT;
ALTER TABLE retail_returns
  ADD COLUMN IF NOT EXISTS store_credit_id BIGINT;

UPDATE retail_returns
SET refund_mode = COALESCE(NULLIF(TRIM(refund_mode), ''), 'cash_return')
WHERE refund_mode IS NULL OR TRIM(refund_mode) = '';

ALTER TABLE retail_returns
  ALTER COLUMN refund_mode SET DEFAULT 'cash_return';
ALTER TABLE retail_returns
  ALTER COLUMN refund_mode SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_returns_refund_mode'
  ) THEN
    ALTER TABLE retail_returns
      ADD CONSTRAINT chk_retail_returns_refund_mode
      CHECK (refund_mode IN ('cash_return', 'store_credit'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_retail_returns_store_credit'
  ) THEN
    ALTER TABLE retail_returns
      ADD CONSTRAINT fk_retail_returns_store_credit
      FOREIGN KEY (store_credit_id)
      REFERENCES retail_store_credits(id)
      ON DELETE SET NULL;
  END IF;
END $$;

ALTER TABLE retail_exchanges
  ADD COLUMN IF NOT EXISTS settlement_mode TEXT;
ALTER TABLE retail_exchanges
  ADD COLUMN IF NOT EXISTS settlement_amount_ars NUMERIC(14,2);
ALTER TABLE retail_exchanges
  ADD COLUMN IF NOT EXISTS store_credit_id BIGINT;

UPDATE retail_exchanges
SET settlement_mode = COALESCE(NULLIF(TRIM(settlement_mode), ''), 'even'),
    settlement_amount_ars = COALESCE(settlement_amount_ars, 0)
WHERE settlement_mode IS NULL OR settlement_amount_ars IS NULL;

ALTER TABLE retail_exchanges
  ALTER COLUMN settlement_mode SET DEFAULT 'even';
ALTER TABLE retail_exchanges
  ALTER COLUMN settlement_mode SET NOT NULL;

ALTER TABLE retail_exchanges
  ALTER COLUMN settlement_amount_ars SET DEFAULT 0;
ALTER TABLE retail_exchanges
  ALTER COLUMN settlement_amount_ars SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_exchanges_settlement_mode'
  ) THEN
    ALTER TABLE retail_exchanges
      ADD CONSTRAINT chk_retail_exchanges_settlement_mode
      CHECK (settlement_mode IN ('even', 'customer_owes', 'store_owes', 'store_credit'));
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'chk_retail_exchanges_settlement_amount'
  ) THEN
    ALTER TABLE retail_exchanges
      ADD CONSTRAINT chk_retail_exchanges_settlement_amount
      CHECK (settlement_amount_ars >= 0);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_retail_exchanges_store_credit'
  ) THEN
    ALTER TABLE retail_exchanges
      ADD CONSTRAINT fk_retail_exchanges_store_credit
      FOREIGN KEY (store_credit_id)
      REFERENCES retail_store_credits(id)
      ON DELETE SET NULL;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS retail_operation_incidents (
  id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source              TEXT NOT NULL,
  severity            TEXT NOT NULL DEFAULT 'medium',
  action_required     TEXT NOT NULL,
  sla_minutes         INTEGER NOT NULL DEFAULT 120,
  status              TEXT NOT NULL DEFAULT 'open',
  title               TEXT NOT NULL,
  detail              TEXT,
  related_entity_type TEXT,
  related_entity_id   BIGINT,
  payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_by          INTEGER REFERENCES users(id) ON DELETE SET NULL,
  resolved_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
  resolution_note     TEXT,
  resolved_at         TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_operation_incidents_source CHECK (source IN ('arca', 'online', 'pos', 'caja', 'inventario', 'alertas', 'postventa')),
  CONSTRAINT chk_retail_operation_incidents_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  CONSTRAINT chk_retail_operation_incidents_status CHECK (status IN ('open', 'in_progress', 'acknowledged', 'resolved', 'dismissed')),
  CONSTRAINT chk_retail_operation_incidents_sla CHECK (sla_minutes >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_operation_incidents_updated_at ON retail_operation_incidents;
CREATE TRIGGER trg_retail_operation_incidents_updated_at
BEFORE UPDATE ON retail_operation_incidents
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_inventory_counts (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code             TEXT NOT NULL,
  status           TEXT NOT NULL DEFAULT 'draft',
  scope            TEXT NOT NULL DEFAULT 'all',
  reason           TEXT,
  started_at       TIMESTAMPTZ,
  closed_at        TIMESTAMPTZ,
  created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  closed_by        INTEGER REFERENCES users(id) ON DELETE SET NULL,
  snapshot         JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_inventory_counts_code UNIQUE (code),
  CONSTRAINT chk_retail_inventory_counts_status CHECK (status IN ('draft', 'in_progress', 'closed', 'cancelled')),
  CONSTRAINT chk_retail_inventory_counts_scope CHECK (scope IN ('all', 'low_stock', 'custom'))
);

DROP TRIGGER IF EXISTS trg_retail_inventory_counts_updated_at ON retail_inventory_counts;
CREATE TRIGGER trg_retail_inventory_counts_updated_at
BEFORE UPDATE ON retail_inventory_counts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_inventory_count_items (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  count_id          BIGINT NOT NULL REFERENCES retail_inventory_counts(id) ON DELETE CASCADE,
  variant_id        BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  expected_qty      INTEGER NOT NULL,
  counted_qty       INTEGER,
  diff_qty          INTEGER NOT NULL DEFAULT 0,
  adjustment_reason TEXT,
  adjusted_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
  adjusted_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_inventory_count_items UNIQUE (count_id, variant_id)
);

DROP TRIGGER IF EXISTS trg_retail_inventory_count_items_updated_at ON retail_inventory_count_items;
CREATE TRIGGER trg_retail_inventory_count_items_updated_at
BEFORE UPDATE ON retail_inventory_count_items
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_operation_alerts (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  source           TEXT NOT NULL,
  severity         TEXT NOT NULL DEFAULT 'medium',
  action_required  TEXT NOT NULL,
  sla_minutes      INTEGER NOT NULL DEFAULT 120,
  status           TEXT NOT NULL DEFAULT 'open',
  title            TEXT NOT NULL,
  detail           TEXT,
  payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
  fingerprint      TEXT NOT NULL,
  first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  acknowledged_at  TIMESTAMPTZ,
  acknowledged_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_operation_alerts_fingerprint UNIQUE (fingerprint),
  CONSTRAINT chk_retail_operation_alerts_source CHECK (source IN ('arca', 'online', 'pos', 'caja', 'inventario', 'alertas', 'postventa')),
  CONSTRAINT chk_retail_operation_alerts_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
  CONSTRAINT chk_retail_operation_alerts_status CHECK (status IN ('open', 'acknowledged', 'resolved')),
  CONSTRAINT chk_retail_operation_alerts_sla CHECK (sla_minutes >= 0)
);

DROP TRIGGER IF EXISTS trg_retail_operation_alerts_updated_at ON retail_operation_alerts;
CREATE TRIGGER trg_retail_operation_alerts_updated_at
BEFORE UPDATE ON retail_operation_alerts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS idx_retail_store_credits_status ON retail_store_credits(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_store_credit_mov_credit ON retail_store_credit_movements(credit_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_operation_incidents_status ON retail_operation_incidents(status, severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_operation_incidents_source ON retail_operation_incidents(source, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_inventory_counts_status ON retail_inventory_counts(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_inventory_count_items_count ON retail_inventory_count_items(count_id, id);
CREATE INDEX IF NOT EXISTS idx_retail_operation_alerts_status ON retail_operation_alerts(status, severity, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_operation_alerts_source ON retail_operation_alerts(source, created_at DESC);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0008_retail_ean13_and_variant_barcodes'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
