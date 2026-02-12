[CmdletBinding()]
param(
    [string]$EnvFile = ".env.prod.internet",
    [string]$ComposeFile = "docker-compose.prod.internet.yml",
    [switch]$SkipDns
)

$ErrorActionPreference = "Stop"
$script:hasErrors = $false

function Write-Info([string]$Message) {
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-WarnMsg([string]$Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg([string]$Message) {
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    $script:hasErrors = $true
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

function Normalize-Url([string]$Url) {
    if (-not $Url) { return "" }
    return $Url.Trim().TrimEnd("/")
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Info "Precheck de despliegue internet para VM"

    if (-not (Test-Path -Path $ComposeFile)) {
        Write-ErrorMsg "No existe $ComposeFile"
    }
    if (-not (Test-Path -Path $EnvFile)) {
        Write-ErrorMsg "No existe $EnvFile"
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-ErrorMsg "Docker CLI no esta instalado o no esta en PATH"
    } else {
        try {
            $null = docker compose version
            Write-Info "Docker Compose detectado"
        } catch {
            Write-ErrorMsg "Docker Compose v2 no disponible: $($_.Exception.Message)"
        }
    }

    if (-not $script:hasErrors) {
        $envMap = Get-EnvMap -Path $EnvFile

        $requiredKeys = @(
            "PUBLIC_DOMAIN",
            "DJANGO_ALLOWED_HOSTS",
            "ALLOWED_ORIGINS",
            "FRONTEND_ORIGIN",
            "PUBLIC_WEB_URL",
            "VITE_API_URL",
            "TRAEFIK_ACME_EMAIL"
        )
        foreach ($key in $requiredKeys) {
            if (-not $envMap.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envMap[$key])) {
                Write-ErrorMsg "Falta variable requerida en ${EnvFile}: $key"
            }
        }

        $domain = ($envMap["PUBLIC_DOMAIN"] | ForEach-Object { $_.Trim().ToLowerInvariant() })
        if (-not $domain) {
            Write-ErrorMsg "PUBLIC_DOMAIN vacio"
        } elseif ($domain -notmatch "\.") {
            Write-ErrorMsg "PUBLIC_DOMAIN debe ser FQDN (ej: reparaciones.equiluxmd.com)"
        }

        if ($domain) {
            $expectedSiteUrl = "https://$domain"
            $expectedApiUrl = "https://$domain/api"

            $allowedHosts = ($envMap["DJANGO_ALLOWED_HOSTS"] | ForEach-Object { $_.ToLowerInvariant() })
            if ($allowedHosts -notmatch [Regex]::Escape($domain)) {
                Write-ErrorMsg "DJANGO_ALLOWED_HOSTS no incluye $domain"
            }

            $allowedOrigins = Normalize-Url $envMap["ALLOWED_ORIGINS"]
            if ($allowedOrigins -notmatch [Regex]::Escape($expectedSiteUrl)) {
                Write-ErrorMsg "ALLOWED_ORIGINS debe incluir $expectedSiteUrl"
            }

            $frontendOrigin = Normalize-Url $envMap["FRONTEND_ORIGIN"]
            if ($frontendOrigin -ne $expectedSiteUrl) {
                Write-ErrorMsg "FRONTEND_ORIGIN debe ser $expectedSiteUrl"
            }

            $publicWebUrl = Normalize-Url $envMap["PUBLIC_WEB_URL"]
            if ($publicWebUrl -ne $expectedSiteUrl) {
                Write-ErrorMsg "PUBLIC_WEB_URL debe ser $expectedSiteUrl"
            }

            $viteApiUrl = Normalize-Url $envMap["VITE_API_URL"]
            if ($viteApiUrl -ne $expectedApiUrl) {
                Write-ErrorMsg "VITE_API_URL debe ser $expectedApiUrl"
            }
        }

        foreach ($port in @(80, 443)) {
            try {
                $listeners = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
                if ($listeners) {
                    $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
                    $procNames = @()
                    foreach ($procId in $pids) {
                        $name = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
                        if ($name) { $procNames += "$name($procId)" } else { $procNames += "PID:$procId" }
                    }
                    Write-WarnMsg "Puerto $port ocupado por: $($procNames -join ', ')"
                } else {
                    Write-Info "Puerto $port libre"
                }
            } catch {
                Write-WarnMsg "No se pudo verificar puerto ${port}: $($_.Exception.Message)"
            }
        }

        if (-not $SkipDns -and $domain) {
            $publicIp = $null
            try {
                $publicIp = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json" -TimeoutSec 8).ip
                Write-Info "IP publica detectada: $publicIp"
            } catch {
                Write-WarnMsg "No se pudo obtener IP publica automaticamente"
            }

            $resolvedIps = @()
            try {
                $resolvedIps = Resolve-DnsName -Name $domain -Type A -ErrorAction Stop |
                    Select-Object -ExpandProperty IPAddress -Unique
            } catch {
                Write-ErrorMsg "No se pudo resolver DNS A de $domain"
            }

            if ($resolvedIps.Count -gt 0) {
                Write-Info "DNS A de $domain => $($resolvedIps -join ', ')"
            }
            if ($publicIp -and $resolvedIps.Count -gt 0 -and ($resolvedIps -notcontains $publicIp)) {
                Write-WarnMsg "El DNS no apunta a la IP publica actual de esta VM/host. Revisar NAT/DNS si corresponde."
            }
        }
    }

    $acmeDir = Join-Path $repoRoot "deploy\traefik"
    $acmeFile = Join-Path $acmeDir "acme.json"
    if (-not (Test-Path -Path $acmeDir)) {
        New-Item -ItemType Directory -Path $acmeDir | Out-Null
    }
    if (-not (Test-Path -Path $acmeFile)) {
        "" | Set-Content -Path $acmeFile -Encoding ascii
        Write-Info "Creado $acmeFile"
    }

    if ($script:hasErrors) {
        Write-ErrorMsg "Precheck finalizado con errores"
        exit 1
    }

    Write-Info "Precheck OK"
    exit 0
}
finally {
    Pop-Location
}
