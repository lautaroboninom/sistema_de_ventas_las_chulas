RetailHub - Documentacion

Manual funcional (uso diario)
- [Manual de Usuario RetailHub](docs/MANUAL_USUARIO_RETAILHUB.md)

Indice de documentacion tecnica y operativa
- [Indice en docs](docs/README.md)

Arquitectura rapida
- Backend: `api/service/...` (Django REST)
- Frontend: `web/src/pages/...` (React)
- SQL/Schema: `sql/schema.sql`

Configuracion y despliegue
- Variables de entorno: usar `.env` (local/dev) y `.env.prod` (produccion)
- Modos soportados:
  - `dev`: `docker-compose.yml`
  - `prod`: `docker-compose.prod.yml` (Tailscale + Funnel para webhooks)
- Nginx: `web/deploy/web.nginx.conf` (frontend) y `web/deploy/webhook.nginx.conf` (gateway webhooks)

Seed dev (docker-compose.yml)
- Usuario admin: `admin@laschulas.local`
- Password admin: `Admin1234!`
- Catalogo minimo: proveedor seed + producto `Remera Basica Seed` con variantes color/talle.

Applies SQL incrementales (auto)
- Crear nuevos parches en `api/sql/applies/*.sql`.
- Se ejecutan automaticamente en arranque/update con `python manage.py apply_sql_patches`.
- En `deploy/retailhub_update_manager.ps1` (`apply-on-start`), el backend vuelve a correr `migrate` + `apply_sql_patches`
  aun cuando no haya commits pendientes, para autocorregir instalaciones con applies pendientes.
- Estado guardado en tabla `retail_db_applies` (script + hash + fecha).
- Si un parche ya aplicado cambia de contenido, el proceso falla para evitar inconsistencias.

Tareas post-actualizacion (auto)
- Tabla `retail_post_update_tasks`: tareas de una sola vez que corren en la instalacion del cliente
  despues de una actualizacion (reparaciones de datos, republicaciones en Tienda Nube).
- Se siembran desde un apply SQL y las ejecuta `service/post_update_tasks.py`.
- Disparadores: el frontend al primer ingreso despues de actualizar, y
  `python manage.py run_post_update_tasks` desde `deploy/retailhub_update_manager.ps1`.
- El runner nunca corta el arranque: si una tarea falla queda registrada y se reintenta
  (hasta `max_attempts`).
- Interruptor de emergencia: `RETAILHUB_POST_UPDATE_TASKS_ENABLED=0`.
- El resultado se muestra en el aviso de novedades de la app.

Integraciones externas (estado)
- ARCA WSAA/WSFEv1: disponible segun configuracion fiscal/certificados.
- Tienda Nube API + webhooks: disponible segun credenciales, OAuth y URL HTTPS publica.
- Si falta configuracion externa, tratar como `No disponible / depende de configuracion externa`.
