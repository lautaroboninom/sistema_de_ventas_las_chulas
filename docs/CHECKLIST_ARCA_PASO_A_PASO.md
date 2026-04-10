# Checklist ARCA (alta y puesta en marcha para facturacion)

## Objetivo
Esta guia sirve para que el equipo del cliente junte los datos fiscales y tecnicos que RetailHub necesita para empezar a facturar con ARCA, sin exponer credenciales sensibles al equipo funcional.

## 1) Datos que deben tener antes de cargar RH

- CUIT emisor.
- Condicion IVA vigente.
- Punto de venta para local y punto de venta para online.
- Certificado digital y clave privada para el ambiente que se va a usar (homologacion o produccion).
- Confirmacion de que el certificado esta asociado al servicio de negocio WSFE.

## 2) Alta en homologacion (testing)

1. Ingresar con clave fiscal a WSASS.
2. Generar CSR.
3. Emitir certificado digital de homologacion.
4. Crear autorizacion de acceso al WSN de factura electronica.
5. Asociar certificado + alias para el WSN.
6. Descargar/guardar certificado y clave en una ruta segura de la PC/servidor.

## 3) Cargar datos en RetailHub (Config > Config general > Facturacion ARCA)

- `arca_env`: `homologacion` o `produccion`.
- `arca_cuit`: CUIT emisor.
- `arca_pto_vta_store`: punto de venta para mostrador/local.
- `arca_pto_vta_online`: punto de venta para ecommerce.
- `arca_cert_path`: ruta del certificado.
- `arca_key_path`: ruta de la clave privada.
- `auto_invoice_online_paid`: definir si la emision online se ejecuta automaticamente al cobrar.

## 4) Prueba funcional en homologacion

1. Confirmar una venta con `Factura requerida = Si`.
2. En `Ventas`, abrir el detalle y ejecutar `Emitir / reintentar factura`.
3. Verificar que el estado pase a `authorized`.
4. Verificar `CAE` y `Cbte nro` en el detalle.
5. Si falla, revisar `status`, `error_message` y reintentar despues de corregir configuracion.

## 5) Pase a produccion

1. Generar certificado de produccion (Administrador de Certificados Digitales).
2. Asociar certificado al WSN WSFE (Administrador de Relaciones de Clave Fiscal).
3. Delegar WSN si factura un tercero/proveedor tecnico.
4. Dar de alta el punto de venta fiscal en ARCA.
5. Cambiar `arca_env` a `produccion`.
6. Cargar rutas de certificado/clave productivas.
7. Ejecutar una venta real controlada y validar CAE.

## 6) Validaciones recomendadas de salida

- Emision local y online autorizan con CAE.
- Reintento manual funciona cuando hubo error temporal.
- Se conserva correlatividad por punto de venta/tipo de comprobante.
- Operacion conoce el procedimiento ante `retry` o `manual_review`.

## 7) Enlaces oficiales ARCA/AFIP (tutoriales y especificaciones)

- Acciones para consumir WS de Factura Electronica:
  - https://www.afip.gob.ar/fe/documentos/AccionesarealizarparaconsumirunWebservicedeFacturaElectr.pdf
- Documentacion WS Factura Electronica (manuales, wsfev1):
  - https://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp
- Manual WSFEv1 (RG 4291, version vigente publicada por ARCA):
  - https://www.afip.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG-v4-1.pdf
- Documentacion WSAA:
  - https://www.afip.gob.ar/ws/documentacion/wsaa.asp
- Especificacion tecnica WSAA 1.2.2:
  - https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.2.pdf
- Manual WSASS (homologacion):
  - https://www.afip.gob.ar/ws/WSASS/html/index.html
- Asociar certificado digital a WSN en produccion:
  - https://www.afip.gob.ar/ws/WSAA/wsaa_asociar_certificado_a_wsn_produccion.pdf
- Delegar WSN (Administrador de Relaciones):
  - https://www.afip.gob.ar/ws/WSAA/ADMINREL.DelegarWS.pdf

## 8) Nota operativa importante

La facturacion real depende de credenciales sensibles (certificado/clave, relaciones de clave fiscal y puntos de venta habilitados). Por seguridad, estas pruebas deben ejecutarlas las titulares o el responsable tecnico fiscal del cliente.
