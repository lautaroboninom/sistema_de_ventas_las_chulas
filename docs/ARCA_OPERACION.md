# Operacion ARCA en RetailHub

## Flujo operativo (resumen)

- La emision de factura y nota de credito usa WSAA + WSFEv1 nativo desde el backend.
- Si hay timeout/error de red en `FECAESolicitar`, se intenta recuperacion con `FECompConsultar`.
- Si no hay recuperacion, el comprobante queda en `retry` y se encola `integration_jobs`.
- Si falta documento del cliente para emitir, el comprobante queda en `manual_review`.

## Comando de reintentos ARCA

Ejecutar processor de jobs ARCA:

```bash
python manage.py process_arca_jobs --limit 20 --max-attempts 8
```

- `--limit`: cantidad maxima de jobs a procesar por corrida.
- `--max-attempts`: intentos antes de mover a `dead_letter`.

## Recomendacion de scheduling

- Correr cada 1-5 minutos en entorno productivo.
- Monitorear jobs en `integration_jobs` con estado `failed` o `dead_letter`.
- Ante `manual_review`, resolver el dato fiscal faltante y reintentar desde UI.
