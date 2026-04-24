# Reglas Operativas del Agente

- A partir de ahora, los cambios incrementales de DB deben implementarse con `SQL applies` versionados en `api/sql/applies/*.sql` (archivo nuevo por cambio, nunca editar uno ya aplicado).
- El sistema debe auto-aplicar esos scripts al iniciar/actualizar mediante `python manage.py apply_sql_patches`, con registro en `retail_db_applies` (script_name + sha256 + applied_at).
- `deploy/retailhub_update_manager.ps1` en modo `apply-on-start` debe intentar `migrate + apply_sql_patches` incluso sin `git pending`, para recuperar applies no ejecutados en instalaciones cliente.
- Si un script ya aplicado cambia de contenido, debe fallar por mismatch de hash para evitar drift silencioso.
- Todo cambio de DB debe seguir reflejandose en `sql/schema.sql` cuando corresponda para instalaciones nuevas.
- En cada entrega con cambios de DB, verificar y reportar explicitamente:
  - que `migrate` corre sin errores,
  - que `apply_sql_patches` corre y aplica/omite correctamente,
  - y que la app levanta y responde (`/api/health/`).
