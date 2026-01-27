#powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\sync_repuestos_costos.ps1 PARA SINCRONZIAR

param(
    [string]$Source = "Z:\MG BIO\LISTA DE PRECIOS DE MGBIO\COSTOS VIGENTES.xlsx",
    [string]$TargetDir = "C:\repuestos_costos",
    [string]$TargetFile = "",
    [string]$EnvFile = "",
    [string]$DbHost = "",
    [string]$DbPort = "",
    [string]$DbName = "",
    [string]$DbUser = "",
    [string]$DbPassword = ""
)

function Read-EnvFile {
    param([string]$Path)
    $map = @{}
    if (-not (Test-Path -LiteralPath $Path)) { return $map }
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }
        $parts = $line -split "=", 2
        if ($parts.Length -lt 2) { return }
        $key = $parts[0].Trim()
        $val = $parts[1]
        if ($key) { $map[$key] = $val }
    }
    return $map
}

function Pick-Value {
    param(
        [string]$ParamValue,
        [string]$EnvKey,
        [string]$Fallback,
        [hashtable]$EnvMap
    )
    if ($ParamValue) { return $ParamValue }
    $fromEnv = [Environment]::GetEnvironmentVariable($EnvKey)
    if ($fromEnv) { return $fromEnv }
    if ($EnvMap.ContainsKey($EnvKey) -and $EnvMap[$EnvKey]) { return $EnvMap[$EnvKey] }
    return $Fallback
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

if (-not $EnvFile) {
    $envProd = Join-Path $repoRoot ".env.prod"
    $envLocal = Join-Path $repoRoot ".env"
    if (Test-Path -LiteralPath $envProd) {
        $EnvFile = $envProd
    } elseif (Test-Path -LiteralPath $envLocal) {
        $EnvFile = $envLocal
    }
}

$envMap = Read-EnvFile $EnvFile

$DbHost = Pick-Value $DbHost "POSTGRES_HOST" "localhost" $envMap
if ($DbHost -eq "postgres") { $DbHost = "localhost" }
$DbPort = Pick-Value $DbPort "POSTGRES_PORT" "5432" $envMap
$DbName = Pick-Value $DbName "POSTGRES_DB" "servicio_tecnico" $envMap
$DbUser = Pick-Value $DbUser "POSTGRES_USER" "sepid" $envMap
$DbPassword = Pick-Value $DbPassword "POSTGRES_PASSWORD" "" $envMap

if (-not $TargetFile) {
    $TargetFile = Join-Path $TargetDir "COSTOS VIGENTES.xlsx"
}

try {
    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Error "Source file not found: $Source"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $TargetFile -Force
    Write-Output "Updated repuestos file: $TargetFile"
} catch {
    Write-Error ("Error copying repuestos file: " + $_.Exception.Message)
    exit 1
}

try {
    $apiDir = Join-Path $repoRoot "api"
    $managePy = Join-Path $apiDir "manage.py"
    if (-not (Test-Path -LiteralPath $managePy)) {
        Write-Error "manage.py not found: $managePy"
        exit 1
    }

    $env:POSTGRES_HOST = $DbHost
    $env:POSTGRES_PORT = $DbPort
    $env:POSTGRES_DB = $DbName
    $env:POSTGRES_USER = $DbUser
    if ($DbPassword) { $env:POSTGRES_PASSWORD = $DbPassword }
    $env:REPUESTOS_COSTOS_FILE = $TargetFile

    $old = Get-Location
    Set-Location $apiDir
    $exitCode = 0
    try {
        & python $managePy sync_repuestos_catalogo
        $exitCode = $LASTEXITCODE
    } finally {
        Set-Location $old
    }
    if ($exitCode -ne 0) { exit $exitCode }
} catch {
    Write-Error ("Error running sync_repuestos_catalogo: " + $_.Exception.Message)
    exit 1
}
