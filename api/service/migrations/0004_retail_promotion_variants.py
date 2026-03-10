from django.db import migrations


SQL = r"""
CREATE TABLE IF NOT EXISTS retail_promotion_variants (
  id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  promotion_id     BIGINT NOT NULL REFERENCES retail_promotions(id) ON DELETE CASCADE,
  variant_id       BIGINT NOT NULL REFERENCES retail_product_variants(id) ON DELETE RESTRICT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_retail_promotion_variant UNIQUE (promotion_id, variant_id)
);

CREATE INDEX IF NOT EXISTS idx_retail_promotion_variants_promotion ON retail_promotion_variants(promotion_id);
CREATE INDEX IF NOT EXISTS idx_retail_promotion_variants_variant ON retail_promotion_variants(variant_id);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0003_retail_promotions_and_exchanges'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
