# Apply DB - Probe minimo (2026-04)

## Alcance del cambio
Este apply agrega un cambio minimo de schema para validar el flujo de actualizacion en servidor:
- columna `retail_settings.db_apply_probe_marker`
- migracion Django `service.0013_db_apply_probe_marker`

## Despues del pull en servidor
Ejecutar desde la raiz del repo:

```powershell
python apply.py
```

El script:
1. Corre `migrate service 0013_db_apply_probe_marker`
2. Corre `migrate --noinput`
3. Verifica columna y valor de marker en `retail_settings`

## Resultado esperado
Salida con:
- `column_ok=True`
- `marker=v2026_04_probe`
- `OK: apply DB completado.`

