[CmdletBinding()]
param(
    [string]$EnvFile = ".env.prod.internet",
    [string]$ComposeFile = "docker-compose.prod.internet.yml",
    [switch]$SkipPrecheck,
    [switch]$SkipBuild,
    [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Get-EnvMap([string]$Path) {
    $map = @{}
    foreach ($line in Get-Content -Path $Path) {
        $trim = $line.Trim()
        if (-not $trim) { continue }
        if ($trim.StartsWith("#")) { continue }
        $eq = $trim.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $trim.Substring(0, $eq).Trim()
        $value = $trim.Substring($eq + 1).Trim()
        $map[$key] = $value
    }
    return $map
}

function Ensure-FirewallRule([string]$Name, [int]$Port) {
    $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Info "Firewall rule existente: $Name"
        return
    }
    New-NetFirewallRule -DisplayName $Name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
    Write-Info "Firewall rule creada: $Name (TCP $Port)"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    if (-not $SkipPrecheck) {
        Write-Info "Ejecutando precheck..."
        & "$PSScriptRoot\vm_internet_precheck.ps1" -EnvFile $EnvFile -ComposeFile $ComposeFile
        if ($LASTEXITCODE -ne 0) {
            throw "Precheck con errores"
        }
    }

    if ($OpenFirewall) {
        Write-Info "Abriendo firewall local para 80/443..."
        Ensure-FirewallRule -Name "Equilux Reparaciones HTTP 80" -Port 80
        Ensure-FirewallRule -Name "Equilux Reparaciones HTTPS 443" -Port 443
    }

    $composeArgs = @("-f", $ComposeFile, "--env-file", $EnvFile)

    if ($SkipBuild) {
        Write-Info "Levantando stack sin build..."
        docker compose @composeArgs up -d
    } else {
        Write-Info "Levantando stack con build..."
        docker compose @composeArgs up -d --build
    }

    Write-Info "Estado de contenedores:"
    docker compose @composeArgs ps

    $envMap = Get-EnvMap -Path $EnvFile
    $publicDomain = $envMap["PUBLIC_DOMAIN"]
    if ($publicDomain) {
        Write-Info "URL esperada: https://$publicDomain"
        Write-Info "Health API esperado: https://$publicDomain/api/health"
    }

    Write-Info "Comando de logs (proxy): docker compose -f $ComposeFile --env-file $EnvFile logs -f reverse-proxy"
}
finally {
    Pop-Location
}
