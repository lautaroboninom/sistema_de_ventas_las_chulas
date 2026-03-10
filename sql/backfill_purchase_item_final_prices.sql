-- backfill_purchase_item_final_prices.sql
-- Completa precio final faltante desde precio sugerido y recalcula margen real.
-- Idempotente para PostgreSQL.

UPDATE retail_purchase_items
SET unit_price_final_ars = unit_price_suggested_ars
WHERE unit_price_final_ars IS NULL
  AND unit_price_suggested_ars IS NOT NULL;

UPDATE retail_purchase_items
SET real_margin_pct = ROUND((((unit_price_final_ars - unit_cost_ars) / unit_cost_ars) * 100.0)::numeric, 2)
WHERE unit_price_final_ars IS NOT NULL
  AND unit_cost_ars > 0
  AND real_margin_pct IS NULL;
