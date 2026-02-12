Manual del Sistema de Reparaciones (Equilux)

Objetivo
- Documentar el funcionamiento operativo del sistema y sus reglas principales.

Roles
- `jefe`, `jefe_veedor`, `admin`, `recepcion`, `tecnico`.

Estados
- Ticket (`ticket_state`): `ingresado`, `diagnosticado`, `presupuestado`, `reparar`, `controlado_sin_defecto`, `reparado`, `liberado`, `entregado`, `baja`, `derivado`, `alquilado`.
- Presupuesto (`quote_estado`): `pendiente`, `emitido`, `presupuestado`, `aprobado`, `rechazado`, `no_aplica`.

Flujos principales
- Ingreso de equipo y carga de datos/fotos.
- Diagnóstico y resolución técnica.
- Presupuestación, aprobación/rechazo y envío.
- Reparación, liberación (remito) y entrega.
- Derivaciones a proveedor externo y devolución.

Reglas de base de datos
- El esquema base está consolidado en `sql/schema.sql`.
- La unicidad de derivación abierta por ingreso se aplica en `sql/schema.sql` (índice parcial).
- Triggers de auditoría de cambios y sincronización de estados incluidos en `sql/schema.sql`.

Pantallas relevantes
- Hoja de servicio: `web/src/pages/ServiceSheet.jsx`.
- Aprobados: `web/src/pages/Aprobados.jsx`.
- Presupuestados: `web/src/pages/Presupuestados.jsx`.
- Derivados: `web/src/pages/Derivados.jsx`.
- Listos para retiro: `web/src/pages/AdminListos.jsx`.
- Repuestos: `web/src/pages/Repuestos.jsx`.

Configuración y deploy
- Variables de entorno: `.env`, `.env.prod`, `.env.prod.internet`.
- Docker Compose: `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.prod.internet.yml`.

Prueba en VM (internet público)
- Dominio configurado para internet: `reparaciones.equiluxmd.com` (en `.env.prod.internet`).
- Ejecutar precheck:
  - `powershell -ExecutionPolicy Bypass -File deploy/vm_internet_precheck.ps1`
- Levantar stack internet:
  - `powershell -ExecutionPolicy Bypass -File deploy/vm_internet_up.ps1`
- Si querés que el script abra el firewall local en la VM:
  - `powershell -ExecutionPolicy Bypass -File deploy/vm_internet_up.ps1 -OpenFirewall`
- Ver logs del proxy:
  - `docker compose -f docker-compose.prod.internet.yml --env-file .env.prod.internet logs -f reverse-proxy`
