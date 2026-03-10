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
3. Reemplazar `.env.prod` por el archivo rotado.
4. Reiniciar servicios:
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
5. Verificar login, webhooks y ARCA.
6. Eliminar de forma segura copias viejas de `.env.prod` que no se usen.

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

## Rollback
Si algo falla:
1. Restaurar el `.env.prod` anterior.
2. Reiniciar stack.
3. Investigar secreto externo faltante o variable mal cargada.
