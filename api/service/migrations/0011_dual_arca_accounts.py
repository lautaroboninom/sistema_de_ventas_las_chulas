from django.db import migrations


SQL = r"""
CREATE TABLE IF NOT EXISTS retail_arca_accounts (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  code                  TEXT NOT NULL UNIQUE,
  label                 TEXT NOT NULL,
  active                BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order            INTEGER NOT NULL DEFAULT 100,
  arca_cuit             TEXT,
  arca_pto_vta_store    INTEGER,
  arca_pto_vta_online   INTEGER,
  arca_cbte_tipo_store  INTEGER,
  arca_cbte_tipo_online INTEGER,
  arca_cert_path        TEXT,
  arca_key_path         TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_arca_accounts_sort_order CHECK (sort_order >= 0),
  CONSTRAINT chk_retail_arca_accounts_pto_store CHECK (arca_pto_vta_store IS NULL OR arca_pto_vta_store > 0),
  CONSTRAINT chk_retail_arca_accounts_pto_online CHECK (arca_pto_vta_online IS NULL OR arca_pto_vta_online > 0),
  CONSTRAINT chk_retail_arca_accounts_cbte_store CHECK (arca_cbte_tipo_store IS NULL OR arca_cbte_tipo_store > 0),
  CONSTRAINT chk_retail_arca_accounts_cbte_online CHECK (arca_cbte_tipo_online IS NULL OR arca_cbte_tipo_online > 0)
);

DROP TRIGGER IF EXISTS trg_retail_arca_accounts_updated_at ON retail_arca_accounts;
CREATE TRIGGER trg_retail_arca_accounts_updated_at
BEFORE UPDATE ON retail_arca_accounts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS retail_arca_rotation_state (
  id               SMALLINT PRIMARY KEY DEFAULT 1,
  last_account_id  BIGINT REFERENCES retail_arca_accounts(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_retail_arca_rotation_state_singleton CHECK (id = 1)
);

DROP TRIGGER IF EXISTS trg_retail_arca_rotation_state_updated_at ON retail_arca_rotation_state;
CREATE TRIGGER trg_retail_arca_rotation_state_updated_at
BEFORE UPDATE ON retail_arca_rotation_state
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO retail_arca_rotation_state(id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE retail_invoices
  ADD COLUMN IF NOT EXISTS arca_account_id BIGINT REFERENCES retail_arca_accounts(id) ON DELETE RESTRICT;

ALTER TABLE retail_invoice_credit_notes
  ADD COLUMN IF NOT EXISTS arca_account_id BIGINT REFERENCES retail_arca_accounts(id) ON DELETE RESTRICT;

DO $$
DECLARE legacy_account_id BIGINT;
BEGIN
  INSERT INTO retail_arca_accounts(
    code, label, active, sort_order,
    arca_cuit, arca_pto_vta_store, arca_pto_vta_online,
    arca_cbte_tipo_store, arca_cbte_tipo_online,
    arca_cert_path, arca_key_path
  )
  SELECT
    'legacy-primary',
    'Cuenta ARCA principal',
    TRUE,
    10,
    arca_cuit,
    COALESCE(arca_pto_vta_store, 1),
    COALESCE(arca_pto_vta_online, COALESCE(arca_pto_vta_store, 1)),
    COALESCE(arca_cbte_tipo_store, 6),
    COALESCE(arca_cbte_tipo_online, COALESCE(arca_cbte_tipo_store, 6)),
    arca_cert_path,
    arca_key_path
  FROM retail_settings
  WHERE id = 1
  ON CONFLICT (code) DO NOTHING;

  INSERT INTO retail_arca_accounts(
    code, label, active, sort_order,
    arca_pto_vta_store, arca_pto_vta_online,
    arca_cbte_tipo_store, arca_cbte_tipo_online
  )
  VALUES (
    'arca-secondary',
    'Cuenta ARCA secundaria',
    FALSE,
    20,
    1,
    1,
    6,
    6
  )
  ON CONFLICT (code) DO NOTHING;

  SELECT id
  INTO legacy_account_id
  FROM retail_arca_accounts
  WHERE code = 'legacy-primary'
  LIMIT 1;

  IF legacy_account_id IS NOT NULL THEN
    UPDATE retail_invoices
    SET arca_account_id = legacy_account_id
    WHERE arca_account_id IS NULL;

    UPDATE retail_invoice_credit_notes cn
    SET arca_account_id = COALESCE(cn.arca_account_id, i.arca_account_id, legacy_account_id)
    FROM retail_invoices i
    WHERE cn.invoice_id = i.id
      AND cn.arca_account_id IS NULL;

    UPDATE retail_invoice_credit_notes
    SET arca_account_id = legacy_account_id
    WHERE arca_account_id IS NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_retail_invoices_arca_account ON retail_invoices(arca_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_retail_credit_notes_arca_account ON retail_invoice_credit_notes(arca_account_id, created_at DESC);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0010_store_credit_payment_support'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
