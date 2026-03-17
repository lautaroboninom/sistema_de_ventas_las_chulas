@echo off
setlocal EnableExtensions

set "REPO_URL=https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git"
set "BRANCH=main"
set "INSTALL_ROOT=C:\Users\Las Chulas\Documents\RetailHub"
set "REPO_DIR=%INSTALL_ROOT%\sistema_de_ventas_las_chulas"
set "GIT_EXE=git.exe"
set "DRY_RUN=0"
set "ELEVATED_LAUNCH=0"
set "LOG_FILE_OVERRIDE="
set "LOG_DIR=%TEMP%\RetailHubBootstrap"
set "NO_PAUSE=0"
set "ELEVATION_TRIGGERED=0"
set "SKIP_WINGET_PS=0"

:PARSE_ARGS
if "%~1"=="" goto :ARGS_DONE
if /I "%~1"=="--help" goto :USAGE
if /I "%~1"=="/?" goto :USAGE
if /I "%~1"=="--dry-run" (
  set "DRY_RUN=1"
  shift
  goto :PARSE_ARGS
)
if /I "%~1"=="--elevated" (
  set "ELEVATED_LAUNCH=1"
  shift
  goto :PARSE_ARGS
)
if /I "%~1"=="--log-file" (
  if "%~2"=="" goto :USAGE
  set "LOG_FILE_OVERRIDE=%~2"
  shift
  shift
  goto :PARSE_ARGS
)
if /I "%~1"=="--no-pause" (
  set "NO_PAUSE=1"
  shift
  goto :PARSE_ARGS
)
shift
goto :PARSE_ARGS

:ARGS_DONE
if defined LOG_FILE_OVERRIDE (
  set "LOG_FILE=%LOG_FILE_OVERRIDE%"
  for %%I in ("%LOG_FILE%") do set "LOG_DIR=%%~dpI"
  if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
) else if defined RETAILHUB_LOG_FILE (
  set "LOG_FILE=%RETAILHUB_LOG_FILE%"
  for %%I in ("%LOG_FILE%") do set "LOG_DIR=%%~dpI"
  if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
) else (
  if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
  if not exist "%LOG_DIR%" (
    set "LOG_DIR=."
  )
  for /f %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "LOG_TS=%%I"
  if not defined LOG_TS set "LOG_TS=%RANDOM%"
  set "LOG_FILE=%LOG_DIR%\instalar_cliente_%LOG_TS%.log"
)
if /I "%ELEVATED_LAUNCH%"=="1" (
  >> "%LOG_FILE%" echo [ReinicioElevado] %DATE% %TIME%
) else (
  > "%LOG_FILE%" echo [Inicio] %DATE% %TIME%
)
set "RETAILHUB_LOG_FILE=%LOG_FILE%"

echo ==========================================================
echo  RetailHub - Bootstrap instalacion cliente (Windows)
echo ==========================================================
echo Repo:    %REPO_URL%
echo Branch:  %BRANCH%
echo Destino: %REPO_DIR%
echo Log:     %LOG_FILE%
echo.

call :LOG "Inicio bootstrap. elevated=%ELEVATED_LAUNCH% args=%*"
call :LOG "Repo=%REPO_URL% Branch=%BRANCH% Destino=%REPO_DIR%"

call :LOG "Paso ENSURE_ADMIN: inicio"
call :ENSURE_ADMIN
set "STEP_RC=%ERRORLEVEL%"
call :LOG "Paso ENSURE_ADMIN: rc=%STEP_RC%"
if "%STEP_RC%"=="2" goto :EXIT_RELAUNCH
if not "%STEP_RC%"=="0" goto :EXIT_FAIL

call :LOG "Paso ENSURE_GIT: inicio"
call :ENSURE_GIT
set "STEP_RC=%ERRORLEVEL%"
call :LOG "Paso ENSURE_GIT: rc=%STEP_RC%"
if not "%STEP_RC%"=="0" goto :EXIT_FAIL

call :LOG "Paso ENSURE_WINGET: inicio"
call :ENSURE_WINGET
set "STEP_RC=%ERRORLEVEL%"
call :LOG "Paso ENSURE_WINGET: rc=%STEP_RC%"
if not "%STEP_RC%"=="0" (
  set "SKIP_WINGET_PS=1"
  echo [WARN] winget no disponible. Se continuara sin instalaciones por winget.
  echo [WARN] Si faltan Docker o Tailscale, instalalos manualmente y reintenta.
  call :LOG "ENSURE_WINGET: se continuara con -SkipWinget en install_cliente.ps1."
)

if "%DRY_RUN%"=="1" (
  echo [DRY-RUN] Sin cambios. Finalizando.
  call :LOG "Modo dry-run finalizado OK"
  goto :EXIT_OK
)

call :LOG "Paso SYNC_REPO: inicio"
call :SYNC_REPO
set "STEP_RC=%ERRORLEVEL%"
call :LOG "Paso SYNC_REPO: rc=%STEP_RC%"
if not "%STEP_RC%"=="0" goto :EXIT_FAIL

if not exist "%REPO_DIR%\deploy\install_cliente.ps1" (
  echo [ERROR] No se encontro %REPO_DIR%\deploy\install_cliente.ps1
  call :LOG "ERROR: Falta install_cliente.ps1 en %REPO_DIR%\deploy"
  goto :EXIT_FAIL
)

echo.
echo [INFO] Ejecutando instalador principal...
if "%SKIP_WINGET_PS%"=="1" (
  call :LOG "Instalador principal: ejecutando con -SkipWinget."
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_DIR%\deploy\install_cliente.ps1" -InstallRoot "%INSTALL_ROOT%" -RepoUrl "%REPO_URL%" -Branch "%BRANCH%" -SkipWinget >> "%LOG_FILE%" 2>&1
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_DIR%\deploy\install_cliente.ps1" -InstallRoot "%INSTALL_ROOT%" -RepoUrl "%REPO_URL%" -Branch "%BRANCH%" >> "%LOG_FILE%" 2>&1
)
set "RC=%ERRORLEVEL%"
call :LOG "Instalador principal rc=%RC%"
if not "%RC%"=="0" (
  echo [ERROR] El instalador principal finalizo con codigo %RC%.
  echo [INFO] Revisar log: %LOG_FILE%
  goto :EXIT_FAIL
)

echo.
echo [OK] Bootstrap completado.
echo [INFO] Log: %LOG_FILE%
call :LOG "Bootstrap completado OK"
call :SHOW_NEW_SERVER_URL_GUIDE
echo.
echo Siguientes comandos utiles:
echo   %REPO_DIR%\deploy\install_cliente.cmd status
echo   %REPO_DIR%\deploy\install_cliente.cmd restart
goto :EXIT_OK

:ENSURE_ADMIN
if /I "%ELEVATED_LAUNCH%"=="1" (
  call :LOG "ENSURE_ADMIN: marcado como --elevated, continuando sin revalidar."
  exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$id=[Security.Principal.WindowsIdentity]::GetCurrent();" ^
  "$pr=New-Object Security.Principal.WindowsPrincipal($id);" ^
  "if ($pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 0 } else { exit 1 }" >> "%LOG_FILE%" 2>&1
if not errorlevel 1 (
  call :LOG "ENSURE_ADMIN: sesion actual ya es admin."
  exit /b 0
)
echo [INFO] Requiere permisos de administrador. Solicitando elevacion...
echo [INFO] Se abrira una nueva ventana con permisos de Administrador.
call :LOG "ENSURE_ADMIN: solicitando elevacion UAC..."
set "SELF_PATH=%~f0"
set "SELF_DIR=%~dp0"
set "ELEV_ARGS=--elevated"
if "%DRY_RUN%"=="1" set "ELEV_ARGS=%ELEV_ARGS% --dry-run"
if "%NO_PAUSE%"=="1" set "ELEV_ARGS=%ELEV_ARGS% --no-pause"
set "RETAILHUB_LOG_FILE=%LOG_FILE%"
set "LOCAL_COPY=%TEMP%\retailhub_bootstrap_elevated.bat"
copy /y "%SELF_PATH%" "%LOCAL_COPY%" >nul 2>&1
if exist "%LOCAL_COPY%" (
  call :LOG "ENSURE_ADMIN: copia local creada en %LOCAL_COPY%"
  set "TARGET_PATH=%LOCAL_COPY%"
) else (
  call :LOG "ENSURE_ADMIN: no se pudo copiar a TEMP, se usa ruta original."
  set "TARGET_PATH=%SELF_PATH%"
)
if exist "%SELF_DIR%Git-64-bit.exe" (
  copy /y "%SELF_DIR%Git-64-bit.exe" "%TEMP%\Git-Installer-64bit.exe" >nul 2>&1
  if exist "%TEMP%\Git-Installer-64bit.exe" (
    call :LOG "ENSURE_ADMIN: instalador local Git-64-bit.exe copiado a TEMP."
  ) else (
    call :LOG "ENSURE_ADMIN: no se pudo copiar Git-64-bit.exe local a TEMP."
  )
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "if ([string]::IsNullOrWhiteSpace($env:ELEV_ARGS)) {" ^
  "  Start-Process -FilePath $env:TARGET_PATH -Verb RunAs;" ^
  "} else {" ^
  "  Start-Process -FilePath $env:TARGET_PATH -ArgumentList $env:ELEV_ARGS -Verb RunAs;" ^
  "}" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  echo [ERROR] No se pudo elevar permisos (UAC cancelado o bloqueado).
  call :LOG "ENSURE_ADMIN: fallo elevacion UAC rc=%ERRORLEVEL%"
  exit /b 1
)
call :LOG "ENSURE_ADMIN: elevacion disparada, finaliza proceso no-elevado."
set "ELEVATION_TRIGGERED=1"
exit /b 2

:ENSURE_WINGET
where winget.exe >nul 2>&1
if not errorlevel 1 (
  call :LOG "ENSURE_WINGET: winget disponible."
  exit /b 0
)

echo [INFO] winget no encontrado. Intentando instalar App Installer...
call :LOG "ENSURE_WINGET: winget no encontrado, intentando instalar App Installer."
set "WINGET_BUNDLE=%TEMP%\Microsoft.DesktopAppInstaller.msixbundle"
set "WINGET_URL=https://aka.ms/getwinget"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$bundle = '%WINGET_BUNDLE%';" ^
  "$url = '%WINGET_URL%';" ^
  "try {" ^
  "  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
  "  Invoke-WebRequest -Uri $url -OutFile $bundle -UseBasicParsing -MaximumRedirection 10 -TimeoutSec 300 -Headers @{ 'User-Agent'='Mozilla/5.0' };" ^
  "  Add-AppxPackage -Path $bundle -ErrorAction Stop;" ^
  "  exit 0;" ^
  "} catch {" ^
  "  Write-Host $_.Exception.Message;" ^
  "  exit 1;" ^
  "}" >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
  call :LOG "ENSURE_WINGET: instalacion automatica de App Installer fallo rc=%ERRORLEVEL%"
)

where winget.exe >nul 2>&1
if not errorlevel 1 (
  call :LOG "ENSURE_WINGET: winget disponible tras instalacion."
  exit /b 0
)

call :LOG "ENSURE_WINGET: winget sigue sin estar disponible."
exit /b 1

:SHOW_NEW_SERVER_URL_GUIDE
echo.
echo ==========================================================
echo  GUIA RAPIDA - NUEVA PC SERVIDOR / URL TAILSCALE
echo ==========================================================
echo [PASO 1] Login Tailscale (si aun no esta):
echo   tailscale up
echo.
echo [PASO 2] Obtener URL .ts.net de esta PC:
echo   tailscale status
echo.
echo [PASO 3] En el instalador principal, cuando pida PUBLIC_HOST:
echo   podes pegar:
echo     - retailhub.xxxxx.ts.net
echo     - https://retailhub.xxxxx.ts.net
echo   (el instalador lo normaliza automaticamente)
echo.
echo [PASO 4] Exposicion recomendada (admin privado + webhook publico):
echo   tailscale serve --bg --https=8443 http://127.0.0.1:80
echo   tailscale funnel --bg --https=443 http://127.0.0.1:8080
echo.
echo [PASO 5] Certificado TLS opcional (solo si tu tailnet lo permite):
echo   tailscale cert ^<tu-host^>.ts.net
echo.
echo [PASO 6] Actualizar webhooks en Tienda Nube con la nueva URL .ts.net
echo          (orden-pagada y orden-cancelada).
echo.
echo [NOTA] Este .bat NO ejecuta tailscale cert automaticamente.
echo.
set "TS_HOST="
where tailscale.exe >nul 2>&1
if not errorlevel 1 (
  for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s = & tailscale.exe status --json 2>$null; if ($LASTEXITCODE -ne 0 -or -not $s) { exit 1 }; $o = $s | ConvertFrom-Json; $h = [string]$o.Self.DNSName; $h = $h.Trim().TrimEnd('.'); if ([string]::IsNullOrWhiteSpace($h)) { exit 1 }; Write-Output $h"`) do set "TS_HOST=%%H"
  if defined TS_HOST (
    echo [DETECTADO] URL actual de esta PC: https://%TS_HOST%
    echo            PUBLIC_HOST sugerido: %TS_HOST%
    call :LOG "SHOW_NEW_SERVER_URL_GUIDE: host detectado %TS_HOST%"
  ) else (
    echo [INFO] Tailscale instalado, pero sin host detectado (falta login o status).
    call :LOG "SHOW_NEW_SERVER_URL_GUIDE: tailscale sin host detectado."
  )
) else (
  echo [INFO] Tailscale aun no esta instalado en esta PC.
  echo        El instalador principal intentara instalarlo via winget.
call :LOG "SHOW_NEW_SERVER_URL_GUIDE: tailscale no instalado."
)
echo ==========================================================
echo.
exit /b 0

:ENSURE_GIT
call :RESOLVE_GIT
if not errorlevel 1 exit /b 0

where winget.exe >nul 2>&1
if not errorlevel 1 (
  echo [INFO] Git no encontrado. Instalando con winget...
  call :LOG "ENSURE_GIT: instalando Git con winget..."
  winget.exe install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity >> "%LOG_FILE%" 2>&1
  if errorlevel 1 (
    call :LOG "ENSURE_GIT: winget fallo rc=%ERRORLEVEL%, se intentara descarga directa."
  ) else (
    call :RESOLVE_GIT
    if not errorlevel 1 (
      call :LOG "ENSURE_GIT: git disponible tras instalacion con winget."
      exit /b 0
    )
    call :LOG "ENSURE_GIT: winget finalizo OK pero git no quedo accesible, se intentara descarga directa."
  )
) else (
  call :LOG "ENSURE_GIT: winget no disponible, se intentara descarga directa."
)

echo [INFO] Intentando instalacion directa de Git...
call :INSTALL_GIT_DIRECT
if errorlevel 1 (
  echo [ERROR] No se pudo instalar Git automaticamente.
  echo         Revisa el log: %LOG_FILE%
  call :LOG "ENSURE_GIT: fallo instalacion directa de Git."
  exit /b 1
)

call :RESOLVE_GIT
if not errorlevel 1 (
  call :LOG "ENSURE_GIT: git disponible tras instalacion directa."
  exit /b 0
)

echo [ERROR] Git no quedo disponible despues de los intentos automaticos.
echo         Instala Git manualmente: https://git-scm.com/download/win
echo         Luego reintenta este .bat.
call :LOG "ENSURE_GIT: git no disponible luego de todos los intentos."
exit /b 1

:RESOLVE_GIT
where git.exe >nul 2>&1
if not errorlevel 1 (
  set "GIT_EXE=git.exe"
  call :LOG "RESOLVE_GIT: git encontrado en PATH."
  exit /b 0
)
if exist "%ProgramFiles%\Git\cmd\git.exe" (
  set "GIT_EXE=%ProgramFiles%\Git\cmd\git.exe"
  call :LOG "RESOLVE_GIT: git encontrado en ProgramFiles cmd."
  exit /b 0
)
if exist "%ProgramFiles%\Git\bin\git.exe" (
  set "GIT_EXE=%ProgramFiles%\Git\bin\git.exe"
  call :LOG "RESOLVE_GIT: git encontrado en ProgramFiles bin."
  exit /b 0
)
if exist "%LocalAppData%\Programs\Git\cmd\git.exe" (
  set "GIT_EXE=%LocalAppData%\Programs\Git\cmd\git.exe"
  call :LOG "RESOLVE_GIT: git encontrado en LocalAppData."
  exit /b 0
)
call :LOG "RESOLVE_GIT: git no encontrado."
exit /b 1

:INSTALL_GIT_DIRECT
set "GIT_INSTALLER=%TEMP%\Git-Installer-64bit.exe"
set "GIT_URL=https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"
set "GIT_INSTALLER_READY=0"
if exist "%GIT_INSTALLER%" (
  for %%F in ("%GIT_INSTALLER%") do set "GIT_INSTALLER_SIZE=%%~zF"
  if not defined GIT_INSTALLER_SIZE set "GIT_INSTALLER_SIZE=0"
  if %GIT_INSTALLER_SIZE% GEQ 10000000 (
    set "GIT_INSTALLER_READY=1"
    call :LOG "INSTALL_GIT_DIRECT: reutilizando instalador local en TEMP (%GIT_INSTALLER_SIZE% bytes)."
  ) else (
    call :LOG "INSTALL_GIT_DIRECT: instalador en TEMP demasiado pequeno (%GIT_INSTALLER_SIZE%), se redescarga."
    del /f /q "%GIT_INSTALLER%" >nul 2>&1
  )
)

if "%GIT_INSTALLER_READY%"=="1" goto :DL_DONE

call :LOG "INSTALL_GIT_DIRECT: descargando instalador desde %GIT_URL% (PowerShell, 3 intentos)"
set "DL_TRY=1"
:DL_POWERSHELL_RETRY
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = '%GIT_URL%';" ^
  "$out = '%GIT_INSTALLER%';" ^
  "try {" ^
  "  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
  "  Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -MaximumRedirection 10 -TimeoutSec 300 -Headers @{ 'User-Agent'='Mozilla/5.0' };" ^
  "  exit 0;" ^
  "} catch {" ^
  "  Write-Host $_.Exception.Message;" ^
  "  exit 1;" ^
  "}" >> "%LOG_FILE%" 2>&1
if not errorlevel 1 goto :DL_DONE
call :LOG "INSTALL_GIT_DIRECT: intento PowerShell #%DL_TRY% fallo."
set /a DL_TRY+=1
if %DL_TRY% LEQ 3 (
  timeout /t 3 /nobreak >nul
  goto :DL_POWERSHELL_RETRY
)

call :LOG "INSTALL_GIT_DIRECT: fallback con BITS (Start-BitsTransfer)."
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$url = '%GIT_URL%';" ^
  "$out = '%GIT_INSTALLER%';" ^
  "try {" ^
  "  Import-Module BitsTransfer -ErrorAction Stop;" ^
  "  Start-BitsTransfer -Source $url -Destination $out -TransferType Download -ErrorAction Stop;" ^
  "  exit 0;" ^
  "} catch {" ^
  "  Write-Host $_.Exception.Message;" ^
  "  exit 1;" ^
  "}" >> "%LOG_FILE%" 2>&1
if not errorlevel 1 goto :DL_DONE
call :LOG "INSTALL_GIT_DIRECT: BITS tambien fallo, se prueba curl."

where curl.exe >nul 2>&1
if not errorlevel 1 (
  call :LOG "INSTALL_GIT_DIRECT: fallback con curl.exe"
  curl.exe -L --retry 5 --retry-delay 3 --connect-timeout 30 --max-time 900 -o "%GIT_INSTALLER%" "%GIT_URL%" >> "%LOG_FILE%" 2>&1
  if errorlevel 1 (
    call :LOG "INSTALL_GIT_DIRECT: curl tambien fallo rc=%ERRORLEVEL%"
    exit /b 1
  )
) else (
  call :LOG "INSTALL_GIT_DIRECT: sin curl.exe disponible y fallo PowerShell."
  exit /b 1
)

:DL_DONE
if not exist "%GIT_INSTALLER%" (
  call :LOG "INSTALL_GIT_DIRECT: archivo instalador no existe despues de descargar."
  exit /b 1
)

call :LOG "INSTALL_GIT_DIRECT: ejecutando instalador en modo silencioso (/VERYSILENT)."
"%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP- >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :LOG "INSTALL_GIT_DIRECT: /VERYSILENT fallo rc=%ERRORLEVEL%, probando /SILENT."
  "%GIT_INSTALLER%" /SILENT /NORESTART /SP- >> "%LOG_FILE%" 2>&1
  if errorlevel 1 (
    call :LOG "INSTALL_GIT_DIRECT: /SILENT tambien fallo rc=%ERRORLEVEL%"
    del /f /q "%GIT_INSTALLER%" >nul 2>&1
    exit /b 1
  )
)
del /f /q "%GIT_INSTALLER%" >nul 2>&1
call :LOG "INSTALL_GIT_DIRECT: instalacion finalizada."
exit /b 0

:SYNC_REPO
if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%"
if errorlevel 1 (
  echo [ERROR] No se pudo crear %INSTALL_ROOT%.
  call :LOG "SYNC_REPO: no se pudo crear INSTALL_ROOT rc=%ERRORLEVEL%"
  exit /b 1
)

if exist "%REPO_DIR%\.git" (
  echo [INFO] Repo existente detectado. Actualizando...
  call :LOG "SYNC_REPO: repo existente, actualizando."
  "%GIT_EXE%" -C "%REPO_DIR%" fetch --all --prune >> "%LOG_FILE%" 2>&1
  if errorlevel 1 exit /b 1
  "%GIT_EXE%" -C "%REPO_DIR%" checkout "%BRANCH%" >> "%LOG_FILE%" 2>&1
  if errorlevel 1 exit /b 1
  "%GIT_EXE%" -C "%REPO_DIR%" pull --ff-only origin "%BRANCH%" >> "%LOG_FILE%" 2>&1
  if errorlevel 1 exit /b 1
) else (
  if exist "%REPO_DIR%" (
    echo [ERROR] La carpeta %REPO_DIR% existe pero no es un repo Git.
    echo         Renombrala o borra su contenido para continuar.
    call :LOG "SYNC_REPO: carpeta destino existe sin .git."
    exit /b 1
  )
  echo [INFO] Clonando repo...
  call :LOG "SYNC_REPO: clonando repo nuevo."
  "%GIT_EXE%" clone --branch "%BRANCH%" --single-branch "%REPO_URL%" "%REPO_DIR%" >> "%LOG_FILE%" 2>&1
  if errorlevel 1 exit /b 1
)
call :LOG "SYNC_REPO: completado OK."
exit /b 0

:LOG
if "%~1"=="" exit /b 0
if not defined LOG_FILE exit /b 0
>> "%LOG_FILE%" echo [%DATE% %TIME%] %~1
exit /b 0

:EXIT_OK
call :LOG "Salida OK"
if "%NO_PAUSE%"=="0" (
  echo.
  echo [INFO] Presiona una tecla para cerrar...
  pause >nul
)
exit /b 0

:EXIT_RELAUNCH
call :LOG "Salida OK (relanzado en ventana elevada)."
exit /b 0

:EXIT_FAIL
call :LOG "Salida con error"
if "%NO_PAUSE%"=="0" (
  echo.
  echo [ERROR] Instalacion interrumpida.
  echo [INFO] Log: %LOG_FILE%
  echo [INFO] Presiona una tecla para cerrar...
  pause >nul
)
exit /b 1

:USAGE
echo Uso:
echo   instalar_cliente.bat
echo   instalar_cliente.bat --dry-run
echo   instalar_cliente.bat --no-pause
echo.
echo Que hace:
echo   1) Eleva permisos (UAC)
echo   2) Habilita winget (App Installer) si falta
echo   3) Instala Git si falta (winget / descarga directa / instalador local)
echo   4) Clona/actualiza el repo en %INSTALL_ROOT%
echo   5) Ejecuta deploy\install_cliente.ps1
echo   6) Muestra guia de Tailscale/URL y pasos finales
echo.
echo Tip red restringida:
echo   Si la descarga falla, copia Git-64-bit.exe junto a este .bat y reintenta.
goto :EXIT_OK

