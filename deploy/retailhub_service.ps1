[CmdletBinding()]
param(
  [ValidateSet("start", "stop", "status", "restart")]
  [string]$Action = "status",
  [string]$InstallRoot = "C:\RetailHub",
  [switch]$SkipUpdates
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Join-Path ([System.IO.Path]::GetFullPath($InstallRoot)) "sistema_de_ventas_las_chulas"
if (-not (Test-Path $repoRoot)) {
  throw "No se encontro el repositorio en $repoRoot"
}

$dockerCmd = Get-Command docker.exe -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
  $fallback = "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
  if (Test-Path $fallback) {
    $dockerExe = $fallback
  } else {
    throw "No se encontro docker.exe. Abre Docker Desktop o reinstala Docker."
  }
} else {
  $dockerExe = $dockerCmd.Source
}

function Invoke-Compose {
  param([string[]]$Args)
  & $dockerExe compose -f docker-compose.prod.yml @Args
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose fallo para accion '$Action'."
  }
}

function Invoke-StartupUpdates {
  if ($SkipUpdates) {
    Write-Host "RetailHub updates: omitido por -SkipUpdates."
    return
  }

  $updateScript = Join-Path $repoRoot "deploy\retailhub_update_manager.ps1"
  if (-not (Test-Path $updateScript)) {
    Write-Host "RetailHub updates: script no encontrado, se continua sin apply-on-start."
    return
  }

  $psExe = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
  if (-not (Test-Path $psExe)) {
    $psCmd = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($psCmd) {
      $psExe = $psCmd.Source
    }
  }
  if (-not (Test-Path $psExe)) {
    Write-Host "RetailHub updates: no se encontro powershell.exe para ejecutar apply-on-start."
    return
  }

  try {
    $raw = & $psExe -NoProfile -ExecutionPolicy Bypass -File $updateScript -Mode apply-on-start -RetailHubRoot $InstallRoot -Channel main -SkipBackendMigrate -Json 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Host "RetailHub updates: apply-on-start devolvio exit $LASTEXITCODE."
      return
    }

    $jsonLine = $null
    foreach ($line in ($raw | ForEach-Object { [string]$_ })) {
      $trimmed = $line.Trim()
      if ($trimmed.StartsWith('{') -and $trimmed.EndsWith('}')) {
        $jsonLine = $trimmed
      }
    }
    if ([string]::IsNullOrWhiteSpace($jsonLine)) {
      Write-Host "RetailHub updates: no se pudo parsear salida JSON; se continua."
      return
    }

    $payload = $jsonLine | ConvertFrom-Json
    if (-not [bool]$payload.ok) {
      Write-Host "RetailHub updates: error en apply-on-start ($($payload.last_error))."
      return
    }
    if ([bool]$payload.applied) {
      Write-Host "RetailHub updates: aplicada una actualizacion en este inicio."
    } elseif ([bool]$payload.pending) {
      Write-Host "RetailHub updates: sigue habiendo update pendiente."
    } else {
      Write-Host "RetailHub updates: sin pendientes."
    }
  } catch {
    Write-Host "RetailHub updates: fallo apply-on-start ($($_.Exception.Message))."
  }
}

Push-Location $repoRoot
try {
  switch ($Action.ToLowerInvariant()) {
    "start" {
      Invoke-StartupUpdates
      Invoke-Compose -Args @("up", "-d")
    }
    "stop" {
      Invoke-Compose -Args @("stop")
    }
    "status" {
      Invoke-Compose -Args @("ps")
    }
    "restart" {
      Invoke-StartupUpdates
      Invoke-Compose -Args @("up", "-d", "--build")
    }
    default {
      throw "Accion no soportada: $Action"
    }
  }
} finally {
  Pop-Location
}
