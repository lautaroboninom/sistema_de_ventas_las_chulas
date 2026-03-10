# Instalacion automatizada en PC de cliente (Windows)

Este flujo instala RetailHub en modo cliente unico usando scripts (no `.exe`/`.dll`).

Archivos:
- `deploy/install_cliente.ps1` (instalador principal)
- `deploy/install_cliente.cmd` (launcher con doble click/elevacion)
- `deploy/retailhub_service.ps1` (control start/stop/status/restart)

## 1) Requisitos previos
- Windows 10/11.
- Usuario con permisos de Administrador.
- Conexion a Internet.
- Cuenta Tailscale con Funnel habilitado.
- Credenciales de Tienda Nube y ARCA (si aplica en esta etapa).

## 2) Instalacion rapida
Desde la raiz del repo:

```powershell
.\deploy\install_cliente.cmd install
```

O directo con PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install_cliente.ps1
```

## 3) Parametros del instalador

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install_cliente.ps1 `
  -InstallRoot "C:\RetailHub" `
  -RepoUrl "https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git" `
  -Branch "main" `
  -SkipWinget:$false `
  -SkipTailscale:$false `
  -NonInteractive:$false
```

Parametros:
- `-InstallRoot`: carpeta base de instalacion (default `C:\RetailHub`).
- `-RepoUrl`: URL git HTTPS del repo.
- `-Branch`: rama a instalar/actualizar.
- `-SkipWinget`: omite instalacion de dependencias con winget.
- `-SkipTailscale`: omite login y configuracion Serve/Funnel.
- `-NonInteractive`: no pregunta valores; requiere `.env.prod` ya completo.

## 4) Que hace el instalador
1. Verifica admin, Windows, internet, winget y estado de virtualizacion/WSL2.
2. Instala/actualiza `Git.Git`, `Docker.DockerDesktop`, `Tailscale.Tailscale`.
3. Clona o actualiza el repo en:
   - `C:\RetailHub\sistema_de_ventas_las_chulas`
4. Genera/actualiza `.env.prod`:
   - crea desde `.env.prod.example` si falta.
   - pide `PUBLIC_HOST` + datos de Tienda Nube + ARCA opcional.
   - genera secretos fuertes para `DJANGO_SECRET_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD` cuando faltan o son debiles.
   - deriva:
     - `DJANGO_ALLOWED_HOSTS=<PUBLIC_HOST>`
     - `ALLOWED_ORIGINS=https://<PUBLIC_HOST>:8443,https://<PUBLIC_HOST>`
     - `FRONTEND_ORIGIN=https://<PUBLIC_HOST>:8443`
     - `PUBLIC_WEB_URL=https://<PUBLIC_HOST>`
   - aplica ACL restrictiva al `.env.prod`.
5. Crea volumentes Docker:
   - `laschulas_pg_data`
   - `laschulas_staticfiles`
   - `laschulas_mediafiles`
6. Levanta stack prod:
   - `docker compose -f docker-compose.prod.yml up -d --build`
7. Configura Tailscale:
   - admin privado: `tailscale serve --bg --https=8443 http://127.0.0.1:80`
   - webhooks publicos: `tailscale funnel --bg --https=443 http://127.0.0.1:8080`
8. Crea tarea programada:
   - `RetailHub-Start` al boot (SYSTEM, elevated).
9. Entrega resumen final:
   - admin privado: `https://<dns-tsnet>:8443`
   - webhook publico: `https://<dns-tsnet>/api/retail/online/webhooks/...`

## 5) Control diario del servicio
Con launcher:

```powershell
.\deploy\install_cliente.cmd status
.\deploy\install_cliente.cmd start
.\deploy\install_cliente.cmd stop
.\deploy\install_cliente.cmd restart
```

O directo:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\retailhub_service.ps1 -Action status
```

## 6) Logs
Cada corrida del instalador genera:
- `C:\RetailHub\logs\install_YYYYMMDD_HHMMSS.log`

No se imprimen secretos en log.

## 7) Checklist despues de instalar
1. Cargar webhooks de Tienda Nube apuntando al host publico.
2. Probar orden pagada y orden cancelada.
3. Validar login, compras, ventas y reportes.
4. Rotar secretos expuestos durante pruebas y actualizar tokens.

## 8) Notas importantes
- Modo soportado: cliente unico (una tienda / una instalacion).
- No correr dos entornos productivos con webhooks activos en paralelo.
- Si Docker Desktop pide reinicio o login inicial, completarlo y reintentar instalador.
