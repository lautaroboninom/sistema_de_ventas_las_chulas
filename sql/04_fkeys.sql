-- 04_fkeys.sql
-- Foreign keys only. Idempotent via catalog checks.

BEGIN;

-- Helper: add FK if not exists
DO $$ BEGIN
  -- marcas.tecnico_id -> users.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'marcas_tecnico_id_fkey' AND conrelid = 'public.marcas'::regclass
  ) THEN
    ALTER TABLE public.marcas
      ADD CONSTRAINT marcas_tecnico_id_fkey FOREIGN KEY (tecnico_id) REFERENCES public.users(id);
  END IF;

  -- models.marca_id -> marcas.id (RESTRICT)
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'models_marca_id_fkey' AND conrelid = 'public.models'::regclass
  ) THEN
    ALTER TABLE public.models
      ADD CONSTRAINT models_marca_id_fkey FOREIGN KEY (marca_id) REFERENCES public.marcas(id) ON DELETE RESTRICT;
  END IF;

  -- models.tecnico_id -> users.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'models_tecnico_id_fkey' AND conrelid = 'public.models'::regclass
  ) THEN
    ALTER TABLE public.models
      ADD CONSTRAINT models_tecnico_id_fkey FOREIGN KEY (tecnico_id) REFERENCES public.users(id);
  END IF;

  -- devices.customer_id -> customers.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'devices_customer_id_fkey' AND conrelid = 'public.devices'::regclass
  ) THEN
    ALTER TABLE public.devices
      ADD CONSTRAINT devices_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);
  END IF;

  -- devices.marca_id -> marcas.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'devices_marca_id_fkey' AND conrelid = 'public.devices'::regclass
  ) THEN
    ALTER TABLE public.devices
      ADD CONSTRAINT devices_marca_id_fkey FOREIGN KEY (marca_id) REFERENCES public.marcas(id);
  END IF;

  -- devices.model_id -> models.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'devices_model_id_fkey' AND conrelid = 'public.devices'::regclass
  ) THEN
    ALTER TABLE public.devices
      ADD CONSTRAINT devices_model_id_fkey FOREIGN KEY (model_id) REFERENCES public.models(id);
  END IF;

  -- ingresos.device_id -> devices.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingresos_device_id_fkey' AND conrelid = 'public.ingresos'::regclass
  ) THEN
    ALTER TABLE public.ingresos
      ADD CONSTRAINT ingresos_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id);
  END IF;

  -- ingresos.ubicacion_id -> locations.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingresos_ubicacion_id_fkey' AND conrelid = 'public.ingresos'::regclass
  ) THEN
    ALTER TABLE public.ingresos
      ADD CONSTRAINT ingresos_ubicacion_id_fkey FOREIGN KEY (ubicacion_id) REFERENCES public.locations(id);
  END IF;

  -- ingresos.recibido_por -> users.id ON DELETE SET NULL
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingresos_recibido_por_fkey' AND conrelid = 'public.ingresos'::regclass
  ) THEN
    ALTER TABLE public.ingresos
      ADD CONSTRAINT ingresos_recibido_por_fkey FOREIGN KEY (recibido_por) REFERENCES public.users(id) ON DELETE SET NULL;
  END IF;

  -- ingresos.asignado_a -> users.id ON DELETE SET NULL
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingresos_asignado_a_fkey' AND conrelid = 'public.ingresos'::regclass
  ) THEN
    ALTER TABLE public.ingresos
      ADD CONSTRAINT ingresos_asignado_a_fkey FOREIGN KEY (asignado_a) REFERENCES public.users(id) ON DELETE SET NULL;
  END IF;

  -- quotes.ingreso_id -> ingresos.id ON DELETE CASCADE
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'quotes_ingreso_id_fkey' AND conrelid = 'public.quotes'::regclass
  ) THEN
    ALTER TABLE public.quotes
      ADD CONSTRAINT quotes_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES public.ingresos(id) ON DELETE CASCADE;
  END IF;

  -- quote_items.quote_id -> quotes.id ON DELETE CASCADE
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_quote_id_fkey' AND conrelid = 'public.quote_items'::regclass
  ) THEN
    ALTER TABLE public.quote_items
      ADD CONSTRAINT quote_items_quote_id_fkey FOREIGN KEY (quote_id) REFERENCES public.quotes(id) ON DELETE CASCADE;
  END IF;

  -- quote_items.repuesto_id -> repuestos.id (if repuestos exists)
  IF EXISTS (
    SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='repuestos'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_repuesto_id_fkey' AND conrelid = 'public.quote_items'::regclass
  ) THEN
    ALTER TABLE public.quote_items
      ADD CONSTRAINT quote_items_repuesto_id_fkey FOREIGN KEY (repuesto_id) REFERENCES public.repuestos(id) ON DELETE SET NULL;
  END IF;

  -- equipos_derivados.ingreso_id -> ingresos.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'equipos_derivados_ingreso_id_fkey' AND conrelid = 'public.equipos_derivados'::regclass
  ) THEN
    ALTER TABLE public.equipos_derivados
      ADD CONSTRAINT equipos_derivados_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES public.ingresos(id) ON DELETE CASCADE;
  END IF;

  -- equipos_derivados.proveedor_id -> proveedores_externos.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'equipos_derivados_proveedor_id_fkey' AND conrelid = 'public.equipos_derivados'::regclass
  ) THEN
    ALTER TABLE public.equipos_derivados
      ADD CONSTRAINT equipos_derivados_proveedor_id_fkey FOREIGN KEY (proveedor_id) REFERENCES public.proveedores_externos(id) ON DELETE RESTRICT;
  END IF;

  -- handoffs.ingreso_id -> ingresos.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'handoffs_ingreso_id_fkey' AND conrelid = 'public.handoffs'::regclass
  ) THEN
    ALTER TABLE public.handoffs
      ADD CONSTRAINT handoffs_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES public.ingresos(id) ON DELETE CASCADE;
  END IF;

  -- ingreso_accesorios.ingreso_id -> ingresos.id, accesorio_id -> catalogo_accesorios
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingreso_accesorios_ingreso_id_fkey' AND conrelid = 'public.ingreso_accesorios'::regclass
  ) THEN
    ALTER TABLE public.ingreso_accesorios
      ADD CONSTRAINT ingreso_accesorios_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES public.ingresos(id) ON DELETE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingreso_accesorios_accesorio_id_fkey' AND conrelid = 'public.ingreso_accesorios'::regclass
  ) THEN
    ALTER TABLE public.ingreso_accesorios
      ADD CONSTRAINT ingreso_accesorios_accesorio_id_fkey FOREIGN KEY (accesorio_id) REFERENCES public.catalogo_accesorios(id);
  END IF;

  -- ingreso_events.ingreso_id -> ingresos.id; usuario_id -> users.id
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingreso_events_ingreso_id_fkey' AND conrelid = 'public.ingreso_events'::regclass
  ) THEN
    ALTER TABLE public.ingreso_events
      ADD CONSTRAINT ingreso_events_ingreso_id_fkey FOREIGN KEY (ingreso_id) REFERENCES public.ingresos(id) ON DELETE CASCADE;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ingreso_events_usuario_id_fkey' AND conrelid = 'public.ingreso_events'::regclass
  ) THEN
    ALTER TABLE public.ingreso_events
      ADD CONSTRAINT ingreso_events_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.users(id);
  END IF;

  -- audit_log.user_id -> users.id (optional FK)
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'audit_log_user_id_fkey' AND conrelid = 'public.audit_log'::regclass
  ) THEN
    ALTER TABLE public.audit_log
      ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;
  END IF;

END $$;

COMMIT;

