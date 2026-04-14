from django.db import migrations


SQL = r"""
ALTER TABLE retail_settings
  ADD COLUMN IF NOT EXISTS db_apply_probe_marker TEXT;

UPDATE retail_settings
SET db_apply_probe_marker = 'v2026_04_probe'
WHERE id = 1
  AND (db_apply_probe_marker IS NULL OR TRIM(db_apply_probe_marker) = '');
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0012_payment_account_invoice_rules'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]

