# ETL: utilitarios y validaciones

Pasos típicos para actualizar catálogos, normalizar y validar la migración desde Access.

## 1) Exportar desde Access

En PowerShell:

```
pwsh etl/export_access.ps1 -DbPath "C:\ruta\Tablas2025 MG-SEPID 2.0.accdb" -OutDir etl/out
```

Genera, entre otros:
- `etl/out/reg_serv_costos_access.csv`
- `etl/out/presupuestos_access.csv`
- `etl/out/models_access.csv`
- `etl/out/devices_access.csv`

## 2) Normalizar modelos y tipos de equipo

Aplica mapeos de marca/modelo y heurísticas de `tipo_equipo` (incluye bombas de infusión ABBOTT/ALARIS/ARGUS/SAMTRONIC):

```
mysql --local-infile=1 -u sepid -p servicio_tecnico < etl/sql/models_devices_normalize.sql
```

Nota: el script carga CSV desde `/tmp/etl/*.csv`. Si estás en Windows, copiá `etl/out/*.csv` a `/tmp/etl/` (WSL) o ajustá rutas en el SQL.

## 3) Informe de validación mensual por cliente

Compara Access (RegistrosdeServicio.CostoTotal) vs MySQL (`quotes.subtotal`/`quotes.total`). Ejecutá:

```
mysql --local-infile=1 -u sepid -p servicio_tecnico < etl/sql/validation_costos_vs_quotes.sql
```

Salida:
- Primer SELECT: por `mes` y `cliente` muestra sumas de `CostoTotal` (Access), `subtotal` y `total` (MySQL) y la diferencia de `subtotal` vs `CostoTotal`.
- Segundo SELECT: lista ingresos con diferencia > $0,01 para revisión puntual.

