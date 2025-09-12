# Staging (MySQL) – Verificación y Smokes

Prerequisitos:
- Docker en ejecución y servicios de `docker-compose.mysql.staging.yml` levantados.
- Contenedor `mysql` saludable y `api-staging` corriendo.

## Verificación de esquema y FKs
1) Copiar el verificador al contenedor (si no existe):
   `docker compose -f docker-compose.mysql.staging.yml cp mysql/99_verify_mysql.sql mysql:/tmp/mysql/99_verify_mysql.sql`
2) Ejecutar verificador:
   `make staging-verify`

Salida esperada: versión/modos y conteos por tabla; luego checks de orfandad (0 es OK, cualquier no-cero a revisar).

## Smokes de BD (mínimos)
- Ejecutar los smokes manuales con el bloque SQL usado en la automatización (ingreso mínimo, quote+item, cambio a diagnosticado). Se recomienda correr dentro de una transacción con `ROLLBACK` al final para no dejar residuos.
- Atajo de placeholder: `make staging-smokes` (sólo valida conexión; ver scripts SQL en el repo o en los prompts de trabajo para el bloque completo).

## Health de servicios
- `make staging-health` muestra estado de contenedores y consulta `/api/health/` del contenedor API (si está disponible).

Notas:
- El proyecto mantiene compatibilidad dual Postgres/MySQL. Las vistas/queries evitan sintaxis específicas; el middleware adapta JSON.
- En MySQL, algunas claves foráneas son lógicas (sin FK física); el verificador revisa orfandades por LEFT JOIN.
