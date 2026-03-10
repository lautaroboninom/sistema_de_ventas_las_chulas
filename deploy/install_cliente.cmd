@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "INSTALL_PS=%SCRIPT_DIR%install_cliente.ps1"
set "SERVICE_PS=%SCRIPT_DIR%retailhub_service.ps1"
set "ACTION=%~1"

if "%ACTION%"=="" set "ACTION=install"

if /I "%ACTION%"=="install" goto :INSTALL
if /I "%ACTION%"=="start" goto :SERVICE
if /I "%ACTION%"=="stop" goto :SERVICE
if /I "%ACTION%"=="status" goto :SERVICE
if /I "%ACTION%"=="restart" goto :SERVICE

echo Uso:
echo   install_cliente.cmd install
echo   install_cliente.cmd start ^| stop ^| status ^| restart
echo.
echo Para parametros avanzados de instalacion, usar deploy\install_cliente.ps1 directo.
exit /b 1

:INSTALL
echo Lanzando instalador con elevacion (UAC)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','\"%INSTALL_PS%\"')"
exit /b %ERRORLEVEL%

:SERVICE
if not exist "%SERVICE_PS%" (
  echo No se encontro %SERVICE_PS%
  exit /b 1
)
echo Ejecutando accion %ACTION%...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SERVICE_PS%" -Action %ACTION%
exit /b %ERRORLEVEL%
