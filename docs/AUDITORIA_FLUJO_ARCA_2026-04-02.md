# Auditoria flujo ARCA en RetailHub (actualizado 2026-04-02)

## Estado actual

- Implementado WSAA nativo (`LoginCms`) con firma CMS y cache de TA.
- Implementado WSFEv1 nativo para:
  - `FECompUltimoAutorizado`
  - `FECAESolicitar`
  - `FECompConsultar`
- Implementado flujo real de factura y nota de credito (sin middleware HTTP externo).
- Implementado recovery por timeout/error indeterminado usando `FECompConsultar` antes de decidir retry.
- Implementado lock de secuencia por `pto_vta + cbte_tipo` con advisory lock transaccional.
- Implementado processor de jobs ARCA (`invoice_issue`, `credit_note_issue`) con backoff y dead-letter.

## Politicas operativas aplicadas

- Si falta documento fiscal del cliente:
  - Emision manual: bloqueo con validacion.
  - Autoemision (POS/online): pasa a `manual_review` sin frenar la venta.
- Si ARCA falla por timeout/conexion:
  - Se consulta comprobante emitido y, si no aparece autorizado, queda en `retry`.
- Si ARCA rechaza funcionalmente:
  - Estado `rejected` (requiere accion operativa).

## Datos persistidos por comprobante

- `cbte_tipo`, `cbte_nro`, `pto_vta`
- `cae`, `cae_due_date`
- `error_code`, `error_message`
- `request_payload`, `response_payload`
- `attempts`, `last_attempt_at`

## Configuracion agregada

- Endpoints WSAA/WSFE por ambiente.
- Timeout de llamada ARCA.
- Margen de seguridad para cache de TA.
- Tipo de comprobante por canal:
  - `arca_cbte_tipo_store`
  - `arca_cbte_tipo_online`

## Operacion recomendada

- Programar `python manage.py process_arca_jobs --limit 20 --max-attempts 8` cada 1-5 minutos.
- Monitorear `integration_jobs` en estados `failed`/`dead_letter`.
- Resolver casos `manual_review` desde operacion antes de reintentar.

## Referencias oficiales

- Arquitectura WS SOAP ARCA:
  - https://www.afip.gob.ar/ws/documentacion/arquitectura-general.asp
- WSAA:
  - https://www.afip.gob.ar/ws/documentacion/wsaa.asp
  - https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.2.pdf
- WSFEv1:
  - https://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp
  - https://www.afip.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG-v4-1.pdf
