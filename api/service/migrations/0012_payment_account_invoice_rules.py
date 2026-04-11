from django.db import migrations


SQL = r"""
ALTER TABLE retail_payment_accounts
  ADD COLUMN IF NOT EXISTS price_modifier_pct NUMERIC(6,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS default_arca_account_id BIGINT REFERENCES retail_arca_accounts(id) ON DELETE SET NULL;

ALTER TABLE retail_payment_accounts
  DROP CONSTRAINT IF EXISTS chk_retail_payment_accounts_modifier_min;
ALTER TABLE retail_payment_accounts
  ADD CONSTRAINT chk_retail_payment_accounts_modifier_min CHECK (price_modifier_pct > -100);

CREATE INDEX IF NOT EXISTS idx_retail_payment_accounts_default_arca
  ON retail_payment_accounts(default_arca_account_id);

UPDATE retail_payment_accounts
SET price_modifier_pct = CASE LOWER(COALESCE(payment_method, ''))
  WHEN 'cash' THEN -10
  WHEN 'credit' THEN 10
  ELSE 0
END
WHERE price_modifier_pct IS NULL
   OR price_modifier_pct = 0;

DO $$
DECLARE first_active_arca_id BIGINT;
BEGIN
  SELECT id
  INTO first_active_arca_id
  FROM retail_arca_accounts
  WHERE active = TRUE
  ORDER BY sort_order, id
  LIMIT 1;

  IF first_active_arca_id IS NOT NULL THEN
    UPDATE retail_payment_accounts
    SET default_arca_account_id = first_active_arca_id
    WHERE default_arca_account_id IS NULL
      AND LOWER(COALESCE(payment_method, '')) IN ('debit', 'transfer', 'credit');
  END IF;
END $$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0011_dual_arca_accounts'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
