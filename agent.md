# Reglas Operativas del Agente

- En la computadora de la clienta, el entorno de produccion local corre **sin Docker**. No asumir Docker para diagnosticar actualizaciones, reinicios, backend, frontend ni despliegues en cliente. Para prod cliente, razonar sobre procesos/servicios locales, entorno Python/Node local y scripts PowerShell de actualizacion.
- A partir de ahora, los cambios incrementales de DB deben implementarse con `SQL applies` versionados en `api/sql/applies/*.sql` (archivo nuevo por cambio, nunca editar uno ya aplicado).
- El sistema debe auto-aplicar esos scripts al iniciar/actualizar mediante `python manage.py apply_sql_patches`, con registro en `retail_db_applies` (script_name + sha256 + applied_at).
- `deploy/retailhub_update_manager.ps1` en modo `apply-on-start` debe intentar `migrate + apply_sql_patches` incluso sin `git pending`, para recuperar applies no ejecutados en instalaciones cliente.
- Si un script ya aplicado cambia de contenido, debe fallar por mismatch de hash para evitar drift silencioso.
- Todo cambio de DB debe seguir reflejandose en `sql/schema.sql` cuando corresponda para instalaciones nuevas.
- En cada entrega con cambios de DB, verificar y reportar explicitamente:
  - que `migrate` corre sin errores,
  - que `apply_sql_patches` corre y aplica/omite correctamente,
  - y que la app levanta y responde (`/api/health/`).
- En cada actualizacion visible para la clienta, crear o actualizar el aviso de novedades de la app:
  - usar un identificador nuevo de aviso para que se muestre una sola vez al primer inicio despues de actualizar,
  - escribir el mensaje junto con el cambio implementado, no dejarlo para despues,
  - redactar los cambios en lenguaje claro para la clienta, sin endpoints, nombres de funciones ni detalles tecnicos,
  - explicar que cambio, donde lo va a ver y como impacta su trabajo diario,
  - mantener el modal simple y facil de cerrar.
