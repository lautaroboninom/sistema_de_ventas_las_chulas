# Pendientes - Reimplementación Retail Las Chulas

## Preguntas de negocio pendientes
- Política exacta de devoluciones/cambios (plazos, reintegro, nota de crédito).
- Definición final de comprobante para consumidor final vs cliente identificado.
- Confirmación de cuentas de transferencia operativas y regla de conciliación diaria.
- Definición de formato final de ticket interno no fiscal en efectivo.
- Definición de hardware de impresión (térmica/tickets y etiquetas) y layout de barcode.

## Dependencias externas
- Alta y habilitación de ARCA WSAA/WSFEv1 (homologación y producción).
- Credenciales productivas de Tienda Nube y configuración de webhooks.
- Servidor público con HTTPS estable para recepción de webhooks Tienda Nube.
- Certificados ARCA (CRT/KEY) custodiados por responsable técnico.
- Implementación final SOAP WSAA/WSFEv1 (firma CMS + TA cache + FECompUltimoAutorizado/FECAESolicitar) para pasar de fallback a emisión fiscal real.

## Datos fiscales/ARCA faltantes
- CUIT emisor definitivo.
- Razón social fiscal exacta.
- Condición IVA vigente.
- Punto de venta por canal (mostrador y online).
- Parametrización final de tipo de comprobante (`tipo_cbte`) y secuencia por punto de venta.
- Responsable operativo de homologación ARCA y proceso de pase a producción.

## Datos Tienda Nube faltantes
- `client_id` y `client_secret`.
- `store_id`.
- `access_token` con scopes de productos, variantes, stock, órdenes y webhooks.
- Secret de firma webhook (`x-linkedstore-hmac-sha256`).
- Confirmación de mapeo SKU definitivo por variante (sin duplicados históricos).

## Decisiones asumidas por defecto
- Moneda MVP: ARS.
- USD solo habilitado en ingreso de compra para trazabilidad de costo.
- Stock único sin separación depósito/local.
- Catálogo local como fuente de verdad para variantes y stock.
- Facturación automática solo para tarjeta/transferencia; efectivo con comprobante interno.
- Webhooks duplicados se descartan por idempotencia (`event_id`/`order_id`).
- Emisión ARCA en MVP funcionando en modo mock si no hay certificados/credenciales configuradas.

## Riesgos y mitigaciones
- Riesgo: falta de datos fiscales impide salida a producción ARCA.
  Mitigación: validar checklist ARCA completo en homologación antes de go-live.
- Riesgo: SKU inconsistentes entre local y Tienda Nube generan descuadres de stock.
  Mitigación: control de unicidad SKU y corrida de conciliación previa a activar webhooks.
- Riesgo: caídas de integraciones externas afectan facturación/sync.
  Mitigación: tabla `integration_jobs` con reintentos, estado fallido y reproceso manual.
- Riesgo: operación simultánea en POS puede forzar sobreventa.
  Mitigación: confirmación transaccional con lock por variante y validación de stock antes de descontar.
- Riesgo: empleados accediendo a costos/rentabilidad.
  Mitigación: permisos `action.reportes.ver_costos` solo para rol `admin`.

## Checklist de salida a producción
- [ ] Crear base nueva ejecutando `sql/schema.sql` completo (sin comandos `apply_*`).
- [ ] Confirmar que todas las tablas retail existen y tienen índices/triggers.
- [ ] Cargar medios de pago y validar cuentas reales (`cash`, `bbva`, `pbs`, `payway`, `transfer_1`, `transfer_2`).
- [ ] Configurar variables de entorno ARCA y validar emisión homologación end-to-end.
- [ ] Configurar variables de Tienda Nube y probar `sync/catalog`, `sync/stock` y webhooks.
- [ ] Validar permisos por rol (`admin`, `empleado`) y ocultamiento de costos.
- [ ] Ejecutar pruebas de concurrencia POS con misma variante (sin stock negativo).
- [ ] Validar flujo de anulación de venta y estado fiscal (`manual_review` cuando aplique).
- [ ] Definir procedimiento operativo ante error ARCA (cola retry/manual).
- [ ] Hacer backup de base y plan de rollback previo a corte productivo.
