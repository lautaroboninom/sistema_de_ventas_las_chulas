BEGIN;

-- ======================================================
-- Enums (creación condicional)  // Usamos TICKET_STATE
-- ======================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='motivo_ingreso') THEN
    EXECUTE $$CREATE TYPE motivo_ingreso AS ENUM
      ('reparación','service preventivo','baja alquiler','reparación alquiler','otros')$$;
  END IF;

  -- IMPORTANTE: mantener el tipo real de la columna (ticket_state)
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='ticket_state') THEN
    EXECUTE $$CREATE TYPE ticket_state AS ENUM
      ('ingresado','diagnosticado',
       'presupuestado','reparar','reparado','entregado',
       'derivado','liberado','alquilado')$$;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='quote_state') THEN
    EXECUTE $$CREATE TYPE quote_state AS ENUM ('pendiente','emitido','aprobado','rechazado')$$;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='external_state') THEN
    EXECUTE $$CREATE TYPE external_state AS ENUM ('derivado','devuelto')$$;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='disposition') THEN
    EXECUTE $$CREATE TYPE disposition AS ENUM ('normal','para_repuesto')$$;
  END IF;
END$$;


-- NECESARIO para poder guardar 'presupuestado' en ingresos.presupuesto_estado (quote_state)
ALTER TYPE quote_state  ADD VALUE IF NOT EXISTS 'presupuestado';

-- Asegurar estados 'liberado' y 'alquilado' en ticket_state
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname='ticket_state') THEN
    BEGIN
      ALTER TYPE ticket_state ADD VALUE IF NOT EXISTS 'liberado';
    EXCEPTION WHEN duplicate_object THEN
      -- ignorar si ya existe
      NULL;
    END;
    BEGIN
      ALTER TYPE ticket_state ADD VALUE IF NOT EXISTS 'alquilado';
    EXCEPTION WHEN duplicate_object THEN
      NULL;
    END;
  END IF;
END $$;

-- ======================================================
-- Users
-- ======================================================
CREATE TABLE IF NOT EXISTS public.users (
  id             serial PRIMARY KEY,
  nombre         text        NOT NULL,
  email          text        NOT NULL UNIQUE,
  hash_pw        text,
  rol            text        NOT NULL,
  activo         boolean     NOT NULL DEFAULT true,
  creado_en      timestamptz NOT NULL DEFAULT now(),
  perm_ingresar  boolean     NOT NULL DEFAULT false,
  CONSTRAINT users_rol_check
    CHECK (rol IN ('tecnico','jefe','jefe_veedor','admin','recepcion','auditor')),
  CONSTRAINT users_perm_ingresar_tecnico_chk
    CHECK (NOT (rol = 'tecnico' AND perm_ingresar = true))
);

-- ======================================================
-- Catálogos
-- ======================================================
CREATE TABLE IF NOT EXISTS public.marcas (
  id          serial PRIMARY KEY,
  nombre      text NOT NULL UNIQUE,
  tecnico_id  int REFERENCES public.users(id)
);
CREATE INDEX IF NOT EXISTS idx_marcas_tecnico ON public.marcas(tecnico_id);

CREATE TABLE IF NOT EXISTS public.models (
  id          serial PRIMARY KEY,
  marca_id    int  NOT NULL REFERENCES public.marcas(id) ON DELETE RESTRICT,
  nombre      text NOT NULL,
  tecnico_id  int  REFERENCES public.users(id),
  UNIQUE(marca_id, nombre)
);
CREATE INDEX IF NOT EXISTS idx_models_marca   ON public.models(marca_id);
CREATE INDEX IF NOT EXISTS idx_models_tecnico ON public.models(tecnico_id);

CREATE TABLE IF NOT EXISTS public.locations (
  id      serial PRIMARY KEY,
  nombre  text NOT NULL UNIQUE
);

INSERT INTO public.locations(nombre) VALUES ('Taller')
ON CONFLICT (nombre) DO NOTHING;

-- ======================================================
-- Customers
-- ======================================================
CREATE TABLE IF NOT EXISTS public.customers (
  id            serial PRIMARY KEY,
  cod_empresa   text,
  razon_social  text NOT NULL,
  cuit          text,
  contacto      text,
  telefono      text,
  email         text
);

-- ======================================================
-- Devices
-- ======================================================
CREATE TABLE IF NOT EXISTS public.devices (
  id               serial PRIMARY KEY,
  customer_id      int  NOT NULL REFERENCES public.customers(id),
  marca_id         int  REFERENCES public.marcas(id),
  model_id         int  REFERENCES public.models(id),
  numero_serie     text,
  garantia_bool    boolean,
  propietario      text,
  etiq_garantia_ok boolean,
  n_de_control     text,
  alquilado        boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_devices_customer  ON public.devices(customer_id);
CREATE INDEX IF NOT EXISTS idx_devices_marca     ON public.devices(marca_id);
CREATE INDEX IF NOT EXISTS idx_devices_model     ON public.devices(model_id);
CREATE INDEX IF NOT EXISTS idx_devices_nro_serie ON public.devices(numero_serie);

-- ======================================================
-- Ingresos  (estado = ticket_state)
-- ======================================================
CREATE TABLE IF NOT EXISTS public.ingresos (
  id                   serial PRIMARY KEY,
  device_id            int            NOT NULL REFERENCES public.devices(id),
  estado               ticket_state   NOT NULL DEFAULT 'ingresado',
  motivo               motivo_ingreso NOT NULL,
  fecha_ingreso        timestamptz    NOT NULL DEFAULT now(),
  fecha_servicio       timestamptz,
  ubicacion_id         int REFERENCES public.locations(id),
  disposicion          disposition    NOT NULL DEFAULT 'normal',
  informe_preliminar   text,
  accesorios           text,
  remito_ingreso       text,
  recibido_por         int REFERENCES public.users(id),
  comentarios          text,
  presupuesto_estado   quote_state    NOT NULL DEFAULT 'pendiente',
  asignado_a           int REFERENCES public.users(id),
  etiqueta_qr          text UNIQUE,

  propietario_nombre   text,
  propietario_contacto text,
  propietario_doc      text,

  descripcion_problema  text,
  trabajos_realizados   text
);
CREATE INDEX IF NOT EXISTS idx_ingresos_device    ON public.ingresos(device_id);
CREATE INDEX IF NOT EXISTS idx_ingresos_estado    ON public.ingresos(estado);
CREATE INDEX IF NOT EXISTS idx_ingresos_asignado  ON public.ingresos(asignado_a);
CREATE INDEX IF NOT EXISTS idx_ingresos_ubicacion ON public.ingresos(ubicacion_id);

-- ======================================================
-- Quotes (cabecera)
-- ======================================================
CREATE TABLE IF NOT EXISTS public.quotes (
  id              serial PRIMARY KEY,
  ingreso_id      int UNIQUE NOT NULL REFERENCES public.ingresos(id) ON DELETE CASCADE,
  estado          quote_state   NOT NULL DEFAULT 'pendiente',
  moneda          text          NOT NULL DEFAULT 'ARS',
  subtotal        numeric(12,2) NOT NULL DEFAULT 0,
  iva_21          numeric(12,2) GENERATED ALWAYS AS (round(subtotal * 0.21, 2)) STORED,
  total           numeric(12,2) GENERATED ALWAYS AS (round(subtotal * 1.21, 2)) STORED,
  autorizado_por  text,
  forma_pago      text,
  fecha_emitido   timestamptz,
  fecha_aprobado  timestamptz,
  pdf_url         text
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='quotes' AND column_name='ticket_id')
     AND EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='quotes' AND column_name='ingreso_id') THEN
    EXECUTE 'UPDATE public.quotes SET ingreso_id = ticket_id WHERE ingreso_id IS NULL AND ticket_id IS NOT NULL';
  END IF;
END$$;

DROP TRIGGER IF EXISTS trg_quote_sync_ins ON public.quotes;
DROP TRIGGER IF EXISTS trg_quote_sync_upd ON public.quotes;
DROP FUNCTION IF EXISTS public.sync_ticket_with_quote();

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='quotes' AND column_name='ticket_id') THEN
    EXECUTE 'ALTER TABLE public.quotes DROP COLUMN ticket_id CASCADE';
  END IF;
END$$;

ALTER TABLE public.quotes
  ALTER COLUMN ingreso_id SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid = 'public.quotes'::regclass AND conname = 'quotes_ingreso_id_fkey'
  ) THEN
    EXECUTE 'ALTER TABLE public.quotes
               ADD CONSTRAINT quotes_ingreso_id_fkey
               FOREIGN KEY (ingreso_id) REFERENCES public.ingresos(id) ON DELETE CASCADE';
  END IF;
END$$;

-- ======================================================
-- Items de Presupuesto
-- ======================================================
CREATE TABLE IF NOT EXISTS public.quote_items (
  id          serial PRIMARY KEY,
  quote_id    int NOT NULL REFERENCES public.quotes(id) ON DELETE CASCADE,
  tipo        text NOT NULL CHECK (tipo IN ('repuesto','mano_obra','servicio')),
  descripcion text NOT NULL,
  qty         numeric(10,2) NOT NULL DEFAULT 1,
  precio_u    numeric(12,2) NOT NULL,
  repuesto_id integer
);
CREATE INDEX IF NOT EXISTS idx_quote_items_quote ON public.quote_items(quote_id);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='repuestos') AND
     NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
                 WHERE table_schema='public' AND table_name='quote_items'
                   AND constraint_name='quote_items_repuesto_id_fkey') THEN
    EXECUTE 'ALTER TABLE public.quote_items
               ADD CONSTRAINT quote_items_repuesto_id_fkey
               FOREIGN KEY (repuesto_id) REFERENCES public.repuestos(id) ON DELETE SET NULL';
  END IF;
END$$;

-- ======================================================
-- Funciones y triggers
-- ======================================================
CREATE OR REPLACE FUNCTION public.recalc_quote_subtotal(p_ingreso_id int)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE v_qid int;
BEGIN
  SELECT id INTO v_qid FROM public.quotes WHERE ingreso_id = p_ingreso_id;
  IF v_qid IS NULL THEN
    INSERT INTO public.quotes(ingreso_id) VALUES (p_ingreso_id)
    ON CONFLICT (ingreso_id) DO NOTHING;
    SELECT id INTO v_qid FROM public.quotes WHERE ingreso_id = p_ingreso_id;
  END IF;

  UPDATE public.quotes q
     SET subtotal = COALESCE((
       SELECT SUM(qi.qty * qi.precio_u)
         FROM public.quote_items qi
        WHERE qi.quote_id = q.id
     ), 0)
   WHERE q.id = v_qid;
END$$;

-- IMPORTANTE: sincroniza estado de presupuesto en Ingresos,
-- mapeando 'emitido' (quote) -> 'presupuestado' (ingreso)
-- Mapea estados de quotes → ingresos (presupuesto_estado y, si corresponde, estado)
CREATE OR REPLACE FUNCTION public.sync_quote_with_ingreso()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  cur_estado ticket_state;
BEGIN
  SELECT estado INTO cur_estado FROM public.ingresos WHERE id = NEW.ingreso_id FOR UPDATE;

  UPDATE public.ingresos
     SET presupuesto_estado = CASE NEW.estado
                                WHEN 'emitido' THEN 'presupuestado'::quote_state
                                WHEN 'presupuestado' THEN 'presupuestado'::quote_state
                                WHEN 'aprobado' THEN 'aprobado'::quote_state
                                WHEN 'rechazado' THEN 'rechazado'::quote_state
                                ELSE 'pendiente'::quote_state
                              END,
         estado = CASE
                    -- aprobado -> pasar a 'reparar' SOLO si venía de ingresado/diagnosticado/presupuestado
                    WHEN NEW.estado = 'aprobado'
                         AND cur_estado IN ('ingresado','diagnosticado','presupuestado')
                    THEN 'reparar'::ticket_state

                    -- rechazado -> NO cambia el estado del equipo (queda como estaba)

                    -- emitido (o presupuestado explícito en quote) → reflejar 'presupuestado'
                    WHEN NEW.estado IN ('emitido','presupuestado') THEN cur_estado

                    ELSE cur_estado
                  END
   WHERE id = NEW.ingreso_id;

  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_quote_sync_ins ON public.quotes;
CREATE TRIGGER trg_quote_sync_ins
  AFTER INSERT ON public.quotes
  FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

DROP TRIGGER IF EXISTS trg_quote_sync_upd ON public.quotes;
CREATE TRIGGER trg_quote_sync_upd
  AFTER UPDATE OF estado, subtotal, fecha_emitido, fecha_aprobado ON public.quotes
  FOR EACH ROW EXECUTE FUNCTION public.sync_quote_with_ingreso();

-- ======================================================
-- RLS
-- ======================================================
ALTER TABLE public.quotes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_quotes_select_all ON public.quotes;
CREATE POLICY p_quotes_select_all ON public.quotes
  FOR SELECT USING (true);

DROP POLICY IF EXISTS p_quotes_ins_admin ON public.quotes;
CREATE POLICY p_quotes_ins_admin ON public.quotes
  FOR INSERT
  WITH CHECK (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

DROP POLICY IF EXISTS p_quotes_upd_admin ON public.quotes;
CREATE POLICY p_quotes_upd_admin ON public.quotes
  FOR UPDATE
  USING     (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'))
  WITH CHECK(current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor'));

ALTER TABLE public.quote_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS p_qi_select_all ON public.quote_items;
CREATE POLICY p_qi_select_all ON public.quote_items
  FOR SELECT USING (true);

DROP POLICY IF EXISTS p_qi_write_roles ON public.quote_items;
CREATE POLICY p_qi_write_roles ON public.quote_items
  FOR ALL
  USING     (current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor','tecnico'))
  WITH CHECK(current_setting('app.user_role', true) IN ('admin','jefe','jefe_veedor','tecnico'));

-- ======================================================
-- Derivación a servicio externo
-- ======================================================
CREATE TABLE IF NOT EXISTS public.proveedores_externos (
  id       serial PRIMARY KEY,
  nombre   text NOT NULL UNIQUE,
  contacto text
);

CREATE TABLE IF NOT EXISTS public.equipos_derivados (
  id            serial PRIMARY KEY,
  ingreso_id    int  NOT NULL REFERENCES public.ingresos(id) ON DELETE CASCADE,
  proveedor_id  int  NOT NULL REFERENCES public.proveedores_externos(id) ON DELETE RESTRICT,
  remit_deriv   text,
  fecha_deriv   date NOT NULL DEFAULT CURRENT_DATE,
  fecha_entrega date,
  estado        external_state NOT NULL DEFAULT 'derivado',
  comentarios   text
);
CREATE INDEX IF NOT EXISTS idx_derivados_ingreso   ON public.equipos_derivados(ingreso_id);
CREATE INDEX IF NOT EXISTS idx_derivados_proveedor ON public.equipos_derivados(proveedor_id);

-- ======================================================
-- Documentos / Handoffs
-- ======================================================
CREATE TABLE IF NOT EXISTS public.handoffs (
  id                     serial PRIMARY KEY,
  ingreso_id             int NOT NULL REFERENCES public.ingresos(id) ON DELETE CASCADE,
  pdf_orden_salida       text,
  firmado_cliente        boolean,
  firmado_empresa        boolean,
  fecha                  timestamptz NOT NULL DEFAULT now(),
  n_factura              text,
  factura_url            text,
  orden_taller           text,
  remito_impreso         boolean,
  fecha_impresion_remito date,
  impresion_remito_url   text
);
CREATE INDEX IF NOT EXISTS idx_handoffs_ingreso ON public.handoffs(ingreso_id);

-- ======================================================
-- Password reset tokens
-- ======================================================
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
  id           bigserial PRIMARY KEY,
  user_id      integer NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  token_hash   text    NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  used_at      timestamptz,
  ip           text,
  user_agent   text
);
CREATE INDEX IF NOT EXISTS idx_prt_user  ON public.password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_prt_token ON public.password_reset_tokens(token_hash);

-- ======================================================
-- Resolución (ex veredicto)
-- ======================================================
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'resolucion_reparacion') THEN
    CREATE TYPE resolucion_reparacion AS ENUM
      ('reparado','no_reparado','no_se_encontro_falla','presupuesto_rechazado');
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ingresos' AND column_name='resolucion'
  ) THEN
    ALTER TABLE public.ingresos
      ADD COLUMN resolucion resolucion_reparacion NULL;
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'veredicto_reparacion') THEN
    ALTER TYPE veredicto_reparacion RENAME TO resolucion_reparacion;
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ingresos' AND column_name='veredicto'
  ) THEN
    ALTER TABLE public.ingresos RENAME COLUMN veredicto TO resolucion;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
                 WHERE t.typname='resolucion_reparacion' AND e.enumlabel='no_reparado') THEN
    ALTER TYPE resolucion_reparacion ADD VALUE IF NOT EXISTS 'no_reparado';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
                 WHERE t.typname='resolucion_reparacion' AND e.enumlabel='no_se_encontro_falla') THEN
    ALTER TYPE resolucion_reparacion ADD VALUE IF NOT EXISTS 'no_se_encontro_falla';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
                 WHERE t.typname='resolucion_reparacion' AND e.enumlabel='presupuesto_rechazado') THEN
    ALTER TYPE resolucion_reparacion ADD VALUE IF NOT EXISTS 'presupuesto_rechazado';
  END IF;
END $$;

-- ======================================================
-- Limpieza de guards viejos y normalización de datos
-- ======================================================

-- Quitar cualquier guard de estado (vos querías poder setear libre)
DROP TRIGGER IF EXISTS trg_ingreso_state_guard   ON public.ingresos;
DROP TRIGGER IF EXISTS trg_ingresos_estado_guard ON public.ingresos;
DROP FUNCTION IF EXISTS public.ingreso_state_guard();

-- Normalizar nombres al esquema actual:
-- 1) presupuesto_estado: 'emitido' -> 'presupuestado'
UPDATE public.ingresos
   SET presupuesto_estado = 'presupuestado'
 WHERE presupuesto_estado::text = 'emitido';

-- 2) estado principal: si quedaron 'emitido' por migraciones, volver a 'presupuestado'
UPDATE public.ingresos
   SET estado = 'presupuestado'
 WHERE estado::text = 'emitido';

 ALTER TABLE models ADD COLUMN IF NOT EXISTS tipo_equipo TEXT;

 -- asignado_a
ALTER TABLE ingresos DROP CONSTRAINT ingresos_asignado_a_fkey;
ALTER TABLE ingresos ADD CONSTRAINT ingresos_asignado_a_fkey
  FOREIGN KEY (asignado_a) REFERENCES users(id) ON DELETE SET NULL;

-- recibido_por (si existe)
ALTER TABLE ingresos DROP CONSTRAINT ingresos_recibido_por_fkey;
ALTER TABLE ingresos ADD CONSTRAINT ingresos_recibido_por_fkey
  FOREIGN KEY (recibido_por) REFERENCES users(id) ON DELETE SET NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_enum e ON e.enumtypid = t.oid
    WHERE t.typname = 'motivo_ingreso'
      AND e.enumlabel = 'urgente control'
  ) THEN
    ALTER TYPE motivo_ingreso ADD VALUE 'urgente control';
  END IF;
END $$;

COMMIT;
