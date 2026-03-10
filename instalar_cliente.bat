@echo off
setlocal EnableExtensions

set "REPO_URL=https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git"
set "BRANCH=main"
set "INSTALL_ROOT=C:\RetailHub"
set "REPO_DIR=%INSTALL_ROOT%\sistema_de_ventas_las_chulas"
set "GIT_EXE=git.exe"
set "DRY_RUN=0"

if /I "%~1"=="--help" goto :USAGE
if /I "%~1"=="/?" goto :USAGE
if /I "%~1"=="--dry-run" set "DRY_RUN=1"

echo ==========================================================
echo  RetailHub - Bootstrap instalacion cliente (Windows)
echo ==========================================================
echo Repo:    %REPO_URL%
echo Branch:  %BRANCH%
echo Destino: %REPO_DIR%
echo.

call :ENSURE_ADMIN
if errorlevel 1 exit /b 1

call :ENSURE_GIT
if errorlevel 1 exit /b 1

if "%DRY_RUN%"=="1" (
  echo [DRY-RUN] Sin cambios. Finalizando.
  exit /b 0
)

call :SYNC_REPO
if errorlevel 1 exit /b 1

if not exist "%REPO_DIR%\deploy\install_cliente.ps1" (
  echo [ERROR] No se encontro %REPO_DIR%\deploy\install_cliente.ps1
  exit /b 1
)

echo.
echo [INFO] Ejecutando instalador principal...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO_DIR%\deploy\install_cliente.ps1" -InstallRoot "%INSTALL_ROOT%" -RepoUrl "%REPO_URL%" -Branch "%BRANCH%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo [ERROR] El instalador principal finalizo con codigo %RC%.
  exit /b %RC%
)

echo.
echo [OK] Bootstrap completado.
echo.
echo Siguientes comandos utiles:
echo   %REPO_DIR%\deploy\install_cliente.cmd status
echo   %REPO_DIR%\deploy\install_cliente.cmd restart
exit /b 0

:ENSURE_ADMIN
net session >nul 2>&1
if %ERRORLEVEL%==0 (
  exit /b 0
)
echo [INFO] Requiere permisos de administrador. Solicitando elevacion...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] No se pudo elevar permisos (UAC cancelado o bloqueado).
  exit /b 1
)
exit /b 1

:ENSURE_GIT
where git.exe >nul 2>&1
if %ERRORLEVEL%==0 (
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

where winget.exe >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Git no encontrado y winget no disponible.
  echo         Instala Git manualmente y vuelve a ejecutar este .bat.
  exit /b 1
)

echo [INFO] Git no encontrado. Instalando con winget...
winget.exe install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] Fallo la instalacion de Git con winget.
  exit /b 1
)

if exist "%ProgramFiles%\Git\cmd\git.exe" (
  set "GIT_EXE=%ProgramFiles%\Git\cmd\git.exe"
  exit /b 0
)
where git.exe >nul 2>&1
if %ERRORLEVEL%==0 (
  set "GIT_EXE=git.exe"
  exit /b 0
)

echo [ERROR] Git no quedo disponible despues de instalar.
exit /b 1

:SYNC_REPO
if not exist "%INSTALL_ROOT%" mkdir "%INSTALL_ROOT%"
if %ERRORLEVEL% NEQ 0 (
  echo [ERROR] No se pudo crear %INSTALL_ROOT%.
  exit /b 1
)

if exist "%REPO_DIR%\.git" (
  echo [INFO] Repo existente detectado. Actualizando...
  "%GIT_EXE%" -C "%REPO_DIR%" fetch --all --prune
  if %ERRORLEVEL% NEQ 0 exit /b 1
  "%GIT_EXE%" -C "%REPO_DIR%" checkout "%BRANCH%"
  if %ERRORLEVEL% NEQ 0 exit /b 1
  "%GIT_EXE%" -C "%REPO_DIR%" pull --ff-only origin "%BRANCH%"
  if %ERRORLEVEL% NEQ 0 exit /b 1
) else (
  if exist "%REPO_DIR%" (
    echo [ERROR] La carpeta %REPO_DIR% existe pero no es un repo Git.
    echo         Renombrala o borra su contenido para continuar.
    exit /b 1
  )
  echo [INFO] Clonando repo...
  "%GIT_EXE%" clone --branch "%BRANCH%" --single-branch "%REPO_URL%" "%REPO_DIR%"
  if %ERRORLEVEL% NEQ 0 exit /b 1
)
exit /b 0

:USAGE
echo Uso:
echo   instalar_cliente.bat
echo   instalar_cliente.bat --dry-run
echo.
echo Que hace:
echo   1) Eleva permisos (UAC)
echo   2) Instala Git si falta (winget)
echo   3) Clona/actualiza el repo en C:\RetailHub
echo   4) Ejecuta deploy\install_cliente.ps1
exit /b 0
