-- 02_tables.sql
-- Tables definitions (PK/UK only, no FKs yet). All timestamps use timestamptz.

BEGIN;

-- Keep audit schema grouped
CREATE SCHEMA IF NOT EXISTS audit;

-- users
CREATE TABLE IF NOT EXISTS public.users (
  id             serial PRIMARY KEY,
  nombre         text        NOT NULL,
  email          text        NOT NULL UNIQUE,
  hash_pw        text,
  rol            text        NOT NULL,
  activo         boolean     NOT NULL DEFAULT true,
  creado_en      timestamptz NOT NULL DEFAULT now(),
  perm_ingresar  boolean     NOT NULL DEFAULT false,
  CONSTRAINT users_rol_check CHECK (rol IN ('tecnico','jefe','jefe_veedor','admin','recepcion','auditor')),
  CONSTRAINT users_perm_ingresar_tecnico_chk CHECK (NOT (rol = 'tecnico' AND perm_ingresar = true))
);

-- catálogos (marcas/models/locations)
CREATE TABLE IF NOT EXISTS public.marcas (
  id          serial PRIMARY KEY,
  nombre      text NOT NULL UNIQUE,
  tecnico_id  int
);

CREATE TABLE IF NOT EXISTS public.models (
  id          serial PRIMARY KEY,
  marca_id    int  NOT NULL,
  nombre      text NOT NULL,
  tecnico_id  int,
  tipo_equipo text,
  UNIQUE(marca_id, nombre)
);

CREATE TABLE IF NOT EXISTS public.locations (
  id      serial PRIMARY KEY,
  nombre  text NOT NULL UNIQUE
);

-- customers
CREATE TABLE IF NOT EXISTS public.customers (
  id            serial PRIMARY KEY,
  cod_empresa   text,
  razon_social  text NOT NULL,
  cuit          text,
  contacto      text,
  telefono      text,
  email         text
);

-- devices
CREATE TABLE IF NOT EXISTS public.devices (
  id               serial PRIMARY KEY,
  customer_id      int  NOT NULL,
  marca_id         int,
  model_id         int,
  numero_serie     text,
  garantia_bool    boolean,
  propietario      text,
  etiq_garantia_ok boolean,
  n_de_control     text,
  alquilado        boolean NOT NULL DEFAULT false
);

-- ingresos
CREATE TABLE IF NOT EXISTS public.ingresos (
  id                   serial PRIMARY KEY,
  device_id            int            NOT NULL,
  estado               ticket_state   NOT NULL DEFAULT 'ingresado',
  motivo               motivo_ingreso NOT NULL,
  fecha_ingreso        timestamptz    NOT NULL DEFAULT now(),
  fecha_servicio       timestamptz,
  ubicacion_id         int,
  disposicion          disposition    NOT NULL DEFAULT 'normal',
  informe_preliminar   text,
  accesorios           text,
  remito_ingreso       text,
  recibido_por         int,
  comentarios          text,
  presupuesto_estado   quote_state    NOT NULL DEFAULT 'pendiente',
  asignado_a           int,
  etiqueta_qr          text UNIQUE,
  propietario_nombre   text,
  propietario_contacto text,
  propietario_doc      text,
  descripcion_problema text,
  trabajos_realizados  text,
  -- v2025-09-05
  garantia_reparacion  boolean NOT NULL DEFAULT false,
  faja_garantia        text,
  remito_salida        text,
  factura_numero       text,
  fecha_entrega        timestamptz,
  alquilado            boolean NOT NULL DEFAULT false,
  alquiler_a           text,
  alquiler_remito      text,
  alquiler_fecha       date,
  resolucion           resolucion_reparacion NULL
);

-- quotes (cabecera). ingreso_id is unique by design
CREATE TABLE IF NOT EXISTS public.quotes (
  id              serial PRIMARY KEY,
  ingreso_id      int UNIQUE,
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

-- quote items
CREATE TABLE IF NOT EXISTS public.quote_items (
  id          serial PRIMARY KEY,
  quote_id    int NOT NULL,
  tipo        text NOT NULL CHECK (tipo IN ('repuesto','mano_obra','servicio')),
  descripcion text NOT NULL,
  qty         numeric(10,2) NOT NULL DEFAULT 1,
  precio_u    numeric(12,2) NOT NULL,
  repuesto_id integer
);

-- proveedores externos y derivaciones
CREATE TABLE IF NOT EXISTS public.proveedores_externos (
  id       serial PRIMARY KEY,
  nombre   text NOT NULL UNIQUE,
  contacto text
);

CREATE TABLE IF NOT EXISTS public.equipos_derivados (
  id            serial PRIMARY KEY,
  ingreso_id    int  NOT NULL,
  proveedor_id  int  NOT NULL,
  remit_deriv   text,
  fecha_deriv   date NOT NULL DEFAULT CURRENT_DATE,
  fecha_entrega date,
  estado        external_state NOT NULL DEFAULT 'derivado',
  comentarios   text
);

-- handoffs (documentos/impresiones)
CREATE TABLE IF NOT EXISTS public.handoffs (
  id                     serial PRIMARY KEY,
  ingreso_id             int NOT NULL,
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

-- password reset tokens
CREATE TABLE IF NOT EXISTS public.password_reset_tokens (
  id           bigserial PRIMARY KEY,
  user_id      integer NOT NULL,
  token_hash   text    NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  used_at      timestamptz,
  ip           text,
  user_agent   text
);

-- accesorios catálogo y asignación por ingreso
CREATE TABLE IF NOT EXISTS public.catalogo_accesorios (
  id      serial PRIMARY KEY,
  nombre  text NOT NULL UNIQUE,
  activo  boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.ingreso_accesorios (
  id            serial PRIMARY KEY,
  ingreso_id    int NOT NULL,
  accesorio_id  int NOT NULL,
  referencia    text,
  descripcion   text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ingreso_events (event log)
CREATE TABLE IF NOT EXISTS public.ingreso_events (
  id         serial PRIMARY KEY,
  ingreso_id int NOT NULL,
  de_estado  ticket_state NULL,
  a_estado   ticket_state NOT NULL,
  usuario_id int NULL,
  ts         timestamptz NOT NULL DEFAULT now(),
  comentario text
);

-- audit.change_log and HTTP audit_log (append-only by triggers)
CREATE TABLE IF NOT EXISTS audit.change_log (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  user_id      text,
  user_role    text,
  ingreso_id   int,
  table_name   text NOT NULL,
  record_id    int  NOT NULL,
  column_name  text NOT NULL,
  old_value    text,
  new_value    text
);

CREATE TABLE IF NOT EXISTS public.audit_log (
  id           bigserial PRIMARY KEY,
  ts           timestamptz NOT NULL DEFAULT now(),
  user_id      int,
  role         text,
  method       text,
  path         text,
  ip           text,
  user_agent   text,
  status_code  int,
  body         jsonb
);

COMMIT;

