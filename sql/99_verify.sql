-- 99_verify.sql
-- Automatic verification checklist. Run after full setup. Re-runnable.

BEGIN;

-- Tables existence
SELECT 'table ingresos exists' AS check, to_regclass('public.ingresos') IS NOT NULL AS ok;
SELECT 'table ingreso_events exists' AS check, to_regclass('public.ingreso_events') IS NOT NULL AS ok;
SELECT 'table quotes exists' AS check, to_regclass('public.quotes') IS NOT NULL AS ok;
SELECT 'table quote_items exists' AS check, to_regclass('public.quote_items') IS NOT NULL AS ok;
SELECT 'table customers exists' AS check, to_regclass('public.customers') IS NOT NULL AS ok;
SELECT 'table devices exists' AS check, to_regclass('public.devices') IS NOT NULL AS ok;
SELECT 'table locations exists' AS check, to_regclass('public.locations') IS NOT NULL AS ok;
SELECT 'table equipos_derivados exists' AS check, to_regclass('public.equipos_derivados') IS NOT NULL AS ok;
SELECT 'table handoffs exists' AS check, to_regclass('public.handoffs') IS NOT NULL AS ok;

-- Critical columns
SELECT 'ingreso_events.ingreso_id column' AS check,
       EXISTS (
         SELECT 1 FROM information_schema.columns
         WHERE table_schema='public' AND table_name='ingreso_events' AND column_name='ingreso_id'
       ) AS ok;

SELECT 'quotes has ingreso_id and no ticket_id' AS check,
       (EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema='public' AND table_name='quotes' AND column_name='ingreso_id'
        ) AND NOT EXISTS (
          SELECT 1 FROM information_schema.columns
          WHERE table_schema='public' AND table_name='quotes' AND column_name='ticket_id'
        )) AS ok;

-- FKs operational
SELECT 'FK ingreso_events.ingreso_id -> ingresos.id' AS check,
  EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.ingreso_events'::regclass AND conname='ingreso_events_ingreso_id_fkey'
  ) AS ok;

SELECT 'FK quotes.ingreso_id -> ingresos.id' AS check,
  EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.quotes'::regclass AND conname='quotes_ingreso_id_fkey'
  ) AS ok;

-- Functions present
SELECT 'fn log_ingreso_state() exists' AS check,
  EXISTS (SELECT 1 FROM pg_proc WHERE proname='log_ingreso_state' AND pg_function_is_visible(oid)) AS ok;

SELECT 'fn sync_quote_with_ingreso() exists' AS check,
  EXISTS (SELECT 1 FROM pg_proc WHERE proname='sync_quote_with_ingreso' AND pg_function_is_visible(oid)) AS ok;

SELECT 'fn recalc_quote_subtotal(int) exists' AS check,
  EXISTS (SELECT 1 FROM pg_proc WHERE proname='recalc_quote_subtotal' AND pg_function_is_visible(oid)) AS ok;

-- Triggers bound
SELECT 'trg_ingreso_state_log_insert on ingresos' AS check,
  EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgrelid='public.ingresos'::regclass AND tgname='trg_ingreso_state_log_insert'
  ) AS ok;

SELECT 'trg_ingreso_state_log_update on ingresos' AS check,
  EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgrelid='public.ingresos'::regclass AND tgname='trg_ingreso_state_log_update'
  ) AS ok;

SELECT 'trg_quote_sync_upd on quotes' AS check,
  EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgrelid='public.quotes'::regclass AND tgname='trg_quote_sync_upd'
  ) AS ok;

-- Policies and RLS
SELECT 'RLS enabled on ingresos' AS check,
  (SELECT relrowsecurity FROM pg_class WHERE oid='public.ingresos'::regclass) AS ok;
SELECT 'policy p_quotes_select exists' AS check,
  EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='quotes' AND policyname='p_quotes_select') AS ok;
SELECT 'policy p_quote_items_select exists' AS check,
  EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='quote_items' AND policyname='p_quote_items_select') AS ok;

-- Indexes critical
SELECT 'idx_events_ingreso exists' AS check,
  to_regclass('public.idx_events_ingreso') IS NOT NULL AS ok;
SELECT 'idx_events_ingreso_estado_ts exists' AS check,
  to_regclass('public.idx_events_ingreso_estado_ts') IS NOT NULL AS ok;
SELECT 'idx_quote_items_quote exists' AS check,
  to_regclass('public.idx_quote_items_quote') IS NOT NULL AS ok;
SELECT 'idx_ingresos_estado exists' AS check,
  to_regclass('public.idx_ingresos_estado') IS NOT NULL AS ok;

COMMIT;

