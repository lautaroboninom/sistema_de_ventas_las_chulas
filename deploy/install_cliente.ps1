[CmdletBinding()]
param(
  [string]$InstallRoot = "C:\RetailHub",
  [string]$RepoUrl = "https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git",
  [string]$Branch = "main",
  [switch]$SkipWinget,
  [switch]$SkipTailscale,
  [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$script:RepoName = "sistema_de_ventas_las_chulas"
$script:RepoDir = Join-Path $script:InstallRoot $script:RepoName
$script:LogFile = $null
$script:GitExe = $null
$script:DockerExe = $null
$script:TailscaleExe = $null

function Write-Log {
  param(
    [string]$Message,
    [ValidateSet("INFO", "WARN", "ERROR")]
    [string]$Level = "INFO"
  )
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  $line = "[$ts][$Level] $Message"
  Write-Host $line
  if ($script:LogFile) {
    Add-Content -Path $script:LogFile -Value $line -Encoding UTF8
  }
}

function Initialize-Log {
  New-Item -ItemType Directory -Path $script:InstallRoot -Force | Out-Null
  $logDir = Join-Path $script:InstallRoot "logs"
  New-Item -ItemType Directory -Path $logDir -Force | Out-Null
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $script:LogFile = Join-Path $logDir "install_$stamp.log"
  New-Item -ItemType File -Path $script:LogFile -Force | Out-Null
}

function Assert-Windows {
  if ($env:OS -ne "Windows_NT") {
    throw "Este instalador solo soporta Windows 10/11."
  }
}

function Test-IsAdmin {
  $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Assert-Admin {
  if (-not (Test-IsAdmin)) {
    throw "Ejecuta este script como Administrador."
  }
}

function Assert-Internet {
  try {
    Invoke-WebRequest -Uri "https://www.msftconnecttest.com/connecttest.txt" -UseBasicParsing -TimeoutSec 15 | Out-Null
  } catch {
    throw "No hay conectividad a Internet. Verifica red/proxy y reintenta."
  }
}

function Warn-VirtualizationState {
  $warned = $false
  try {
    $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if ($wsl) {
      $out = & $wsl.Source --status 2>&1
      if ($LASTEXITCODE -ne 0) {
        Write-Log "WSL2 no parece listo. Docker Desktop puede requerir configuracion manual." "WARN"
        $warned = $true
      } elseif ($out -is [string] -and $out -match "Default Version:\s*1") {
        Write-Log "WSL default version es 1. Docker Desktop recomienda WSL2." "WARN"
        $warned = $true
      }
    } else {
      Write-Log "No se encontro wsl.exe. Si Docker falla, habilita WSL2 y Virtual Machine Platform." "WARN"
      $warned = $true
    }
  } catch {
    Write-Log "No se pudo validar estado de WSL2/virtualizacion." "WARN"
    $warned = $true
  }

  if (-not $warned) {
    Write-Log "Chequeo WSL2/virtualizacion completado."
  }
}

function Assert-Winget {
  if ($SkipWinget) {
    return
  }
  $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "winget no esta disponible. Instala App Installer (Microsoft Store) y reintenta."
  }
}

function Install-WingetPackage {
  param(
    [string]$PackageId,
    [string]$Label
  )
  Write-Log "Instalando/actualizando $Label ($PackageId) con winget..."
  & winget.exe install --id $PackageId --exact --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
  if ($LASTEXITCODE -ne 0) {
    throw "winget fallo al instalar/actualizar $PackageId."
  }
}

function Resolve-Tool {
  param(
    [string]$CommandName,
    [string[]]$FallbackPaths
  )
  $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }
  foreach ($path in $FallbackPaths) {
    if (Test-Path $path) {
      return $path
    }
  }
  return $null
}

function Ensure-Dependencies {
  if (-not $SkipWinget) {
    Install-WingetPackage -PackageId "Git.Git" -Label "Git"
    Install-WingetPackage -PackageId "Docker.DockerDesktop" -Label "Docker Desktop"
    Install-WingetPackage -PackageId "Tailscale.Tailscale" -Label "Tailscale"
  } else {
    Write-Log "SkipWinget activo: se omite instalacion de dependencias." "WARN"
  }

  $script:GitExe = Resolve-Tool -CommandName "git.exe" -FallbackPaths @(
    "$env:ProgramFiles\Git\cmd\git.exe",
    "$env:ProgramFiles\Git\bin\git.exe"
  )
  if (-not $script:GitExe) {
    throw "No se encontro git.exe en PATH ni en rutas tipicas."
  }

  $script:DockerExe = Resolve-Tool -CommandName "docker.exe" -FallbackPaths @(
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
    "$env:ProgramFiles\Docker\Docker\resources\docker.exe"
  )
  if (-not $script:DockerExe) {
    throw "No se encontro docker.exe en PATH ni en rutas tipicas."
  }

  if (-not $SkipTailscale) {
    $script:TailscaleExe = Resolve-Tool -CommandName "tailscale.exe" -FallbackPaths @(
      "$env:ProgramFiles\Tailscale\tailscale.exe"
    )
    if (-not $script:TailscaleExe) {
      throw "No se encontro tailscale.exe en PATH ni en rutas tipicas."
    }
  }
}

function Ensure-DockerReady {
  & $script:DockerExe info *> $null
  if ($LASTEXITCODE -eq 0) {
    Write-Log "Docker daemon disponible."
    return
  }

  $dockerDesktop = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerDesktop) {
    Write-Log "Iniciando Docker Desktop..."
    Start-Process -FilePath $dockerDesktop | Out-Null
  } else {
    Write-Log "No se encontro Docker Desktop.exe. Intentando esperar daemon igualmente." "WARN"
  }

  $timeoutSec = 600
  $stepSec = 5
  $elapsed = 0
  while ($elapsed -lt $timeoutSec) {
    Start-Sleep -Seconds $stepSec
    & $script:DockerExe info *> $null
    if ($LASTEXITCODE -eq 0) {
      Write-Log "Docker daemon listo."
      return
    }
    $elapsed += $stepSec
    if (($elapsed % 30) -eq 0) {
      Write-Log "Esperando Docker daemon... ($elapsed/$timeoutSec segundos)"
    }
  }

  throw "Docker daemon no quedo listo en $timeoutSec segundos. Abre Docker Desktop y reintenta."
}

function Ensure-Repository {
  New-Item -ItemType Directory -Path $script:InstallRoot -Force | Out-Null

  $gitDir = Join-Path $script:RepoDir ".git"
  if (Test-Path $gitDir) {
    Write-Log "Repositorio existente detectado. Actualizando rama $Branch..."
    & $script:GitExe -C $script:RepoDir fetch --all --prune
    if ($LASTEXITCODE -ne 0) { throw "Fallo git fetch." }
    & $script:GitExe -C $script:RepoDir checkout $Branch
    if ($LASTEXITCODE -ne 0) { throw "Fallo git checkout $Branch." }
    & $script:GitExe -C $script:RepoDir pull --ff-only origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "Fallo git pull origin $Branch." }
  } elseif (Test-Path $script:RepoDir) {
    throw "La carpeta $script:RepoDir existe pero no es un repositorio Git. Renombrala o borra su contenido."
  } else {
    Write-Log "Clonando repositorio en $script:RepoDir..."
    & $script:GitExe clone --branch $Branch --single-branch $RepoUrl $script:RepoDir
    if ($LASTEXITCODE -ne 0) { throw "Fallo git clone." }
  }

  & $script:GitExe config --global --add safe.directory $script:RepoDir
  if ($LASTEXITCODE -ne 0) {
    Write-Log "No se pudo registrar safe.directory. Continuando..." "WARN"
  }
}

function Read-EnvMap {
  param([string]$Path)
  $map = @{}
  if (-not (Test-Path $Path)) {
    return $map
  }
  foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $trim = $line.Trim()
    if ($trim.StartsWith("#")) { continue }
    if (-not $line.Contains("=")) { continue }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1]
    $map[$key] = $value
  }
  return $map
}

function Write-EnvFilePreserveLines {
  param(
    [string]$Path,
    [hashtable]$Values
  )
  $existing = @()
  if (Test-Path $Path) {
    $existing = Get-Content -Path $Path -Encoding UTF8
  }

  $seen = @{}
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($line in $existing) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#") -or -not $line.Contains("=")) {
      $out.Add($line)
      continue
    }
    $parts = $line.Split("=", 2)
    $key = $parts[0].Trim()
    if ($Values.ContainsKey($key)) {
      $out.Add("$key=$($Values[$key])")
      $seen[$key] = $true
    } else {
      $out.Add($line)
    }
  }

  foreach ($key in ($Values.Keys | Sort-Object)) {
    if (-not $seen.ContainsKey($key)) {
      $out.Add("$key=$($Values[$key])")
    }
  }

  Set-Content -Path $Path -Value $out -Encoding UTF8
  Add-Content -Path $Path -Value ""
}

function New-UrlSafeSecret {
  param([int]$Bytes = 48)
  $arr = New-Object byte[] $Bytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($arr)
  $rng.Dispose()
  return [Convert]::ToBase64String($arr).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Test-WeakSecret {
  param(
    [string]$Value,
    [int]$MinLen
  )
  $raw = (($Value | Out-String).Trim())
  $low = $raw.ToLowerInvariant()
  $weakValues = @(
    "",
    "change-me",
    "changeme",
    "default",
    "replace_with_strong_secret",
    "replace-with-strong-secret",
    "replace_with_strong_db_password",
    "replace-with-strong-db-password"
  )
  if ($weakValues -contains $low) { return $true }
  if ($low.Contains("replace") -or $low.Contains("changeme")) { return $true }
  if ($raw.Length -lt $MinLen) { return $true }
  return $false
}

function Read-PlainTextFromSecure {
  param([System.Security.SecureString]$SecureValue)
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Prompt-Value {
  param(
    [string]$Label,
    [string]$CurrentValue = "",
    [switch]$Required,
    [switch]$Secret
  )

  if ($NonInteractive) {
    return $CurrentValue
  }

  while ($true) {
    if ($Secret) {
      $promptText = if ([string]::IsNullOrWhiteSpace($CurrentValue)) { $Label } else { "$Label (Enter para mantener actual)" }
      $secure = Read-Host -Prompt $promptText -AsSecureString
      $plain = (Read-PlainTextFromSecure -SecureValue $secure).Trim()
      if ([string]::IsNullOrWhiteSpace($plain)) {
        if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) { return $CurrentValue }
        if ($Required) {
          Write-Host "Valor obligatorio."
          continue
        }
        return ""
      }
      return $plain
    }

    $display = if ([string]::IsNullOrWhiteSpace($CurrentValue)) { "" } else { " [$CurrentValue]" }
    $input = Read-Host -Prompt "$Label$display"
    $trimmed = $input.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
      if (-not [string]::IsNullOrWhiteSpace($CurrentValue)) { return $CurrentValue }
      if ($Required) {
        Write-Host "Valor obligatorio."
        continue
      }
      return ""
    }
    return $trimmed
  }
}

function Protect-EnvFileAcl {
  param([string]$Path)

  $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  & icacls.exe $Path /inheritance:r /grant:r "${identity}:(M)" "Administrators:(F)" "SYSTEM:(F)" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Log "No se pudo aplicar ACL restrictiva a $Path. Revisalo manualmente." "WARN"
  }
}

function Ensure-EnvProd {
  $templatePath = Join-Path $script:RepoDir ".env.prod.example"
  $envPath = Join-Path $script:RepoDir ".env.prod"

  if (-not (Test-Path $templatePath)) {
    throw "No se encontro .env.prod.example en $script:RepoDir."
  }
  if (-not (Test-Path $envPath)) {
    Copy-Item -Path $templatePath -Destination $envPath -Force
    Write-Log "Se creo .env.prod desde .env.prod.example."
  }

  $map = Read-EnvMap -Path $envPath

  $publicHost = Prompt-Value -Label "PUBLIC_HOST (dns ts.net de esta PC)" -CurrentValue ($map["PUBLIC_HOST"]) -Required
  if ([string]::IsNullOrWhiteSpace($publicHost)) {
    throw "PUBLIC_HOST es obligatorio."
  }

  $tiendaClientId = Prompt-Value -Label "TIENDANUBE_CLIENT_ID (opcional por ahora)" -CurrentValue ($map["TIENDANUBE_CLIENT_ID"])
  $tiendaClientSecret = Prompt-Value -Label "TIENDANUBE_CLIENT_SECRET (opcional por ahora)" -CurrentValue ($map["TIENDANUBE_CLIENT_SECRET"]) -Secret
  $tiendaStoreId = Prompt-Value -Label "TIENDANUBE_STORE_ID (opcional por ahora)" -CurrentValue ($map["TIENDANUBE_STORE_ID"])
  $tiendaAccessToken = Prompt-Value -Label "TIENDANUBE_ACCESS_TOKEN (opcional por ahora)" -CurrentValue ($map["TIENDANUBE_ACCESS_TOKEN"]) -Secret
  $tiendaWebhookSecret = Prompt-Value -Label "TIENDANUBE_WEBHOOK_SECRET (opcional, Enter para heredar client secret)" -CurrentValue ($map["TIENDANUBE_WEBHOOK_SECRET"]) -Secret

  if ([string]::IsNullOrWhiteSpace($tiendaWebhookSecret) -and -not [string]::IsNullOrWhiteSpace($tiendaClientSecret)) {
    $tiendaWebhookSecret = $tiendaClientSecret
  }

  $arcaCuit = Prompt-Value -Label "ARCA_CUIT (opcional)" -CurrentValue ($map["ARCA_CUIT"])
  $arcaCertPath = Prompt-Value -Label "ARCA_CERT_PATH (opcional, fuera del repo)" -CurrentValue ($map["ARCA_CERT_PATH"])
  $arcaKeyPath = Prompt-Value -Label "ARCA_KEY_PATH (opcional, fuera del repo)" -CurrentValue ($map["ARCA_KEY_PATH"])

  if (Test-WeakSecret -Value ($map["DJANGO_SECRET_KEY"]) -MinLen 40) {
    $map["DJANGO_SECRET_KEY"] = New-UrlSafeSecret
    Write-Log "DJANGO_SECRET_KEY generado automaticamente."
  }
  if (Test-WeakSecret -Value ($map["JWT_SECRET"]) -MinLen 40) {
    $map["JWT_SECRET"] = New-UrlSafeSecret
    Write-Log "JWT_SECRET generado automaticamente."
  }
  if (Test-WeakSecret -Value ($map["POSTGRES_PASSWORD"]) -MinLen 20) {
    $map["POSTGRES_PASSWORD"] = New-UrlSafeSecret
    Write-Log "POSTGRES_PASSWORD generado automaticamente."
  }

  $map["PUBLIC_HOST"] = $publicHost
  $map["DJANGO_ALLOWED_HOSTS"] = $publicHost
  $map["ALLOWED_ORIGINS"] = "https://$publicHost:8443,https://$publicHost"
  $map["FRONTEND_ORIGIN"] = "https://$publicHost:8443"
  $map["PUBLIC_WEB_URL"] = "https://$publicHost"

  $map["TIENDANUBE_CLIENT_ID"] = $tiendaClientId
  $map["TIENDANUBE_CLIENT_SECRET"] = $tiendaClientSecret
  $map["TIENDANUBE_STORE_ID"] = $tiendaStoreId
  $map["TIENDANUBE_ACCESS_TOKEN"] = $tiendaAccessToken
  $map["TIENDANUBE_WEBHOOK_SECRET"] = $tiendaWebhookSecret

  $map["ARCA_CUIT"] = $arcaCuit
  $map["ARCA_CERT_PATH"] = $arcaCertPath
  $map["ARCA_KEY_PATH"] = $arcaKeyPath

  if ($NonInteractive) {
    if ([string]::IsNullOrWhiteSpace($map["PUBLIC_HOST"])) {
      throw "En modo -NonInteractive, PUBLIC_HOST debe estar completo en .env.prod."
    }
  }

  Write-EnvFilePreserveLines -Path $envPath -Values $map
  Protect-EnvFileAcl -Path $envPath
  Write-Log ".env.prod actualizado y protegido."

  return @{
    EnvPath = $envPath
    PublicHost = $publicHost
  }
}

function Ensure-DockerVolume {
  param([string]$Name)

  & $script:DockerExe volume inspect $Name *> $null
  if ($LASTEXITCODE -eq 0) { return }

  Write-Log "Creando volumen Docker $Name..."
  & $script:DockerExe volume create $Name *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "No se pudo crear el volumen Docker $Name."
  }
}

function Wait-ContainerReady {
  param(
    [string]$ContainerName,
    [bool]$RequireHealthy = $true,
    [int]$TimeoutSec = 420
  )

  $stepSec = 5
  $elapsed = 0
  while ($elapsed -lt $TimeoutSec) {
    $raw = & $script:DockerExe inspect --format "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}" $ContainerName 2>$null
    if ($LASTEXITCODE -eq 0 -and $raw) {
      $parts = $raw -split "\|", 2
      $status = $parts[0]
      $health = if ($parts.Count -gt 1) { $parts[1] } else { "" }

      if ($RequireHealthy) {
        if ($status -eq "running" -and $health -eq "healthy") {
          Write-Log "$ContainerName listo (running/healthy)."
          return
        }
      } else {
        if ($status -eq "running") {
          Write-Log "$ContainerName listo (running)."
          return
        }
      }
    }
    Start-Sleep -Seconds $stepSec
    $elapsed += $stepSec
  }

  throw "Timeout esperando contenedor $ContainerName."
}

function Start-ProdStack {
  Ensure-DockerVolume -Name "laschulas_pg_data"
  Ensure-DockerVolume -Name "laschulas_staticfiles"
  Ensure-DockerVolume -Name "laschulas_mediafiles"

  Write-Log "Levantando stack productivo..."
  Push-Location $script:RepoDir
  try {
    & $script:DockerExe compose -f docker-compose.prod.yml up -d --build
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose up -d --build fallo."
    }
  } finally {
    Pop-Location
  }

  Wait-ContainerReady -ContainerName "retailhub-postgres" -RequireHealthy $true -TimeoutSec 420
  Wait-ContainerReady -ContainerName "retailhub-redis" -RequireHealthy $true -TimeoutSec 420
  Wait-ContainerReady -ContainerName "retailhub-api" -RequireHealthy $true -TimeoutSec 480
  Wait-ContainerReady -ContainerName "retailhub-web" -RequireHealthy $false -TimeoutSec 240
  Wait-ContainerReady -ContainerName "retailhub-webhook-gateway" -RequireHealthy $false -TimeoutSec 240
}

function Ensure-TailscaleLogin {
  if ($SkipTailscale) {
    Write-Log "SkipTailscale activo: se omite configuracion Tailscale/Funnel." "WARN"
    return $null
  }

  $statusRaw = & $script:TailscaleExe status --json 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($statusRaw)) {
    Write-Log "Tailscale no esta autenticado. Ejecutando 'tailscale up' (interactivo)..."
    & $script:TailscaleExe up
    if ($LASTEXITCODE -ne 0) {
      throw "No se pudo completar tailscale up."
    }
    $statusRaw = & $script:TailscaleExe status --json 2>$null
    if ($LASTEXITCODE -ne 0) {
      throw "No se pudo leer estado de Tailscale despues de login."
    }
  }

  $statusObj = $statusRaw | ConvertFrom-Json
  $dnsHost = [string]$statusObj.Self.DNSName
  $dnsHost = $dnsHost.Trim().TrimEnd(".")
  if ([string]::IsNullOrWhiteSpace($dnsHost)) {
    throw "No se pudo obtener DNSName de Tailscale."
  }

  return $dnsHost
}

function Configure-TailscaleExposure {
  if ($SkipTailscale) {
    return
  }

  Write-Log "Configurando Tailscale Serve privado (admin en :8443)..."
  & $script:TailscaleExe serve --bg --https=8443 http://127.0.0.1:80
  if ($LASTEXITCODE -ne 0) {
    throw "Fallo tailscale serve para admin privado."
  }

  Write-Log "Configurando Tailscale Funnel publico (solo webhook gateway en :443)..."
  & $script:TailscaleExe funnel --bg --https=443 http://127.0.0.1:8080
  if ($LASTEXITCODE -ne 0) {
    throw "Fallo tailscale funnel para webhook publico. Verifica que Funnel este habilitado en tu cuenta."
  }
}

function Get-HttpStatusCode {
  param(
    [string]$Url,
    [string]$Method = "GET"
  )
  $code = & curl.exe -s -o NUL -w "%{http_code}" -X $Method $Url
  if ($LASTEXITCODE -ne 0) { return "000" }
  return [string]$code
}

function Validate-Exposure {
  param([string]$DnsHost)

  if ([string]::IsNullOrWhiteSpace($DnsHost)) {
    Write-Log "No hay DNS host de Tailscale para validar exposicion." "WARN"
    return
  }

  $publicRoot = Get-HttpStatusCode -Url "https://$DnsHost/"
  if ($publicRoot -ne "404") {
    throw "La raiz publica devolvio $publicRoot (esperado 404 en modo seguro)."
  } else {
    Write-Log "Validacion OK: raiz publica devuelve 404."
  }

  $webhookStatus = Get-HttpStatusCode -Url "https://$DnsHost/api/retail/online/webhooks/orden-pagada/" -Method "POST"
  if ($webhookStatus -eq "404" -or $webhookStatus -eq "000") {
    throw "Webhook publico no accesible (status $webhookStatus)."
  }
  Write-Log "Validacion OK: webhook publico responde status $webhookStatus."

  $adminStatus = Get-HttpStatusCode -Url "https://$DnsHost:8443/login"
  if (@("200", "301", "302", "307", "308") -notcontains $adminStatus) {
    throw "URL admin privada no valida (status $adminStatus). Revisa tailscale serve en :8443."
  }
  Write-Log "Validacion URL admin privada status $adminStatus."
}

function Register-StartupTask {
  $taskName = "RetailHub-Start"
  $controlScript = Join-Path $script:RepoDir "deploy\retailhub_service.ps1"
  if (-not (Test-Path $controlScript)) {
    throw "No existe script de control: $controlScript"
  }

  $psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$controlScript`" -Action start -InstallRoot `"$script:InstallRoot`""
  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs
  $trigger = New-ScheduledTaskTrigger -AtStartup
  $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  Write-Log "Tarea programada creada/actualizada: $taskName"
}

function Show-PostInstallChecklist {
  param(
    [string]$DnsHost,
    [string]$PublicHost
  )

  $hostForSummary = if ([string]::IsNullOrWhiteSpace($DnsHost)) { $PublicHost } else { $DnsHost }

  Write-Host ""
  Write-Host "================= INSTALACION COMPLETADA ================="
  Write-Host "Log: $script:LogFile"
  Write-Host ""
  Write-Host "Admin privado (tailnet): https://$hostForSummary`:8443"
  Write-Host "Webhook publico:         https://$hostForSummary/api/retail/online/webhooks/orden-pagada/"
  Write-Host ""
  Write-Host "Checklist inmediato:"
  Write-Host "1) Cargar webhooks de Tienda Nube apuntando al host publico."
  Write-Host "2) Probar orden pagada y orden cancelada."
  Write-Host "3) Verificar login, compras, ventas y reportes."
  Write-Host "4) Rotar secretos expuestos antes de salida productiva final."
  Write-Host "==========================================================="
  Write-Host ""
}

try {
  Assert-Windows
  Assert-Admin
  Initialize-Log

  Write-Log "Inicio instalacion automatizada RetailHub cliente unico."
  Write-Log "InstallRoot: $script:InstallRoot"
  Write-Log "RepoUrl: $RepoUrl"
  Write-Log "Branch: $Branch"
  Write-Log "Flags: SkipWinget=$SkipWinget SkipTailscale=$SkipTailscale NonInteractive=$NonInteractive"

  Assert-Internet
  Assert-Winget
  Warn-VirtualizationState
  Ensure-Dependencies
  Ensure-DockerReady
  Ensure-Repository
  $envCfg = Ensure-EnvProd
  Start-ProdStack

  $dnsHost = $null
  if (-not $SkipTailscale) {
    $dnsHost = Ensure-TailscaleLogin
    Configure-TailscaleExposure
    Validate-Exposure -DnsHost $dnsHost
  }

  Register-StartupTask
  Show-PostInstallChecklist -DnsHost $dnsHost -PublicHost $envCfg.PublicHost
  Write-Log "Instalacion finalizada correctamente."
  exit 0
} catch {
  $msg = $_.Exception.Message
  if (-not $msg) {
    $msg = "Error no controlado."
  }
  Write-Log $msg "ERROR"
  Write-Host ""
  Write-Host "Instalacion fallida. Revisar log: $script:LogFile" -ForegroundColor Red
  exit 1
}
