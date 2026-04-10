from django.db import migrations


SQL = r"""
ALTER TABLE retail_payment_accounts
  DROP CONSTRAINT IF EXISTS chk_payment_method;
ALTER TABLE retail_payment_accounts
  ADD CONSTRAINT chk_payment_method
  CHECK (payment_method IS NULL OR payment_method IN ('cash', 'debit', 'transfer', 'credit', 'store_credit'));

INSERT INTO retail_payment_accounts(code, label, payment_method, provider, active, sort_order)
VALUES ('store_credit', 'Credito tienda', 'store_credit', 'internal', TRUE, 70)
ON CONFLICT (code) DO UPDATE
SET label = EXCLUDED.label,
    payment_method = EXCLUDED.payment_method,
    provider = EXCLUDED.provider,
    active = TRUE,
    sort_order = EXCLUDED.sort_order;

ALTER TABLE retail_cash_session_movements
  DROP CONSTRAINT IF EXISTS chk_cash_movement_type;
ALTER TABLE retail_cash_session_movements
  ADD CONSTRAINT chk_cash_movement_type
  CHECK (movement_type IN ('opening', 'sale', 'return', 'expense', 'income', 'manual_adjustment', 'exchange_settlement', 'closing'));

ALTER TABLE retail_cash_session_movements
  DROP CONSTRAINT IF EXISTS chk_cash_movement_method;
ALTER TABLE retail_cash_session_movements
  ADD CONSTRAINT chk_cash_movement_method
  CHECK (payment_method IS NULL OR payment_method IN ('cash', 'debit', 'transfer', 'credit', 'store_credit'));

ALTER TABLE retail_sales
  DROP CONSTRAINT IF EXISTS chk_retail_sales_payment_method;
ALTER TABLE retail_sales
  ADD CONSTRAINT chk_retail_sales_payment_method
  CHECK (payment_method IN ('cash', 'debit', 'transfer', 'credit', 'store_credit'));

ALTER TABLE retail_sale_payments
  DROP CONSTRAINT IF EXISTS chk_sale_payment_method;
ALTER TABLE retail_sale_payments
  ADD CONSTRAINT chk_sale_payment_method
  CHECK (payment_method IN ('cash', 'debit', 'transfer', 'credit', 'store_credit'));
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0009_retail_operacion_inventory_alertas'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
