# Instalacion automatizada en PC de cliente (Windows)

Este flujo instala RetailHub en modo cliente unico usando scripts (no `.exe`/`.dll`).

Archivos:
- `instalar_cliente.bat` (bootstrap 1-click: clona/actualiza repo y dispara instalador)
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
Opcion recomendada (bootstrap):

```powershell
.\instalar_cliente.bat
.\instalar_cliente.bat --public-host retailhub.taila1413b.ts.net
```

Este `.bat`:
1. Eleva permisos.
2. Verifica Git y lo instala si falta.
3. Reutiliza una copia utilizable del repo o la clona si aun no existe.
4. Ejecuta `deploy/install_cliente.ps1` con el host esperado.

Opcion manual:

```powershell
.\deploy\install_cliente.cmd install
```

O directo con PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install_cliente.ps1
```

## 2.1 Ayuda del bootstrap

```powershell
.\instalar_cliente.bat --help
.\instalar_cliente.bat --dry-run
.\instalar_cliente.bat --public-host retailhub.taila1413b.ts.net
```

`--dry-run` no instala ni clona; solo valida flujo base.

## 2.2 Instalacion rapida (sin bootstrap)
Desde la raiz del repo:

```powershell
.\deploy\install_cliente.cmd install
```

## 3) Parametros del instalador

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\install_cliente.ps1 `
  -InstallRoot "C:\RetailHub" `
  -RepoUrl "https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git" `
  -Branch "main" `
  -ExpectedPublicHost "retailhub.taila1413b.ts.net" `
  -SkipWinget:$false `
  -SkipTailscale:$false `
  -NonInteractive:$false
```

Parametros:
- `-InstallRoot`: carpeta base de instalacion (default `C:\RetailHub`).
- `-RepoUrl`: URL git HTTPS del repo.
- `-Branch`: rama a instalar/actualizar.
- `-ExpectedPublicHost`: host publico esperado para `.env.prod` y validacion de Tailscale.
- `-SkipWinget`: omite instalacion de dependencias con winget.
- `-SkipTailscale`: omite login y configuracion Serve/Funnel.
- `-NonInteractive`: no pregunta valores; requiere `.env.prod` ya completo.

## 4) Que hace el instalador
1. Verifica admin, Windows, internet y estado de virtualizacion/WSL2.
2. Reutiliza dependencias ya instaladas y solo instala con winget lo que falta.
3. Reutiliza el repo si esta usable; solo hace `fetch/pull --ff-only` cuando la copia local esta limpia y alineada.
4. Genera o reconcilia `.env.prod` hacia `-ExpectedPublicHost`:
   - crea desde `.env.prod.example` si falta.
   - reutiliza valores existentes validos.
   - genera secretos fuertes para `DJANGO_SECRET_KEY`, `JWT_SECRET`, `POSTGRES_PASSWORD` cuando faltan o son debiles.
   - deriva:
     - `DJANGO_ALLOWED_HOSTS=<PUBLIC_HOST>`
     - `ALLOWED_ORIGINS=https://<PUBLIC_HOST>:8443,https://<PUBLIC_HOST>`
     - `FRONTEND_ORIGIN=https://<PUBLIC_HOST>:8443`
     - `PUBLIC_WEB_URL=https://<PUBLIC_HOST>`
   - aplica ACL restrictiva al `.env.prod`.
5. Levanta o reconcilia el stack prod:
   - crea volumenes Docker faltantes.
   - guarda fingerprint local con commit + hash de `.env.prod` + hash de `docker-compose.prod.yml`.
   - solo ejecuta `docker compose -f docker-compose.prod.yml up -d --build` cuando hay cambios o contenedores faltantes/degradados.
6. Despues de Docker, valida Tailscale:
   - hace `tailscale up` solo si falta login.
   - compara el `DNSName` real de la PC con `-ExpectedPublicHost`.
   - si no coincide, termina parcial con codigo `10` y no toca Serve/Funnel/certs.
7. Si el host coincide, configura:
   - admin privado: `tailscale serve --bg --https=8443 http://127.0.0.1:80`
   - webhooks publicos: `tailscale funnel --bg --https=443 http://127.0.0.1:8080`
   - certificados locales: `tailscale cert --cert-file certs\tls.crt --key-file certs\tls.key --min-validity 720h <host>`
8. Crea o actualiza la tarea programada:
   - `RetailHub-Start` al boot (SYSTEM, elevated).
9. Entrega resumen final por paso con estados `SKIP`, `RUN`, `UPDATED`, `BLOCKED`, `FAIL`.

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

Codigos de salida:
- `0`: instalacion completa.
- `10`: instalacion parcial; Docker/base OK, Tailscale pendiente por host/tailnet.
- `1`: fallo real de prerequisito o despliegue.

## 7) Checklist despues de instalar
1. Cargar webhooks de Tienda Nube apuntando al host publico.
2. Probar orden pagada y orden cancelada.
3. Validar login, compras, ventas y reportes.
4. Rotar secretos expuestos durante pruebas y actualizar tokens.

## 8) Notas importantes
- Modo soportado: cliente unico (una tienda / una instalacion).
- No correr dos entornos productivos con webhooks activos en paralelo.
- Si Docker Desktop pide reinicio o login inicial, completarlo y reintentar instalador.
- Si el host esperado no coincide con `tailscale status`, el instalador no intentara forzarlo: dejara la instalacion parcial y esperara que el tailnet/nodo se corrija afuera del script.
