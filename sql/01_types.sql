-- 01_types.sql
-- Enumerated types used by the application. All changes are idempotent and safe.

BEGIN;

-- motivo_ingreso
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='motivo_ingreso') THEN
    EXECUTE $$CREATE TYPE motivo_ingreso AS ENUM
      ('reparación','service preventivo','baja alquiler','reparación alquiler','otros')$$;
  END IF;
END$$;

-- ticket_state (main ingreso state)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='ticket_state') THEN
    EXECUTE $$CREATE TYPE ticket_state AS ENUM
      ('ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','derivado','liberado','alquilado')$$;
  END IF;
  -- Ensure values that may be missing on legacy DBs
  BEGIN
    ALTER TYPE ticket_state ADD VALUE IF NOT EXISTS 'liberado';
  EXCEPTION WHEN duplicate_object THEN NULL; END;
  BEGIN
    ALTER TYPE ticket_state ADD VALUE IF NOT EXISTS 'alquilado';
  EXCEPTION WHEN duplicate_object THEN NULL; END;
END$$;

-- quote_state (heads of quotes)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='quote_state') THEN
    EXECUTE $$CREATE TYPE quote_state AS ENUM ('pendiente','emitido','aprobado','rechazado')$$;
  END IF;
  -- Allow mapping from emitido -> presupuestado used in ingresos.presupuesto_estado
  BEGIN
    ALTER TYPE quote_state ADD VALUE IF NOT EXISTS 'presupuestado';
  EXCEPTION WHEN duplicate_object THEN NULL; END;
END$$;

-- external_state (derivaciones a servicio externo)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='external_state') THEN
    EXECUTE $$CREATE TYPE external_state AS ENUM ('derivado','en_servicio','devuelto','entregado_cliente')$$;
  END IF;
END$$;

-- disposition (disposición del equipo)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='disposition') THEN
    EXECUTE $$CREATE TYPE disposition AS ENUM ('normal','para_repuesto')$$;
  END IF;
END$$;

-- resolucion_reparacion (veredicto/resolución)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'resolucion_reparacion') THEN
    CREATE TYPE resolucion_reparacion AS ENUM ('reparado','no_reparado','no_se_encontro_falla','presupuesto_rechazado');
  END IF;
END $$;

-- Backward-compatible rename if old type name exists
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'veredicto_reparacion') AND
     NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'resolucion_reparacion') THEN
    ALTER TYPE veredicto_reparacion RENAME TO resolucion_reparacion;
  END IF;
END $$;

-- Ensure all required enum labels exist on resolucion_reparacion
DO $$ BEGIN
  IF NOT EXISTS (
      SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
      WHERE t.typname='resolucion_reparacion' AND e.enumlabel='no_reparado'
  ) THEN
    ALTER TYPE resolucion_reparacion ADD VALUE IF NOT EXISTS 'no_reparado';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
      WHERE t.typname='resolucion_reparacion' AND e.enumlabel='no_se_encontro_falla'
  ) THEN
    ALTER TYPE resolucion_reparacion ADD VALUE IF NOT EXISTS 'no_se_encontro_falla';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
      WHERE t.typname='resolucion_reparacion' AND e.enumlabel='presupuesto_rechazado'
  ) THEN
    ALTER TYPE resolucion_reparacion ADD VALUE IF NOT EXISTS 'presupuesto_rechazado';
  END IF;
END $$;

COMMIT;

