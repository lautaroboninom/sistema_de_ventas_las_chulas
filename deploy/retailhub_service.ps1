[CmdletBinding()]
param(
  [ValidateSet("start", "stop", "status", "restart")]
  [string]$Action = "status",
  [string]$InstallRoot = "C:\RetailHub"
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

Push-Location $repoRoot
try {
  switch ($Action.ToLowerInvariant()) {
    "start" {
      Invoke-Compose -Args @("up", "-d")
    }
    "stop" {
      Invoke-Compose -Args @("stop")
    }
    "status" {
      Invoke-Compose -Args @("ps")
    }
    "restart" {
      Invoke-Compose -Args @("up", "-d", "--build")
    }
    default {
      throw "Accion no soportada: $Action"
    }
  }
} finally {
  Pop-Location
}
