# SQL Applies Incrementales

Este directorio es para parches SQL incrementales que deban correrse automaticamente
en bases ya existentes.

Reglas:
- Crear archivos `.sql` nuevos (no editar archivos ya aplicados).
- Orden de ejecucion: por nombre de archivo (alfabetico).
- El backend registra `script_name + sha256` en `retail_db_applies`.
- Si un archivo ya aplicado cambia de contenido, el sistema falla para evitar drift silencioso.

Ejecucion automatica:
- `docker-compose.yml` y `docker-compose.prod.yml` ejecutan `python manage.py apply_sql_patches`.
- `deploy/retailhub_update_manager.ps1` tambien lo ejecuta en actualizaciones sin Docker.
- Script manual: `python apply.py` (docker) o `python apply.py --local`.

Variables opcionales:
- `DB_APPLY_SCRIPTS_DIR`: cambia el directorio de parches.
- `DB_APPLY_SCRIPTS_ENABLED=0`: desactiva temporalmente el auto-apply.
