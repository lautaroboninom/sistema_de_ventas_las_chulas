# Rotacion de secretos (operativo)

## Que significa "rotar secretos"
Rotar secretos significa reemplazar credenciales activas por credenciales nuevas (claves, tokens, passwords) y retirar las anteriores.

Se hace para reducir riesgo si hubo filtracion y para limitar ventana de uso de credenciales viejas.

## Alcance en este proyecto
Secretos internos (rotacion automatica):
- `DJANGO_SECRET_KEY`
- `JWT_SECRET`
- `POSTGRES_PASSWORD`

Secretos externos (rotacion manual):
- `TIENDANUBE_ACCESS_TOKEN`
- `TIENDANUBE_WEBHOOK_SECRET` / `tiendanube_client_secret`
- Credenciales y certificados ARCA

## Script Linux/macOS
```bash
bash deploy/rotate_secrets.sh .env.prod
```

## Script Windows PowerShell
```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\rotate_secrets.ps1 -EnvFile .env.prod
```

El script genera un archivo nuevo:
- `.env.prod.rotated.YYYYMMDD_HHMMSS`

No pisa `.env.prod` automaticamente.

## Flujo recomendado de rotacion
1. Generar archivo rotado con script.
2. Revisar que solo cambiaron claves esperadas.
3. Si la base YA existe, cambiar primero la password del rol en PostgreSQL con el NUEVO `POSTGRES_PASSWORD` del archivo rotado:
```bash
docker exec -it retailhub-postgres psql -U <POSTGRES_USER> -d <POSTGRES_DB> -c "ALTER ROLE <POSTGRES_USER> WITH PASSWORD '<NUEVO_POSTGRES_PASSWORD>';"
```
Si PostgreSQL corre fuera de Docker:
```bash
psql -h <POSTGRES_HOST> -p <POSTGRES_PORT> -U <POSTGRES_USER> -d <POSTGRES_DB> -c "ALTER ROLE <POSTGRES_USER> WITH PASSWORD '<NUEVO_POSTGRES_PASSWORD>';"
```
4. Reemplazar `.env.prod` por el archivo rotado.
5. Reiniciar servicios:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
6. Verificar login, webhooks y ARCA.
7. Eliminar de forma segura copias viejas de `.env.prod` que no se usen.

## Flujo inicial en PC de cliente (recomendado)
1. Copiar `.env.prod.example` a `.env.prod`.
2. Editar `.env.prod` y completar dominio real, emails y datos de integraciones.
3. Ejecutar rotacion de secretos para reemplazar placeholders.
4. Aplicar archivo rotado sobre `.env.prod`.
5. Levantar stack productivo.
6. Correr smoke test de login + reportes + compras + webhooks.

## Validacion minima post-rotacion
- Login UI funciona.
- `POST /api/auth/login/` responde ok con cookie.
- Webhooks Tienda Nube validan firma.
- Conexion a DB estable.
- Emision ARCA operativa (si aplica en entorno).

## Nota critica para instalaciones existentes
- Si cambias `POSTGRES_PASSWORD` en `.env.prod` antes de ejecutar `ALTER ROLE`, la API puede perder acceso a DB al reiniciar.
- Orden obligatorio cuando la DB ya fue inicializada:
  1. Generar nuevo secreto.
  2. `ALTER ROLE` dentro de PostgreSQL.
  3. Actualizar `.env.prod`.
  4. Reiniciar stack.

## Rollback
Si algo falla:
1. Restaurar el `.env.prod` anterior.
2. Reiniciar stack.
3. Investigar secreto externo faltante o variable mal cargada.
