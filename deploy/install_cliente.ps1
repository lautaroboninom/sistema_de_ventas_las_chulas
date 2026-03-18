[CmdletBinding()]
param(
  [string]$InstallRoot = "C:\RetailHub",
  [string]$RepoUrl = "https://github.com/lautaroboninom/sistema_de_ventas_las_chulas.git",
  [string]$Branch = "main",
  [string]$ExpectedPublicHost = "retailhub.taila1413b.ts.net",
  [switch]$SkipWinget,
  [switch]$SkipTailscale,
  [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$script:RepoName = "sistema_de_ventas_las_chulas"
$script:RepoDir = Join-Path $script:InstallRoot $script:RepoName
$script:StateDir = Join-Path $script:InstallRoot "state"
$script:StateFile = Join-Path $script:StateDir "prod_stack_state.json"
$script:LogFile = $null
$script:GitExe = $null
$script:DockerExe = $null
$script:TailscaleExe = $null
$script:WingetAvailable = $false
$script:StepResults = New-Object System.Collections.Generic.List[object]
$script:PartialInstall = $false
$script:PartialReason = ""
$script:ActualDnsHost = ""
$script:ExpectedPublicHost = ([string]$ExpectedPublicHost).Trim()
$script:ExpectedPublicHost = $script:ExpectedPublicHost -replace '^\s*https?://', ''
$script:ExpectedPublicHost = $script:ExpectedPublicHost.Trim().TrimEnd("/")

if ([string]::IsNullOrWhiteSpace($script:ExpectedPublicHost)) {
  throw "ExpectedPublicHost es obligatorio."
}

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

function Add-StepResult {
  param(
    [string]$Step,
    [ValidateSet("SKIP", "RUN", "UPDATED", "BLOCKED", "FAIL")]
    [string]$Status,
    [string]$Message
  )

  $script:StepResults.Add([pscustomobject]@{
      Step = $Step
      Status = $Status
      Message = $Message
    }) | Out-Null

  $level = if ($Status -eq "FAIL") { "ERROR" } elseif ($Status -eq "BLOCKED") { "WARN" } else { "INFO" }
  Write-Log "[$Status] $Step - $Message" $level
}

function Mark-PartialInstall {
  param([string]$Reason)

  $script:PartialInstall = $true
  $script:PartialReason = $Reason
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

function Install-WingetPackage {
  param(
    [string]$PackageId,
    [string]$Label
  )

  Write-Log "Instalando $Label ($PackageId) con winget..."
  & winget.exe install --id $PackageId --exact --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
  if ($LASTEXITCODE -ne 0) {
    throw "winget fallo al instalar $PackageId."
  }
}

function Initialize-Winget {
  if ($SkipWinget) {
    Add-StepResult -Step "winget" -Status "SKIP" -Message "SkipWinget activo."
    return
  }

  $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
  if ($winget) {
    $script:WingetAvailable = $true
    Add-StepResult -Step "winget" -Status "SKIP" -Message "winget disponible."
    return
  }

  Write-Log "winget no disponible. Solo se podran reutilizar dependencias ya instaladas." "WARN"
}

function Ensure-Dependency {
  param(
    [string]$StepName,
    [string]$CommandName,
    [string[]]$FallbackPaths,
    [string]$PackageId,
    [string]$Label
  )

  $toolPath = Resolve-Tool -CommandName $CommandName -FallbackPaths $FallbackPaths
  if ($toolPath) {
    Add-StepResult -Step $StepName -Status "SKIP" -Message "$Label ya estaba disponible en $toolPath."
    return $toolPath
  }

  if ($SkipWinget) {
    throw "No se encontro $CommandName y SkipWinget esta activo."
  }
  if (-not $script:WingetAvailable) {
    throw "No se encontro $CommandName y winget no esta disponible para instalarlo."
  }

  Install-WingetPackage -PackageId $PackageId -Label $Label
  $toolPath = Resolve-Tool -CommandName $CommandName -FallbackPaths $FallbackPaths
  if (-not $toolPath) {
    throw "No se encontro $CommandName despues de instalar $Label."
  }

  Add-StepResult -Step $StepName -Status "RUN" -Message "$Label instalado en $toolPath."
  return $toolPath
}

function Ensure-Dependencies {
  $script:GitExe = Ensure-Dependency -StepName "Git" -CommandName "git.exe" -FallbackPaths @(
    "$env:ProgramFiles\Git\cmd\git.exe",
    "$env:ProgramFiles\Git\bin\git.exe",
    "$env:LocalAppData\Programs\Git\cmd\git.exe"
  ) -PackageId "Git.Git" -Label "Git"

  $script:DockerExe = Ensure-Dependency -StepName "Docker" -CommandName "docker.exe" -FallbackPaths @(
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
    "$env:ProgramFiles\Docker\Docker\resources\docker.exe"
  ) -PackageId "Docker.DockerDesktop" -Label "Docker Desktop"

  if ($SkipTailscale) {
    Add-StepResult -Step "Tailscale" -Status "SKIP" -Message "SkipTailscale activo."
  } else {
    $script:TailscaleExe = Ensure-Dependency -StepName "Tailscale" -CommandName "tailscale.exe" -FallbackPaths @(
      "$env:ProgramFiles\Tailscale\tailscale.exe"
    ) -PackageId "Tailscale.Tailscale" -Label "Tailscale"
  }

  if (-not $SkipWinget -and -not $script:WingetAvailable) {
    Add-StepResult -Step "winget" -Status "SKIP" -Message "winget no estaba disponible, pero no hizo falta instalar dependencias."
  }
}

function Ensure-DockerReady {
  & $script:DockerExe info *> $null
  if ($LASTEXITCODE -eq 0) {
    Add-StepResult -Step "Docker daemon" -Status "SKIP" -Message "Docker daemon ya estaba disponible."
    return
  }

  $dockerDesktop = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerDesktop) {
    Write-Log "Iniciando Docker Desktop..."
    Start-Process -FilePath $dockerDesktop | Out-Null
  } else {
    Write-Log "No se encontro Docker Desktop.exe. Se esperara el daemon igualmente." "WARN"
  }

  $timeoutSec = 600
  $stepSec = 5
  $elapsed = 0
  while ($elapsed -lt $timeoutSec) {
    Start-Sleep -Seconds $stepSec
    & $script:DockerExe info *> $null
    if ($LASTEXITCODE -eq 0) {
      Add-StepResult -Step "Docker daemon" -Status "RUN" -Message "Docker daemon quedo disponible."
      return
    }
    $elapsed += $stepSec
    if (($elapsed % 30) -eq 0) {
      Write-Log "Esperando Docker daemon... ($elapsed/$timeoutSec segundos)"
    }
  }

  throw "Docker daemon no quedo listo en $timeoutSec segundos. Abre Docker Desktop y reintenta."
}

function Normalize-RepoUrl {
  param([string]$Url)

  $value = (($Url | Out-String).Trim()).TrimEnd("/")
  if ($value.ToLowerInvariant().EndsWith(".git")) {
    $value = $value.Substring(0, $value.Length - 4)
  }
  return $value.ToLowerInvariant()
}

function Test-RepoFilesPresent {
  param([string]$RootPath)

  $required = @(
    "docker-compose.prod.yml",
    ".env.prod.example",
    "deploy\install_cliente.ps1",
    "deploy\retailhub_service.ps1"
  )

  foreach ($relative in $required) {
    if (-not (Test-Path (Join-Path $RootPath $relative))) {
      return $false
    }
  }

  return $true
}

function Get-RepoCommitMarker {
  if (-not (Test-Path (Join-Path $script:RepoDir ".git"))) {
    return "local-copy"
  }

  $raw = & $script:GitExe -C $script:RepoDir rev-parse HEAD 2>$null
  if ($LASTEXITCODE -ne 0) {
    return "git-unknown"
  }

  return (($raw | Out-String).Trim())
}

function Register-SafeDirectory {
  if (-not (Test-Path (Join-Path $script:RepoDir ".git"))) {
    return
  }

  & $script:GitExe config --global --add safe.directory $script:RepoDir 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Log "No se pudo registrar safe.directory para $script:RepoDir. Continuando..." "WARN"
  }
}

function Ensure-Repository {
  New-Item -ItemType Directory -Path $script:InstallRoot -Force | Out-Null

  $gitDir = Join-Path $script:RepoDir ".git"
  if (Test-Path $gitDir) {
    Register-SafeDirectory

    if (-not (Test-RepoFilesPresent -RootPath $script:RepoDir)) {
      throw "El repositorio en $script:RepoDir no contiene los archivos requeridos del instalador."
    }

    $dirtyRaw = & $script:GitExe -C $script:RepoDir status --porcelain --untracked-files=all 2>$null
    if ($LASTEXITCODE -ne 0) {
      throw "Fallo git status para validar el repositorio existente."
    }
    $isDirty = -not [string]::IsNullOrWhiteSpace((($dirtyRaw | Out-String).Trim()))

    $branchRaw = & $script:GitExe -C $script:RepoDir rev-parse --abbrev-ref HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
      throw "No se pudo determinar la rama activa del repositorio."
    }
    $currentBranch = (($branchRaw | Out-String).Trim())

    $originRaw = & $script:GitExe -C $script:RepoDir config --get remote.origin.url 2>$null
    $currentOrigin = (($originRaw | Out-String).Trim())

    $reasons = New-Object System.Collections.Generic.List[string]
    if ($isDirty) {
      $reasons.Add("hay cambios locales sin commitear")
    }
    if (-not [string]::Equals($currentBranch, $Branch, [System.StringComparison]::OrdinalIgnoreCase)) {
      $reasons.Add("la rama activa es $currentBranch y se esperaba $Branch")
    }
    if (-not [string]::Equals((Normalize-RepoUrl -Url $currentOrigin), (Normalize-RepoUrl -Url $RepoUrl), [System.StringComparison]::OrdinalIgnoreCase)) {
      $reasons.Add("el remoto origin es $currentOrigin y se esperaba $RepoUrl")
    }

    if ($reasons.Count -gt 0) {
      Add-StepResult -Step "Repositorio" -Status "BLOCKED" -Message ("No se actualiza el repo porque " + ($reasons -join "; ") + ". Se reutiliza la copia local.")
      return @{
        RepoCommit = Get-RepoCommitMarker
        UsingLocal = $true
      }
    }

    $beforeCommit = Get-RepoCommitMarker
    try {
      & $script:GitExe -C $script:RepoDir fetch --all --prune
      if ($LASTEXITCODE -ne 0) {
        throw "git fetch fallo."
      }

      & $script:GitExe -C $script:RepoDir pull --ff-only origin $Branch
      if ($LASTEXITCODE -ne 0) {
        throw "git pull --ff-only fallo."
      }
    } catch {
      Add-StepResult -Step "Repositorio" -Status "BLOCKED" -Message "No se pudo actualizar por Git. Se reutiliza la copia local existente."
      return @{
        RepoCommit = $beforeCommit
        UsingLocal = $true
      }
    }

    $afterCommit = Get-RepoCommitMarker
    if ([string]::Equals($beforeCommit, $afterCommit, [System.StringComparison]::OrdinalIgnoreCase)) {
      Add-StepResult -Step "Repositorio" -Status "SKIP" -Message "El repositorio ya estaba actualizado."
    } else {
      Add-StepResult -Step "Repositorio" -Status "UPDATED" -Message "Repositorio actualizado a $afterCommit."
    }

    return @{
      RepoCommit = $afterCommit
      UsingLocal = $false
    }
  }

  if (Test-Path $script:RepoDir) {
    if (Test-RepoFilesPresent -RootPath $script:RepoDir) {
      Add-StepResult -Step "Repositorio" -Status "BLOCKED" -Message "La carpeta existe sin .git. Se reutiliza la copia local sin actualizar."
      return @{
        RepoCommit = "local-copy"
        UsingLocal = $true
      }
    }

    throw "La carpeta $script:RepoDir existe pero no es un repositorio Git valido ni contiene una copia utilizable."
  }

  Write-Log "Clonando repositorio en $script:RepoDir..."
  & $script:GitExe clone --branch $Branch --single-branch $RepoUrl $script:RepoDir
  if ($LASTEXITCODE -ne 0) {
    throw "Fallo git clone."
  }

  Register-SafeDirectory
  Add-StepResult -Step "Repositorio" -Status "RUN" -Message "Repositorio clonado en $script:RepoDir."
  return @{
    RepoCommit = Get-RepoCommitMarker
    UsingLocal = $false
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

  $currentText = if ($existing.Count -gt 0) { [string]::Join("`n", $existing) + "`n" } else { "" }
  $newText = [string]::Join("`n", $out) + "`n"
  if ($currentText -ceq $newText) {
    return $false
  }

  Set-Content -Path $Path -Value $out -Encoding UTF8
  Add-Content -Path $Path -Value ""
  return $true
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
    [switch]$Secret,
    [switch]$ReuseExisting
  )

  if ($NonInteractive) {
    return $CurrentValue
  }

  if ($ReuseExisting -and -not [string]::IsNullOrWhiteSpace($CurrentValue)) {
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

function Get-FileSha256 {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    return ""
  }

  return (Get-FileHash -Algorithm SHA256 -Path $Path).Hash.ToLowerInvariant()
}

function Ensure-EnvProd {
  $templatePath = Join-Path $script:RepoDir ".env.prod.example"
  $envPath = Join-Path $script:RepoDir ".env.prod"

  if (-not (Test-Path $templatePath)) {
    throw "No se encontro .env.prod.example en $script:RepoDir."
  }

  $created = $false
  if (-not (Test-Path $envPath)) {
    Copy-Item -Path $templatePath -Destination $envPath -Force
    $created = $true
    Write-Log "Se creo .env.prod desde .env.prod.example."
  }

  $map = Read-EnvMap -Path $envPath
  $publicHost = $script:ExpectedPublicHost

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

  $map["TIENDANUBE_CLIENT_ID"] = Prompt-Value -Label "TIENDANUBE_CLIENT_ID" -CurrentValue ([string]$map["TIENDANUBE_CLIENT_ID"]) -ReuseExisting
  $map["TIENDANUBE_CLIENT_SECRET"] = Prompt-Value -Label "TIENDANUBE_CLIENT_SECRET" -CurrentValue ([string]$map["TIENDANUBE_CLIENT_SECRET"]) -Secret -ReuseExisting
  $map["TIENDANUBE_STORE_ID"] = Prompt-Value -Label "TIENDANUBE_STORE_ID" -CurrentValue ([string]$map["TIENDANUBE_STORE_ID"]) -ReuseExisting
  $map["TIENDANUBE_ACCESS_TOKEN"] = Prompt-Value -Label "TIENDANUBE_ACCESS_TOKEN" -CurrentValue ([string]$map["TIENDANUBE_ACCESS_TOKEN"]) -Secret -ReuseExisting
  $map["TIENDANUBE_WEBHOOK_SECRET"] = Prompt-Value -Label "TIENDANUBE_WEBHOOK_SECRET" -CurrentValue ([string]$map["TIENDANUBE_WEBHOOK_SECRET"]) -Secret -ReuseExisting
  if ([string]::IsNullOrWhiteSpace([string]$map["TIENDANUBE_WEBHOOK_SECRET"]) -and -not [string]::IsNullOrWhiteSpace([string]$map["TIENDANUBE_CLIENT_SECRET"])) {
    $map["TIENDANUBE_WEBHOOK_SECRET"] = [string]$map["TIENDANUBE_CLIENT_SECRET"]
  }

  $map["ARCA_CUIT"] = Prompt-Value -Label "ARCA_CUIT" -CurrentValue ([string]$map["ARCA_CUIT"]) -ReuseExisting
  $map["ARCA_CERT_PATH"] = Prompt-Value -Label "ARCA_CERT_PATH" -CurrentValue ([string]$map["ARCA_CERT_PATH"]) -ReuseExisting
  $map["ARCA_KEY_PATH"] = Prompt-Value -Label "ARCA_KEY_PATH" -CurrentValue ([string]$map["ARCA_KEY_PATH"]) -ReuseExisting

  if ($NonInteractive -and [string]::IsNullOrWhiteSpace([string]$map["PUBLIC_HOST"])) {
    throw "En modo -NonInteractive, PUBLIC_HOST debe quedar completo en .env.prod."
  }

  $changed = Write-EnvFilePreserveLines -Path $envPath -Values $map
  Protect-EnvFileAcl -Path $envPath

  if ($created) {
    Add-StepResult -Step ".env.prod" -Status "RUN" -Message ".env.prod creado y convergido a $publicHost."
  } elseif ($changed) {
    Add-StepResult -Step ".env.prod" -Status "UPDATED" -Message ".env.prod actualizado y convergido a $publicHost."
  } else {
    Add-StepResult -Step ".env.prod" -Status "SKIP" -Message ".env.prod ya estaba alineado con $publicHost."
  }

  return @{
    EnvPath = $envPath
    PublicHost = $publicHost
    EnvHash = Get-FileSha256 -Path $envPath
  }
}

function Ensure-DockerVolume {
  param([string]$Name)

  & $script:DockerExe volume inspect $Name *> $null
  if ($LASTEXITCODE -eq 0) {
    return $false
  }

  & $script:DockerExe volume create $Name *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "No se pudo crear el volumen Docker $Name."
  }

  return $true
}

function Get-ContainerState {
  param([string]$ContainerName)

  $raw = & $script:DockerExe inspect --format "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}" $ContainerName 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
    return $null
  }

  $parts = $raw -split "\|", 2
  return [pscustomobject]@{
    Status = $parts[0]
    Health = if ($parts.Count -gt 1) { $parts[1] } else { "" }
  }
}

function Test-ProdStackHealthy {
  $checks = @(
    @{ Name = "retailhub-postgres"; RequireHealthy = $true },
    @{ Name = "retailhub-redis"; RequireHealthy = $true },
    @{ Name = "retailhub-api"; RequireHealthy = $true },
    @{ Name = "retailhub-web"; RequireHealthy = $false },
    @{ Name = "retailhub-webhook-gateway"; RequireHealthy = $false }
  )

  $issues = New-Object System.Collections.Generic.List[string]
  foreach ($check in $checks) {
    $state = Get-ContainerState -ContainerName $check.Name
    if ($null -eq $state) {
      $issues.Add("$($check.Name) no existe")
      continue
    }

    if ($check.RequireHealthy) {
      if ($state.Status -ne "running" -or $state.Health -ne "healthy") {
        $issues.Add("$($check.Name) esta $($state.Status)/$($state.Health)")
      }
    } else {
      if ($state.Status -ne "running") {
        $issues.Add("$($check.Name) esta $($state.Status)")
      }
    }
  }

  return @{
    Ready = ($issues.Count -eq 0)
    Message = if ($issues.Count -eq 0) { "todos los contenedores requeridos estan listos" } else { $issues -join "; " }
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
    $state = Get-ContainerState -ContainerName $ContainerName
    if ($null -ne $state) {
      if ($RequireHealthy) {
        if ($state.Status -eq "running" -and $state.Health -eq "healthy") {
          Write-Log "$ContainerName listo (running/healthy)."
          return
        }
      } else {
        if ($state.Status -eq "running") {
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

function Load-ProdState {
  if (-not (Test-Path $script:StateFile)) {
    return $null
  }

  $raw = Get-Content -Path $script:StateFile -Raw -Encoding UTF8
  if ([string]::IsNullOrWhiteSpace($raw)) {
    return $null
  }

  return ($raw | ConvertFrom-Json)
}

function Save-ProdState {
  param(
    [string]$RepoCommit,
    [string]$EnvHash,
    [string]$ComposeHash
  )

  New-Item -ItemType Directory -Path $script:StateDir -Force | Out-Null
  $state = [pscustomobject]@{
    RepoCommit = $RepoCommit
    EnvHash = $EnvHash
    ComposeHash = $ComposeHash
    SavedAt = (Get-Date).ToString("s")
  }
  $state | ConvertTo-Json -Depth 4 | Set-Content -Path $script:StateFile -Encoding UTF8
}

function Test-SameFingerprint {
  param(
    $Left,
    $Right
  )

  if ($null -eq $Left -or $null -eq $Right) {
    return $false
  }

  return (
    ([string]$Left.RepoCommit -eq [string]$Right.RepoCommit) -and
    ([string]$Left.EnvHash -eq [string]$Right.EnvHash) -and
    ([string]$Left.ComposeHash -eq [string]$Right.ComposeHash)
  )
}

function Ensure-ProdStack {
  param(
    [string]$RepoCommit,
    [string]$EnvHash
  )

  $createdVolumes = New-Object System.Collections.Generic.List[string]
  foreach ($volumeName in @("laschulas_pg_data", "laschulas_staticfiles", "laschulas_mediafiles")) {
    if (Ensure-DockerVolume -Name $volumeName) {
      $createdVolumes.Add($volumeName) | Out-Null
    }
  }

  $composePath = Join-Path $script:RepoDir "docker-compose.prod.yml"
  $composeHash = Get-FileSha256 -Path $composePath
  $currentFingerprint = [pscustomobject]@{
    RepoCommit = $RepoCommit
    EnvHash = $EnvHash
    ComposeHash = $composeHash
  }

  $previousState = Load-ProdState
  $stackState = Test-ProdStackHealthy
  $sameFingerprint = Test-SameFingerprint -Left $previousState -Right $currentFingerprint

  if ($sameFingerprint -and $stackState.Ready) {
    Add-StepResult -Step "Stack Docker" -Status "SKIP" -Message "Stack productivo ya estaba levantado y sin cambios."
    return
  }

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

  Save-ProdState -RepoCommit $RepoCommit -EnvHash $EnvHash -ComposeHash $composeHash

  $status = "RUN"
  $message = "Stack productivo desplegado."
  if ($null -ne $previousState) {
    if ($sameFingerprint) {
      $message = "Stack productivo reconciliado porque habia contenedores faltantes o degradados."
    } else {
      $status = "UPDATED"
      $message = "Stack productivo redeployado porque cambio el fingerprint local."
    }
  }
  if ($createdVolumes.Count -gt 0) {
    $message = "$message Volumenes creados: $($createdVolumes -join ', ')."
  }

  Add-StepResult -Step "Stack Docker" -Status $status -Message $message
}

function Get-TailscaleStatusObject {
  $statusRaw = & $script:TailscaleExe status --json 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($statusRaw)) {
    return $null
  }

  return ($statusRaw | ConvertFrom-Json)
}

function Ensure-TailscaleLogin {
  if ($SkipTailscale) {
    Add-StepResult -Step "Login Tailscale" -Status "SKIP" -Message "SkipTailscale activo."
    return $null
  }

  $statusObj = Get-TailscaleStatusObject
  if ($null -eq $statusObj) {
    Write-Log "Tailscale no esta autenticado. Ejecutando 'tailscale up'..."
    & $script:TailscaleExe up
    if ($LASTEXITCODE -ne 0) {
      throw "No se pudo completar tailscale up."
    }

    $statusObj = Get-TailscaleStatusObject
    if ($null -eq $statusObj) {
      throw "No se pudo leer el estado de Tailscale despues del login."
    }

    $dnsHost = ([string]$statusObj.Self.DNSName).Trim().TrimEnd(".")
    $script:ActualDnsHost = $dnsHost
    Add-StepResult -Step "Login Tailscale" -Status "RUN" -Message "Tailscale autenticado como $dnsHost."
    return $statusObj
  }

  $dnsHost = ([string]$statusObj.Self.DNSName).Trim().TrimEnd(".")
  if ([string]::IsNullOrWhiteSpace($dnsHost)) {
    throw "No se pudo obtener DNSName de Tailscale."
  }

  $script:ActualDnsHost = $dnsHost
  Add-StepResult -Step "Login Tailscale" -Status "SKIP" -Message "Tailscale ya estaba autenticado como $dnsHost."
  return $statusObj
}

function Confirm-TailscaleExpectedHost {
  param($StatusObject)

  if ($SkipTailscale) {
    Add-StepResult -Step "Host Tailscale" -Status "SKIP" -Message "SkipTailscale activo."
    return $false
  }

  $dnsHost = ([string]$StatusObject.Self.DNSName).Trim().TrimEnd(".")
  if ([string]::IsNullOrWhiteSpace($dnsHost)) {
    throw "No se pudo obtener DNSName de Tailscale."
  }

  if ([string]::Equals($dnsHost, $script:ExpectedPublicHost, [System.StringComparison]::OrdinalIgnoreCase)) {
    Add-StepResult -Step "Host Tailscale" -Status "SKIP" -Message "El DNS real coincide con $script:ExpectedPublicHost."
    return $true
  }

  $reason = "Esta PC responde como $dnsHost pero se esperaba $script:ExpectedPublicHost. Falta moverla al tailnet correcto o renombrar el nodo."
  Mark-PartialInstall -Reason $reason
  Add-StepResult -Step "Host Tailscale" -Status "BLOCKED" -Message $reason
  return $false
}

function Get-TailscaleConfigJson {
  param(
    [ValidateSet("serve", "funnel")]
    [string]$Mode
  )

  $raw = & $script:TailscaleExe $Mode status --json 2>$null
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($raw)) {
    return "{}"
  }

  return $raw
}

function Test-TailscaleStatusHasRoute {
  param(
    [string]$JsonText,
    [string]$Port,
    [string]$Target
  )

  if ([string]::IsNullOrWhiteSpace($JsonText)) {
    return $false
  }

  $text = $JsonText.ToLowerInvariant()
  $portRegex = "(^|[^0-9])" + [regex]::Escape($Port) + "([^0-9]|$)"
  return ([regex]::IsMatch($text, $portRegex) -and $text.Contains($Target.ToLowerInvariant()))
}

function Ensure-TailscaleExposure {
  param([bool]$HostMatches)

  if ($SkipTailscale) {
    Add-StepResult -Step "Tailscale Serve" -Status "SKIP" -Message "SkipTailscale activo."
    Add-StepResult -Step "Tailscale Funnel" -Status "SKIP" -Message "SkipTailscale activo."
    return
  }

  if (-not $HostMatches) {
    Add-StepResult -Step "Tailscale Serve" -Status "BLOCKED" -Message "Se omite hasta que el DNS real coincida con $script:ExpectedPublicHost."
    Add-StepResult -Step "Tailscale Funnel" -Status "BLOCKED" -Message "Se omite hasta que el DNS real coincida con $script:ExpectedPublicHost."
    return
  }

  $serveJson = Get-TailscaleConfigJson -Mode "serve"
  if (Test-TailscaleStatusHasRoute -JsonText $serveJson -Port "8443" -Target "http://127.0.0.1:80") {
    Add-StepResult -Step "Tailscale Serve" -Status "SKIP" -Message "Serve ya publicaba 8443 -> http://127.0.0.1:80."
  } else {
    & $script:TailscaleExe serve --yes --bg --https=8443 http://127.0.0.1:80
    if ($LASTEXITCODE -ne 0) {
      throw "Fallo tailscale serve para 8443 -> http://127.0.0.1:80."
    }
    $status = if ($serveJson.Trim() -eq "{}") { "RUN" } else { "UPDATED" }
    Add-StepResult -Step "Tailscale Serve" -Status $status -Message "Serve configurado en 8443 -> http://127.0.0.1:80."
  }

  $funnelJson = Get-TailscaleConfigJson -Mode "funnel"
  if (Test-TailscaleStatusHasRoute -JsonText $funnelJson -Port "443" -Target "http://127.0.0.1:8080") {
    Add-StepResult -Step "Tailscale Funnel" -Status "SKIP" -Message "Funnel ya publicaba 443 -> http://127.0.0.1:8080."
  } else {
    & $script:TailscaleExe funnel --yes --bg --https=443 http://127.0.0.1:8080
    if ($LASTEXITCODE -ne 0) {
      throw "Fallo tailscale funnel para 443 -> http://127.0.0.1:8080."
    }
    $status = if ($funnelJson.Trim() -eq "{}") { "RUN" } else { "UPDATED" }
    Add-StepResult -Step "Tailscale Funnel" -Status $status -Message "Funnel configurado en 443 -> http://127.0.0.1:8080."
  }
}

function Backup-FileWithTimestamp {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    return $null
  }

  $backupDir = Join-Path ([System.IO.Path]::GetDirectoryName($Path)) "backup"
  New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $leaf = [System.IO.Path]::GetFileName($Path)
  $backupPath = Join-Path $backupDir "$leaf.$stamp.bak"
  Move-Item -Path $Path -Destination $backupPath -Force
  return $backupPath
}

function Get-CertificateInfo {
  param([string]$CertPath)

  if (-not (Test-Path $CertPath)) {
    return $null
  }

  try {
    $resolved = Resolve-Path $CertPath
    $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($resolved.Path)
    return @{
      DnsName = $cert.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::DnsName, $false)
      NotAfter = $cert.NotAfter
    }
  } catch {
    return $null
  }
}

function Ensure-TailscaleCertificate {
  param([bool]$HostMatches)

  if ($SkipTailscale) {
    Add-StepResult -Step "Certificados" -Status "SKIP" -Message "SkipTailscale activo."
    return
  }

  if (-not $HostMatches) {
    Add-StepResult -Step "Certificados" -Status "BLOCKED" -Message "Se omite la emision de certificados hasta que el DNS real coincida con $script:ExpectedPublicHost."
    return
  }

  $certDir = Join-Path $script:RepoDir "certs"
  $certPath = Join-Path $certDir "tls.crt"
  $keyPath = Join-Path $certDir "tls.key"
  New-Item -ItemType Directory -Path $certDir -Force | Out-Null

  $certInfo = Get-CertificateInfo -CertPath $certPath
  $keyExists = Test-Path $keyPath
  $minValidUntil = (Get-Date).AddDays(30)

  if ($null -ne $certInfo -and $keyExists) {
    $certDns = (([string]$certInfo.DnsName).Trim()).TrimEnd(".")
    if ([string]::Equals($certDns, $script:ExpectedPublicHost, [System.StringComparison]::OrdinalIgnoreCase) -and $certInfo.NotAfter -ge $minValidUntil) {
      Add-StepResult -Step "Certificados" -Status "SKIP" -Message "tls.crt/tls.key ya son validos para $certDns hasta $($certInfo.NotAfter.ToString('yyyy-MM-dd HH:mm:ss'))."
      return
    }
  }

  $hadArtifacts = (Test-Path $certPath) -or (Test-Path $keyPath)
  if ($hadArtifacts) {
    $backupTargets = New-Object System.Collections.Generic.List[string]
    $backupCert = Backup-FileWithTimestamp -Path $certPath
    if ($backupCert) { $backupTargets.Add($backupCert) | Out-Null }
    $backupKey = Backup-FileWithTimestamp -Path $keyPath
    if ($backupKey) { $backupTargets.Add($backupKey) | Out-Null }
    if ($backupTargets.Count -gt 0) {
      Write-Log "Artifacts TLS previos respaldados: $($backupTargets -join ', ')"
    }
  }

  & $script:TailscaleExe cert --cert-file $certPath --key-file $keyPath --min-validity 720h $script:ExpectedPublicHost
  if ($LASTEXITCODE -ne 0) {
    throw "Fallo tailscale cert para $script:ExpectedPublicHost."
  }

  $newCertInfo = Get-CertificateInfo -CertPath $certPath
  if ($null -eq $newCertInfo) {
    throw "Se genero tls.crt pero no se pudo validar su contenido."
  }
  if (-not (Test-Path $keyPath)) {
    throw "Se genero tls.crt pero falta tls.key."
  }

  $newDns = (([string]$newCertInfo.DnsName).Trim()).TrimEnd(".")
  if (-not [string]::Equals($newDns, $script:ExpectedPublicHost, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "El certificado emitido corresponde a $newDns y no a $script:ExpectedPublicHost."
  }

  $status = if ($hadArtifacts) { "UPDATED" } else { "RUN" }
  Add-StepResult -Step "Certificados" -Status $status -Message "Certificados emitidos para $newDns con validez hasta $($newCertInfo.NotAfter.ToString('yyyy-MM-dd HH:mm:ss'))."
}

function Get-HttpStatusCode {
  param(
    [string]$Url,
    [string]$Method = "GET"
  )

  try {
    $response = Invoke-WebRequest -Uri $Url -Method $Method -MaximumRedirection 0 -TimeoutSec 30 -UseBasicParsing
    return [int]$response.StatusCode
  } catch {
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
      return [int]$_.Exception.Response.StatusCode
    }
    return 0
  }
}

function Validate-Exposure {
  param([bool]$HostMatches)

  if ($SkipTailscale) {
    Add-StepResult -Step "Validacion final" -Status "SKIP" -Message "SkipTailscale activo."
    return
  }

  if (-not $HostMatches) {
    Add-StepResult -Step "Validacion final" -Status "BLOCKED" -Message "Se omite hasta que el DNS real coincida con $script:ExpectedPublicHost."
    return
  }

  $publicRoot = Get-HttpStatusCode -Url "https://$script:ExpectedPublicHost/"
  if ($publicRoot -ne 404) {
    throw "La raiz publica devolvio $publicRoot (se esperaba 404)."
  }

  $webhookStatus = Get-HttpStatusCode -Url "https://$script:ExpectedPublicHost/api/retail/online/webhooks/orden-pagada/" -Method "POST"
  if ($webhookStatus -eq 404 -or $webhookStatus -eq 0) {
    throw "El webhook publico no quedo accesible (status $webhookStatus)."
  }

  $adminStatus = Get-HttpStatusCode -Url "https://$script:ExpectedPublicHost`:8443/login"
  if (@(200, 301, 302, 307, 308) -notcontains $adminStatus) {
    throw "La URL admin privada no valida (status $adminStatus)."
  }

  Add-StepResult -Step "Validacion final" -Status "SKIP" -Message "URLs validadas: root=404, webhook=$webhookStatus, admin=$adminStatus."
}

function Register-StartupTask {
  $taskName = "RetailHub-Start"
  $controlScript = Join-Path $script:RepoDir "deploy\retailhub_service.ps1"
  if (-not (Test-Path $controlScript)) {
    throw "No existe script de control: $controlScript"
  }

  $psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$controlScript`" -Action start -InstallRoot `"$script:InstallRoot`""
  $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  if ($existing) {
    $existingAction = $existing.Actions | Select-Object -First 1
    if ($existingAction -and [string]::Equals([string]$existingAction.Execute, "powershell.exe", [System.StringComparison]::OrdinalIgnoreCase) -and [string]::Equals([string]$existingAction.Arguments, $psArgs, [System.StringComparison]::Ordinal)) {
      Add-StepResult -Step "Tarea programada" -Status "SKIP" -Message "RetailHub-Start ya estaba configurada."
      return
    }
  }

  $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs
  $trigger = New-ScheduledTaskTrigger -AtStartup
  $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  $status = if ($existing) { "UPDATED" } else { "RUN" }
  Add-StepResult -Step "Tarea programada" -Status $status -Message "RetailHub-Start registrada para iniciar al boot."
}

function Show-InstallSummary {
  param([string]$PublicHost)

  Write-Host ""
  Write-Host "================= RESUMEN INSTALACION ================="
  Write-Host "Log: $script:LogFile"
  Write-Host ""

  foreach ($entry in $script:StepResults) {
    Write-Host ("[{0}] {1}: {2}" -f $entry.Status, $entry.Step, $entry.Message)
  }

  Write-Host ""
  if ($script:PartialInstall) {
    Write-Host "Estado final: PARCIAL (codigo 10)"
    Write-Host "Docker y configuracion base quedaron listos, pero Tailscale sigue pendiente."
    Write-Host "Host esperado: $PublicHost"
    if (-not [string]::IsNullOrWhiteSpace($script:ActualDnsHost)) {
      Write-Host "Host actual:   $script:ActualDnsHost"
    }
    Write-Host "Accion externa requerida:"
    Write-Host "1) Poner esta PC en el tailnet correcto o renombrar el nodo para que responda como $PublicHost."
    Write-Host "2) Verificar con 'tailscale status' que el DNS real coincida exactamente."
    Write-Host "3) Reejecutar el instalador para aplicar Serve, Funnel y certificados."
  } else {
    Write-Host "Estado final: COMPLETO (codigo 0)"
    Write-Host "Admin privado: https://$PublicHost`:8443"
    Write-Host "Webhook publico: https://$PublicHost/api/retail/online/webhooks/orden-pagada/"
  }

  Write-Host "======================================================="
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
  Write-Log "ExpectedPublicHost: $script:ExpectedPublicHost"
  Write-Log "Flags: SkipWinget=$SkipWinget SkipTailscale=$SkipTailscale NonInteractive=$NonInteractive"

  Assert-Internet
  Add-StepResult -Step "Internet" -Status "SKIP" -Message "Conectividad validada."

  Warn-VirtualizationState
  Initialize-Winget
  Ensure-Dependencies
  Ensure-DockerReady

  $repoInfo = Ensure-Repository
  $envInfo = Ensure-EnvProd
  Ensure-ProdStack -RepoCommit ([string]$repoInfo.RepoCommit) -EnvHash ([string]$envInfo.EnvHash)

  $tailscaleStatus = $null
  $hostMatches = $false
  if (-not $SkipTailscale) {
    $tailscaleStatus = Ensure-TailscaleLogin
    $hostMatches = Confirm-TailscaleExpectedHost -StatusObject $tailscaleStatus
  }

  Ensure-TailscaleExposure -HostMatches $hostMatches
  Ensure-TailscaleCertificate -HostMatches $hostMatches
  Validate-Exposure -HostMatches $hostMatches
  Register-StartupTask

  Show-InstallSummary -PublicHost $envInfo.PublicHost
  Write-Log "Instalacion finalizada."

  if ($script:PartialInstall) {
    exit 10
  }

  exit 0
} catch {
  $msg = $_.Exception.Message
  if (-not $msg) {
    $msg = "Error no controlado."
  }

  Add-StepResult -Step "Instalacion" -Status "FAIL" -Message $msg
  Write-Host ""
  Write-Host "Instalacion fallida. Revisar log: $script:LogFile" -ForegroundColor Red
  exit 1
}
