-- mysql/01_schema.sql


SET NAMES utf8mb4;
SET time_zone = '-03:00';


-- Dominio de usuarios (rol)
-- Usamos ENUM para reforzar el dominio que en PG era un CHECK
-- (si se desean roles abiertos, cambiar por VARCHAR y CHECK condicional)

-- =============================================
-- Users
-- =============================================
CREATE TABLE IF NOT EXISTS users (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  nombre           TEXT        NOT NULL,
  email            VARCHAR(320) NOT NULL UNIQUE,
  hash_pw          TEXT,
  rol              ENUM('tecnico','jefe','jefe_veedor','admin','recepcion','auditor') NOT NULL,
  activo           BOOLEAN     NOT NULL DEFAULT TRUE,
  creado_en        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  perm_ingresar    BOOLEAN     NOT NULL DEFAULT FALSE,
  /*!80016 CONSTRAINT users_perm_ingresar_tecnico_chk
     CHECK (NOT (rol = 'tecnico' AND perm_ingresar = TRUE)) */
) ENGINE=InnoDB;

-- =============================================
-- Catálogos
-- =============================================
CREATE TABLE IF NOT EXISTS marcas (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  nombre      TEXT NOT NULL,
  tecnico_id  INT,
  UNIQUE KEY uq_marcas_nombre (nombre(191))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS models (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  marca_id    INT  NOT NULL,
  nombre      TEXT NOT NULL,
  tecnico_id  INT,
  tipo_equipo TEXT NULL,
  UNIQUE KEY uq_models_marca_nombre (marca_id, nombre(191))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS locations (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  nombre  TEXT NOT NULL,
  UNIQUE KEY uq_locations_nombre (nombre(191))
) ENGINE=InnoDB;

-- Seed mínimo (idempotente)
INSERT INTO locations (nombre) VALUES ('Taller')
ON DUPLICATE KEY UPDATE nombre=VALUES(nombre);

-- =============================================
-- Customers
-- =============================================
CREATE TABLE IF NOT EXISTS customers (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  cod_empresa   TEXT,
  razon_social  TEXT NOT NULL,
  cuit          TEXT,
  contacto      TEXT,
  telefono      TEXT,
  email         TEXT
) ENGINE=InnoDB;

-- =============================================
-- Devices
-- =============================================
CREATE TABLE IF NOT EXISTS devices (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  customer_id      INT  NOT NULL,
  marca_id         INT,
  model_id         INT,
  numero_serie     TEXT,
  garantia_bool    BOOLEAN,
  propietario      TEXT,
  etiq_garantia_ok BOOLEAN,
  n_de_control     TEXT,
  alquilado        BOOLEAN NOT NULL DEFAULT FALSE
) ENGINE=InnoDB;

-- =============================================
-- Ingresos (estado = ticket_state)
-- =============================================
CREATE TABLE IF NOT EXISTS ingresos (
  id                   INT AUTO_INCREMENT PRIMARY KEY,
  device_id            INT            NOT NULL,
  estado               ENUM('ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','derivado','liberado','alquilado') NOT NULL DEFAULT 'ingresado',
  motivo               ENUM('reparación','service preventivo','baja alquiler','reparación alquiler','otros','urgente control') NOT NULL,
  fecha_ingreso        TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_servicio       TIMESTAMP NULL,
  ubicacion_id         INT NULL,
  disposicion          ENUM('normal','para_repuesto') NOT NULL DEFAULT 'normal',
  informe_preliminar   TEXT,
  accesorios           TEXT,
  remito_ingreso       TEXT,
  recibido_por         INT NULL,
  comentarios          TEXT,
  presupuesto_estado   ENUM('pendiente','emitido','aprobado','rechazado','presupuestado') NOT NULL DEFAULT 'pendiente',
  asignado_a           INT NULL,
  etiqueta_qr          TEXT NULL,
  propietario_nombre   TEXT,
  propietario_contacto TEXT,
  propietario_doc      TEXT,
  descripcion_problema  TEXT,
  trabajos_realizados   TEXT,
  resolucion           ENUM('reparado','no_reparado','no_se_encontro_falla','presupuesto_rechazado') NULL,
  UNIQUE KEY uq_ingresos_etiqueta_qr (etiqueta_qr(191))
) ENGINE=InnoDB;

-- =============================================
-- Quotes (cabecera)
-- =============================================
CREATE TABLE IF NOT EXISTS quotes (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  ingreso_id      INT  NOT NULL,
  estado          ENUM('pendiente','emitido','aprobado','rechazado','presupuestado') NOT NULL DEFAULT 'pendiente',
  moneda          VARCHAR(10) NOT NULL DEFAULT 'ARS',
  subtotal        DECIMAL(12,2) NOT NULL DEFAULT 0,
  iva_21          DECIMAL(12,2) GENERATED ALWAYS AS (ROUND(subtotal * 0.21, 2)) STORED,
  total           DECIMAL(12,2) GENERATED ALWAYS AS (ROUND(subtotal * 1.21, 2)) STORED,
  autorizado_por  TEXT,
  forma_pago      TEXT,
  fecha_emitido   TIMESTAMP NULL,
  fecha_aprobado  TIMESTAMP NULL,
  pdf_url         TEXT,
  UNIQUE KEY uq_quotes_ingreso (ingreso_id)
) ENGINE=InnoDB;

-- =============================================
-- Items de Presupuesto
-- =============================================
CREATE TABLE IF NOT EXISTS quote_items (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  quote_id    INT NOT NULL,
  tipo        ENUM('repuesto','mano_obra','servicio') NOT NULL,
  descripcion TEXT NOT NULL,
  qty         DECIMAL(10,2) NOT NULL DEFAULT 1,
  precio_u    DECIMAL(12,2) NOT NULL,
  repuesto_id INT NULL
) ENGINE=InnoDB;

-- =============================================
-- ingreso_events (legacy: ticket_id)
-- =============================================
CREATE TABLE IF NOT EXISTS ingreso_events (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  ticket_id   INT NOT NULL,
  ingreso_id  INT AS (ticket_id) VIRTUAL,
  de_estado   ENUM('ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','derivado','liberado','alquilado') NULL,
  a_estado    ENUM('ingresado','diagnosticado','presupuestado','reparar','reparado','entregado','derivado','liberado','alquilado') NOT NULL,
  usuario_id  INT NULL,
  ts          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  comentario  TEXT
) ENGINE=InnoDB;

-- =============================================
-- Derivación a servicio externo
-- =============================================
CREATE TABLE IF NOT EXISTS proveedores_externos (
  id       INT AUTO_INCREMENT PRIMARY KEY,
  nombre   TEXT NOT NULL,
  contacto TEXT,
  UNIQUE KEY uq_prov_ext_nombre (nombre(191))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS equipos_derivados (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  ingreso_id    INT  NOT NULL,
  proveedor_id  INT  NOT NULL,
  remit_deriv   TEXT,
  fecha_deriv   DATE NOT NULL DEFAULT (CURRENT_DATE),
  fecha_entrega DATE,
  estado        ENUM('derivado','en_servicio','devuelto','entregado_cliente') NOT NULL DEFAULT 'derivado',
  comentarios   TEXT
) ENGINE=InnoDB;

-- =============================================
-- Documentos / Handoffs
-- =============================================
CREATE TABLE IF NOT EXISTS handoffs (
  id                     INT AUTO_INCREMENT PRIMARY KEY,
  ingreso_id             INT NOT NULL,
  pdf_orden_salida       TEXT,
  firmado_cliente        BOOLEAN,
  firmado_empresa        BOOLEAN,
  fecha                  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  n_factura              TEXT,
  factura_url            TEXT,
  orden_taller           TEXT,
  remito_impreso         BOOLEAN,
  fecha_impresion_remito DATE,
  impresion_remito_url   TEXT
) ENGINE=InnoDB;

-- =============================================
-- Password reset tokens
-- =============================================
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id      INT      NOT NULL,
  token_hash   TEXT     NOT NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at   TIMESTAMP NOT NULL,
  used_at      TIMESTAMP NULL,
  ip           TEXT,
  user_agent   TEXT
) ENGINE=InnoDB;

-- =============================================
-- HTTP-level activity log (app middleware)
-- =============================================
CREATE TABLE IF NOT EXISTS audit_log (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  ts           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  user_id      INT,
  role         TEXT,
  method       TEXT,
  path         TEXT,
  ip           TEXT,
  user_agent   TEXT,
  status_code  INT,
  body         JSON
) ENGINE=InnoDB;

