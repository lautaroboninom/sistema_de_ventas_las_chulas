BEGIN;

-- =========================================================
-- Campos nuevos en ingresos
-- =========================================================
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ingresos' AND column_name='garantia_reparacion'
  ) THEN
    ALTER TABLE public.ingresos
      ADD COLUMN garantia_reparacion boolean NOT NULL DEFAULT false;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ingresos' AND column_name='faja_garantia'
  ) THEN
    ALTER TABLE public.ingresos
      ADD COLUMN faja_garantia text NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ingresos' AND column_name='remito_salida'
  ) THEN
    ALTER TABLE public.ingresos
      ADD COLUMN remito_salida text NULL,
      ADD COLUMN factura_numero text NULL,
      ADD COLUMN fecha_entrega timestamptz NULL;
  END IF;
END $$;

-- Datos de alquiler por ingreso (registro del movimiento)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ingresos' AND column_name='alquilado'
  ) THEN
    ALTER TABLE public.ingresos
      ADD COLUMN alquilado boolean NOT NULL DEFAULT false,
      ADD COLUMN alquiler_a text NULL,
      ADD COLUMN alquiler_remito text NULL,
      ADD COLUMN alquiler_fecha date NULL;
  END IF;
END $$;

-- =========================================================
-- Models: tipo de equipo
-- =========================================================
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='models' AND column_name='tipo_equipo'
  ) THEN
    ALTER TABLE public.models
      ADD COLUMN tipo_equipo text NULL;
    CREATE INDEX IF NOT EXISTS idx_models_tipo_equipo ON public.models ((COALESCE(tipo_equipo,'')));
  END IF;
END $$;

-- =========================================================
-- ingreso_events (si faltara)
-- =========================================================
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='ingreso_events'
  ) THEN
    CREATE TABLE public.ingreso_events(
      id serial PRIMARY KEY,
      ingreso_id int NOT NULL REFERENCES public.ingresos(id) ON DELETE CASCADE,
      de_estado ingreso_state NULL,
      a_estado  ingreso_state NOT NULL,
      usuario_id int NULL REFERENCES public.users(id),
      ts timestamptz NOT NULL DEFAULT now(),
      comentario text
    );
    CREATE INDEX IF NOT EXISTS idx_events_ingreso ON public.ingreso_events(ingreso_id);
  END IF;
END $$;

-- =========================================================
-- audit_log (append-only)
-- =========================================================
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='audit_log'
  ) THEN
    CREATE TABLE public.audit_log(
      id bigserial PRIMARY KEY,
      ts timestamptz NOT NULL DEFAULT now(),
      user_id int NULL REFERENCES public.users(id),
      role text NULL,
      method text NOT NULL,
      path text NOT NULL,
      ip inet NULL,
      user_agent text NULL,
      status_code int NULL,
      body jsonb NULL,
      note text NULL
    );
    CREATE INDEX IF NOT EXISTS idx_audit_ts ON public.audit_log(ts DESC);
    CREATE INDEX IF NOT EXISTS idx_audit_user ON public.audit_log(user_id);
  END IF;
END $$;

COMMIT;
