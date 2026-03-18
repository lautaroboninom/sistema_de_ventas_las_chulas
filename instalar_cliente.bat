@echo off
setlocal EnableExtensions

set "REPO_URL=https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git"
set "BRANCH=main"
set "INSTALL_ROOT=C:\Users\Las Chulas\Documents\RetailHub"
set "REPO_DIR=%INSTALL_ROOT%\sistema_de_ventas_las_chulas"
set "DEFAULT_PUBLIC_HOST=retailhub.taila1413b.ts.net"
set "PUBLIC_HOST="
if defined RETAILHUB_EXPECTED_PUBLIC_HOST set "PUBLIC_HOST=%RETAILHUB_EXPECTED_PUBLIC_HOST%"
if not defined PUBLIC_HOST set "PUBLIC_HOST=%DEFAULT_PUBLIC_HOST%"
set "GIT_EXE=git.exe"
set "DRY_RUN=0"
set "ELEVATED_LAUNCH=0"
set "LOG_FILE_OVERRIDE="
set "LOG_DIR=%TEMP%\RetailHubBootstrap"
set "NO_PAUSE=0"
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
if /I "%~1"=="--public-host" (
  if "%~2"=="" goto :USAGE
  set "PUBLIC_HOST=%~2"
  shift
  shift
  goto :PARSE_ARGS
)
shift
goto :PARSE_ARGS

:ARGS_DONE
call :NORMALIZE_PUBLIC_HOST

if defined LOG_FILE_OVERRIDE (
  set "LOG_FILE=%LOG_FILE_OVERRIDE%"
  for %%I in ("%LOG_FILE%") do set "LOG_DIR=%%~dpI"
  if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
) else if defined RETAILHUB_LOG_FILE (
  set "LOG_FILE=%RETAILHUB_LOG_FILE%"
  for %%I in ("%LOG_FILE%") do set "LOG_DIR=%%~dpI"
  if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
) else (
  call :SET_DEFAULT_LOG_FILE
)

if /I "%ELEVATED_LAUNCH%"=="1" (
  >> "%LOG_FILE%" echo [ReinicioElevado] %DATE% %TIME%
) else (
  > "%LOG_FILE%" echo [Inicio] %DATE% %TIME%
)
set "RETAILHUB_LOG_FILE=%LOG_FILE%"
set "RETAILHUB_EXPECTED_PUBLIC_HOST=%PUBLIC_HOST%"

echo ==========================================================
echo  RetailHub - Bootstrap instalacion cliente ^(Windows^)
echo ==========================================================
echo Repo:          %REPO_URL%
echo Branch:        %BRANCH%
echo Destino:       %REPO_DIR%
echo Host esperado: %PUBLIC_HOST%
echo Log:           %LOG_FILE%
echo.

call :LOG "Inicio bootstrap. elevated=%ELEVATED_LAUNCH% dry_run=%DRY_RUN% host=%PUBLIC_HOST%"

call :ENSURE_ADMIN
set "STEP_RC=%ERRORLEVEL%"
if "%STEP_RC%"=="2" goto :EXIT_RELAUNCH
if not "%STEP_RC%"=="0" goto :EXIT_FAIL

call :ENSURE_GIT
set "STEP_RC=%ERRORLEVEL%"
if not "%STEP_RC%"=="0" goto :EXIT_FAIL

call :ENSURE_WINGET
set "STEP_RC=%ERRORLEVEL%"
if "%STEP_RC%"=="2" (
  set "SKIP_WINGET_PS=1"
  call :LOG "winget no disponible. install_cliente.ps1 correra con -SkipWinget."
)
if not "%STEP_RC%"=="0" if not "%STEP_RC%"=="2" goto :EXIT_FAIL

call :ENSURE_BOOTSTRAP_REPO
set "STEP_RC=%ERRORLEVEL%"
if not "%STEP_RC%"=="0" goto :EXIT_FAIL

if "%DRY_RUN%"=="1" (
  call :REPORT_STEP "SKIP" "Bootstrap" "Dry-run completado sin cambios."
  goto :EXIT_OK
)

if not exist "%REPO_DIR%\deploy\install_cliente.ps1" (
  call :REPORT_STEP "FAIL" "Bootstrap" "No se encontro %REPO_DIR%\deploy\install_cliente.ps1."
  goto :EXIT_FAIL
)

echo.
echo [INFO] Ejecutando instalador principal...
call :LOG "Invocando install_cliente.ps1 para host %PUBLIC_HOST%."
if "%SKIP_WINGET_PS%"=="1" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_DIR%\deploy\install_cliente.ps1" -InstallRoot "%INSTALL_ROOT%" -RepoUrl "%REPO_URL%" -Branch "%BRANCH%" -ExpectedPublicHost "%PUBLIC_HOST%" -SkipWinget >> "%LOG_FILE%" 2>&1
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_DIR%\deploy\install_cliente.ps1" -InstallRoot "%INSTALL_ROOT%" -RepoUrl "%REPO_URL%" -Branch "%BRANCH%" -ExpectedPublicHost "%PUBLIC_HOST%" >> "%LOG_FILE%" 2>&1
)
set "RC=%ERRORLEVEL%"
call :LOG "Instalador principal rc=%RC%"

if "%RC%"=="10" (
  call :REPORT_STEP "BLOCKED" "Bootstrap" "Instalacion parcial: Docker/base OK, Tailscale pendiente."
  call :SHOW_NEW_SERVER_URL_GUIDE
  goto :EXIT_PARTIAL
)
if not "%RC%"=="0" (
  call :REPORT_STEP "FAIL" "Bootstrap" "El instalador principal finalizo con codigo %RC%."
  goto :EXIT_FAIL
)

call :REPORT_STEP "RUN" "Bootstrap" "Instalacion principal completada."
call :SHOW_NEW_SERVER_URL_GUIDE
goto :EXIT_OK

:NORMALIZE_PUBLIC_HOST
set "RETAILHUB_PUBLIC_HOST_RAW=%PUBLIC_HOST%"
for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$h = [string]$env:RETAILHUB_PUBLIC_HOST_RAW; $h = $h.Trim(); $h = $h -replace '^\s*https?://', ''; $h = $h.Trim().TrimEnd('/'); if ([string]::IsNullOrWhiteSpace($h)) { $h = '%DEFAULT_PUBLIC_HOST%' }; Write-Output $h"`) do set "PUBLIC_HOST=%%H"
if not defined PUBLIC_HOST set "PUBLIC_HOST=%DEFAULT_PUBLIC_HOST%"
exit /b 0

:REPORT_STEP
if "%~1"=="" exit /b 0
if "%~2"=="" exit /b 0
echo [%~1] %~2 - %~3
call :LOG "[%~1] %~2 - %~3"
exit /b 0

:ENSURE_ADMIN
if /I "%ELEVATED_LAUNCH%"=="1" (
  call :REPORT_STEP "SKIP" "Admin" "La ventana ya se relanzo con elevacion."
  exit /b 0
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$id=[Security.Principal.WindowsIdentity]::GetCurrent();" ^
  "$pr=New-Object Security.Principal.WindowsPrincipal($id);" ^
  "if ($pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 0 } else { exit 1 }" >> "%LOG_FILE%" 2>&1
if not errorlevel 1 (
  call :REPORT_STEP "SKIP" "Admin" "La sesion actual ya es administrador."
  exit /b 0
)

call :REPORT_STEP "RUN" "Admin" "Se solicitara elevacion UAC."
set "SELF_PATH=%~f0"
set "SELF_DIR=%~dp0"
set "ELEV_ARGS=--elevated"
if "%DRY_RUN%"=="1" set "ELEV_ARGS=%ELEV_ARGS% --dry-run"
if "%NO_PAUSE%"=="1" set "ELEV_ARGS=%ELEV_ARGS% --no-pause"
set "LOCAL_COPY=%TEMP%\retailhub_bootstrap_elevated.bat"
copy /y "%SELF_PATH%" "%LOCAL_COPY%" >nul 2>&1
if exist "%LOCAL_COPY%" (
  set "TARGET_PATH=%LOCAL_COPY%"
) else (
  set "TARGET_PATH=%SELF_PATH%"
)
if exist "%SELF_DIR%Git-64-bit.exe" (
  copy /y "%SELF_DIR%Git-64-bit.exe" "%TEMP%\Git-Installer-64bit.exe" >nul 2>&1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process -FilePath $env:TARGET_PATH -ArgumentList $env:ELEV_ARGS -Verb RunAs" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  call :REPORT_STEP "FAIL" "Admin" "No se pudo elevar permisos ^(UAC cancelado o bloqueado^)."
  exit /b 1
)
exit /b 2

:ENSURE_WINGET
where winget.exe >nul 2>&1
if not errorlevel 1 (
  call :REPORT_STEP "SKIP" "winget" "winget ya estaba disponible."
  exit /b 0
)

if "%DRY_RUN%"=="1" (
  call :REPORT_STEP "BLOCKED" "winget" "winget falta y se omitio su instalacion por dry-run."
  exit /b 2
)

set "WINGET_BUNDLE=%TEMP%\Microsoft.DesktopAppInstaller.msixbundle"
set "WINGET_URL=https://aka.ms/getwinget"
call :LOG "Intentando instalar App Installer para recuperar winget."
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

where winget.exe >nul 2>&1
if not errorlevel 1 (
  call :REPORT_STEP "RUN" "winget" "App Installer se instalo y winget quedo disponible."
  exit /b 0
)

call :REPORT_STEP "BLOCKED" "winget" "winget sigue sin estar disponible; PowerShell correra con -SkipWinget."
exit /b 2

:ENSURE_GIT
call :RESOLVE_GIT
if not errorlevel 1 (
  call :REPORT_STEP "SKIP" "Git" "Git ya estaba disponible."
  exit /b 0
)

if "%DRY_RUN%"=="1" (
  call :REPORT_STEP "BLOCKED" "Git" "Git falta y se omitio su instalacion por dry-run."
  exit /b 0
)

where winget.exe >nul 2>&1
if not errorlevel 1 (
  call :LOG "Instalando Git con winget..."
  winget.exe install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity >> "%LOG_FILE%" 2>&1
  call :RESOLVE_GIT
  if not errorlevel 1 (
    call :REPORT_STEP "RUN" "Git" "Git se instalo con winget."
    exit /b 0
  )
)

call :LOG "Intentando instalacion directa de Git."
call :INSTALL_GIT_DIRECT
if errorlevel 1 (
  call :REPORT_STEP "FAIL" "Git" "No se pudo instalar Git automaticamente."
  exit /b 1
)

call :RESOLVE_GIT
if not errorlevel 1 (
  call :REPORT_STEP "RUN" "Git" "Git se instalo por descarga directa."
  exit /b 0
)

call :REPORT_STEP "FAIL" "Git" "Git no quedo disponible despues de los intentos automaticos."
exit /b 1

:RESOLVE_GIT
where git.exe >nul 2>&1
if not errorlevel 1 (
  set "GIT_EXE=git.exe"
  exit /b 0
)
if exist "%ProgramFiles%\Git\cmd\git.exe" (
  set "GIT_EXE=%ProgramFiles%\Git\cmd\git.exe"
  exit /b 0
)
if exist "%ProgramFiles%\Git\bin\git.exe" (
  set "GIT_EXE=%ProgramFiles%\Git\bin\git.exe"
  exit /b 0
)
if exist "%LocalAppData%\Programs\Git\cmd\git.exe" (
  set "GIT_EXE=%LocalAppData%\Programs\Git\cmd\git.exe"
  exit /b 0
)
exit /b 1

:INSTALL_GIT_DIRECT
set "GIT_INSTALLER=%TEMP%\Git-Installer-64bit.exe"
set "GIT_URL=https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"
if exist "%GIT_INSTALLER%" del /f /q "%GIT_INSTALLER%" >nul 2>&1

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
if errorlevel 1 exit /b 1
if not exist "%GIT_INSTALLER%" exit /b 1

"%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP- >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
  "%GIT_INSTALLER%" /SILENT /NORESTART /SP- >> "%LOG_FILE%" 2>&1
  if errorlevel 1 (
    del /f /q "%GIT_INSTALLER%" >nul 2>&1
    exit /b 1
  )
)
del /f /q "%GIT_INSTALLER%" >nul 2>&1
exit /b 0

:ENSURE_BOOTSTRAP_REPO
if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%" >nul 2>&1
if errorlevel 1 (
  call :REPORT_STEP "FAIL" "Repositorio" "No se pudo crear %INSTALL_ROOT%."
  exit /b 1
)

if exist "%REPO_DIR%\.git" (
  if exist "%REPO_DIR%\deploy\install_cliente.ps1" (
    call :REPORT_STEP "SKIP" "Repositorio" "Repo ya presente; la actualizacion segura la hara install_cliente.ps1."
    exit /b 0
  )
  if "%DRY_RUN%"=="1" (
    call :REPORT_STEP "BLOCKED" "Repositorio" "El repo local existe pero esta incompleto; dry-run no lo reemplaza."
    exit /b 0
  )
  call :BACKUP_REPO_DIR "%REPO_DIR%"
  if errorlevel 1 exit /b 1
  goto :CLONE_REPO
)

if exist "%REPO_DIR%" (
  if exist "%REPO_DIR%\deploy\install_cliente.ps1" (
    call :REPORT_STEP "BLOCKED" "Repositorio" "Carpeta local utilizable sin .git; se reutiliza sin actualizar."
    exit /b 0
  )
  if "%DRY_RUN%"=="1" (
    call :REPORT_STEP "BLOCKED" "Repositorio" "Existe una carpeta no utilizable y dry-run no la reemplaza."
    exit /b 0
  )
  call :BACKUP_REPO_DIR "%REPO_DIR%"
  if errorlevel 1 exit /b 1
)

if "%DRY_RUN%"=="1" (
  call :REPORT_STEP "BLOCKED" "Repositorio" "El repo no existe y habria que clonarlo."
  exit /b 0
)

:CLONE_REPO
call :CLONE_REPO_WITH_RETRY
if errorlevel 1 (
  call :REPORT_STEP "FAIL" "Repositorio" "No se pudo clonar el repositorio."
  exit /b 1
)
call :REPORT_STEP "RUN" "Repositorio" "Repositorio clonado en %REPO_DIR%."
exit /b 0

:BACKUP_REPO_DIR
if "%~1"=="" exit /b 1
if not exist "%~1" exit /b 0

for %%D in ("%~1") do set "REPO_BASENAME=%%~nxD"
for %%D in ("%~1") do set "REPO_PARENT=%%~dpD"
for /f %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "REPO_BAK_TS=%%I"
if not defined REPO_BAK_TS set "REPO_BAK_TS=%RANDOM%"
set "REPO_BACKUP_NAME=%REPO_BASENAME%_backup_%REPO_BAK_TS%"

pushd "%REPO_PARENT%" >nul 2>&1
if errorlevel 1 exit /b 1
ren "%REPO_BASENAME%" "%REPO_BACKUP_NAME%" >nul 2>&1
if errorlevel 1 (
  popd >nul 2>&1
  exit /b 1
)
popd >nul 2>&1
call :LOG "Repo existente respaldado en %REPO_PARENT%%REPO_BACKUP_NAME%"
exit /b 0

:CLONE_REPO_WITH_RETRY
set "CLONE_TRY=1"
:CLONE_RETRY_LOOP
"%GIT_EXE%" clone --branch "%BRANCH%" --single-branch "%REPO_URL%" "%REPO_DIR%" >> "%LOG_FILE%" 2>&1
if not errorlevel 1 exit /b 0
if exist "%REPO_DIR%" rmdir /s /q "%REPO_DIR%" >nul 2>&1
if "%CLONE_TRY%"=="3" exit /b 1
set /a CLONE_TRY+=1
timeout /t 3 /nobreak >nul
goto :CLONE_RETRY_LOOP

:SHOW_NEW_SERVER_URL_GUIDE
echo.
echo ==========================================================
echo  GUIA RAPIDA - TAILSCALE Y URL PUBLICA
echo ==========================================================
echo Host esperado para esta instalacion: %PUBLIC_HOST%
echo.
echo Si el DNS real de Tailscale no coincide:
echo   1^)^ Verifica tailscale status
echo   2^)^ Mueve esta PC al tailnet correcto o renombra el nodo
echo   3^)^ Reejecuta este .bat
echo.
echo Exposicion esperada cuando el host coincide:
echo   tailscale serve --bg --https=8443 http://127.0.0.1:80
echo   tailscale funnel --bg --https=443 http://127.0.0.1:8080
echo.
echo Certificados:
echo   install_cliente.ps1 intentara emitir/renovar tls.crt y tls.key
echo   automaticamente cuando el DNS real coincida con %PUBLIC_HOST%.
echo.
set "TS_HOST="
where tailscale.exe >nul 2>&1
if not errorlevel 1 (
  for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s = & tailscale.exe status --json 2>$null; if ($LASTEXITCODE -ne 0 -or -not $s) { exit 1 }; $o = $s | ConvertFrom-Json; $h = [string]$o.Self.DNSName; $h = $h.Trim().TrimEnd('.'); if ([string]::IsNullOrWhiteSpace($h)) { exit 1 }; Write-Output $h"`) do set "TS_HOST=%%H"
  if defined TS_HOST (
    echo Host actual detectado: %TS_HOST%
  ) else (
    echo Tailscale instalado, pero sin DNS detectado.
  )
) else (
  echo Tailscale aun no esta instalado en esta PC.
)
echo ==========================================================
echo.
exit /b 0

:SET_DEFAULT_LOG_FILE
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
if not exist "%LOG_DIR%" set "LOG_DIR=."
set "LOG_TS="
for /f %%I in ('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "(Get-Date).ToString(\"yyyyMMdd_HHmmss\")"') do set "LOG_TS=%%I"
if not defined LOG_TS set "LOG_TS=%RANDOM%"
set "LOG_FILE=%LOG_DIR%\instalar_cliente_%LOG_TS%.log"
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

:EXIT_PARTIAL
call :LOG "Salida parcial"
if "%NO_PAUSE%"=="0" (
  echo.
  echo [WARN] Instalacion parcial.
  echo [INFO] Log: %LOG_FILE%
  echo [INFO] Presiona una tecla para cerrar...
  pause >nul
)
exit /b 10

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
echo   instalar_cliente.bat --public-host retailhub.taila1413b.ts.net
echo   instalar_cliente.bat --dry-run
echo   instalar_cliente.bat --no-pause
echo.
echo Que hace:
echo   1^) Eleva permisos ^(UAC^)
echo   2^) Verifica Git y lo instala si falta
echo   3^) Verifica winget sin bloquear el flujo si ya no hace falta
echo   4^) Garantiza una copia utilizable del repo
echo   5^) Ejecuta deploy\install_cliente.ps1 con el host esperado
echo   6^) Devuelve 0 ^(completo^), 10 ^(parcial por Tailscale^) o 1 ^(falla^)
echo.
echo Tip:
echo   Si la descarga de Git falla, copia Git-64-bit.exe junto a este .bat y reintenta.
goto :EXIT_OK
