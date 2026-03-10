FROM postgres:16

# Load bootstrap SQL from image to avoid host bind-mount issues on mapped/network drives.
COPY sql/schema.sql /docker-entrypoint-initdb.d/001_schema.sql
COPY sql/migrate_warranty_returns.sql /docker-entrypoint-initdb.d/010_migrate_warranty_returns.sql
COPY sql/migrate_purchase_pricing_and_reports.sql /docker-entrypoint-initdb.d/020_migrate_purchase_pricing_and_reports.sql
COPY sql/backfill_purchase_item_final_prices.sql /docker-entrypoint-initdb.d/030_backfill_purchase_item_final_prices.sql
COPY sql/migrate_pos_drafts_split_payments.sql /docker-entrypoint-initdb.d/040_migrate_pos_drafts_split_payments.sql
