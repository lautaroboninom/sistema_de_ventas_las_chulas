from django.db import migrations


SQL = r"""
UPDATE retail_purchase_items
SET unit_price_final_ars = unit_price_suggested_ars
WHERE unit_price_final_ars IS NULL
  AND unit_price_suggested_ars IS NOT NULL;

UPDATE retail_purchase_items
SET real_margin_pct = ROUND((((unit_price_final_ars - unit_cost_ars) / unit_cost_ars) * 100.0)::numeric, 2)
WHERE unit_price_final_ars IS NOT NULL
  AND unit_cost_ars > 0
  AND real_margin_pct IS NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0005_retail_purchase_pricing_and_reports'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
