[CmdletBinding()]
param(
  [ValidateSet('check', 'apply-on-start')]
  [string]$Mode = 'check',
  [switch]$Force,
  [switch]$SkipBackendMigrate,
  [string]$RetailHubRoot = '',
  [string]$Channel = 'main',
  [int]$CooldownHours = 24,
  [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-IsoUtcNow {
  return (Get-Date).ToUniversalTime().ToString('o')
}

function Resolve-PathConfig {
  if (-not $PSScriptRoot) {
    throw 'No se pudo resolver la carpeta del script de actualizacion.'
  }

  $deployDir = $PSScriptRoot
  $repoDir = Split-Path -Parent $deployDir

  $root = [string]$RetailHubRoot
  if ([string]::IsNullOrWhiteSpace($root)) {
    $root = Split-Path -Parent $repoDir
  }
  $root = [System.IO.Path]::GetFullPath($root)

  $resolvedRepo = [System.IO.Path]::GetFullPath($repoDir)
  $stateDir = Join-Path $root 'state'
  $stateFile = Join-Path $stateDir 'update_state.json'

  return @{
    Root = $root
    RepoDir = $resolvedRepo
    StateDir = $stateDir
    StateFile = $stateFile
  }
}

function Resolve-GitExe {
  $cmd = Get-Command git.exe -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  foreach ($path in @(
      "$env:ProgramFiles\Git\cmd\git.exe",
      "$env:ProgramFiles\Git\bin\git.exe",
      "$env:LocalAppData\Programs\Git\cmd\git.exe"
    )) {
    if (Test-Path $path) {
      return $path
    }
  }
  throw 'No se encontro git.exe para gestionar actualizaciones.'
}

function Invoke-GitText {
  param(
    [Parameter(Mandatory = $true)]
    [string[]]$Args,
    [switch]$IgnoreFailure
  )

  $oldErrPref = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    $output = & $script:GitExe -C $script:RepoDir @Args 2>&1
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $oldErrPref
  }
  $text = (($output | Out-String).Trim())
  if ($code -ne 0 -and -not $IgnoreFailure) {
    if ([string]::IsNullOrWhiteSpace($text)) {
      throw "git fallo: $($Args -join ' ') (exit $code)"
    }
    throw "git fallo: $text"
  }
  return $text
}

function Get-HeadCommit {
  $head = Invoke-GitText -Args @('rev-parse', 'HEAD') -IgnoreFailure
  if ([string]::IsNullOrWhiteSpace($head)) {
    return ''
  }
  return $head
}

function Get-RemoteCommit {
  $remote = Invoke-GitText -Args @('rev-parse', "origin/$script:Channel") -IgnoreFailure
  if ([string]::IsNullOrWhiteSpace($remote)) {
    return ''
  }
  return $remote
}

function Normalize-State {
  param(
    [object]$StateObj,
    [string]$FallbackHead
  )

  function Get-StateValue {
    param(
      [object]$Source,
      [string]$Key
    )

    if ($null -eq $Source) {
      return $null
    }
    if ($Source -is [System.Collections.IDictionary]) {
      if ($Source.Contains($Key)) {
        return $Source[$Key]
      }
      return $null
    }

    $prop = $Source.PSObject.Properties[$Key]
    if ($null -ne $prop) {
      return $prop.Value
    }
    return $null
  }

  $channelValue = Get-StateValue -Source $StateObj -Key 'channel'
  $installedValue = Get-StateValue -Source $StateObj -Key 'installed_commit'
  $remoteValue = Get-StateValue -Source $StateObj -Key 'remote_commit'
  $pendingValue = Get-StateValue -Source $StateObj -Key 'pending'
  $lastCheckValue = Get-StateValue -Source $StateObj -Key 'last_check_at'
  $lastUpdateValue = Get-StateValue -Source $StateObj -Key 'last_update_at'
  $lastErrorValue = Get-StateValue -Source $StateObj -Key 'last_error'

  $normalized = [ordered]@{
    channel = if ([string]::IsNullOrWhiteSpace([string]$channelValue)) { $script:Channel } else { [string]$channelValue }
    installed_commit = if ([string]::IsNullOrWhiteSpace([string]$installedValue)) { $FallbackHead } else { [string]$installedValue }
    remote_commit = if ([string]::IsNullOrWhiteSpace([string]$remoteValue)) { $FallbackHead } else { [string]$remoteValue }
    pending = [bool]$pendingValue
    last_check_at = if ($null -eq $lastCheckValue) { $null } else { [string]$lastCheckValue }
    last_update_at = if ($null -eq $lastUpdateValue) { $null } else { [string]$lastUpdateValue }
    last_error = if ($null -eq $lastErrorValue) { $null } else { [string]$lastErrorValue }
  }

  if ([string]::IsNullOrWhiteSpace([string]$normalized.installed_commit)) {
    $normalized.installed_commit = ''
  }
  if ([string]::IsNullOrWhiteSpace([string]$normalized.remote_commit)) {
    $normalized.remote_commit = $normalized.installed_commit
  }
  $normalized.pending = [bool]($normalized.installed_commit -ne $normalized.remote_commit)
  return $normalized
}

function Read-State {
  $head = Get-HeadCommit
  if (-not (Test-Path $script:StateFile)) {
    return (Normalize-State -StateObj @{} -FallbackHead $head)
  }

  try {
    $raw = Get-Content -Path $script:StateFile -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
      return (Normalize-State -StateObj @{} -FallbackHead $head)
    }
    $obj = $raw | ConvertFrom-Json
    return (Normalize-State -StateObj $obj -FallbackHead $head)
  } catch {
    return (Normalize-State -StateObj @{} -FallbackHead $head)
  }
}

function Write-State {
  param([object]$State)

  New-Item -ItemType Directory -Path $script:StateDir -Force | Out-Null
  $json = $State | ConvertTo-Json -Depth 6
  Set-Content -Path $script:StateFile -Value $json -Encoding UTF8
}

function Should-RunFetch {
  param([object]$State)

  if ($Force) {
    return $true
  }

  $last = [string]$State.last_check_at
  if ([string]::IsNullOrWhiteSpace($last)) {
    return $true
  }

  try {
    $lastTime = [datetimeoffset]::Parse($last).UtcDateTime
  } catch {
    return $true
  }

  $hours = ((Get-Date).ToUniversalTime() - $lastTime).TotalHours
  return ($hours -ge [double]$script:CooldownHours)
}

function Sync-BackendDependencies {
  $pythonExe = Join-Path $script:RepoDir 'api\.venv\Scripts\python.exe'
  $requirements = Join-Path $script:RepoDir 'api\requirements.txt'
  if (-not (Test-Path $pythonExe) -or -not (Test-Path $requirements)) {
    return
  }

  & $pythonExe -m pip install -r $requirements *> $null
  if ($LASTEXITCODE -ne 0) {
    throw 'No se pudieron sincronizar dependencias de backend (pip install).'
  }
}

function Resolve-NpmCmd {
  $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }
  foreach ($candidate in @(
      'C:\Program Files\nodejs\npm.cmd',
      'C:\Program Files\nodejs\npm.exe'
    )) {
    if (Test-Path $candidate) {
      return $candidate
    }
  }
  return ''
}

function Sync-FrontendDependencies {
  $npmCmd = Resolve-NpmCmd
  $packageJson = Join-Path $script:RepoDir 'web\package.json'
  $webDir = Join-Path $script:RepoDir 'web'
  if ([string]::IsNullOrWhiteSpace($npmCmd) -or -not (Test-Path $packageJson)) {
    return
  }

  Push-Location $webDir
  try {
    & $npmCmd install --no-fund --no-audit *> $null
    if ($LASTEXITCODE -ne 0) {
      throw 'No se pudieron sincronizar dependencias de frontend (npm install).'
    }
  } finally {
    Pop-Location
  }
}

function Set-BackendEnvForMigrate {
  $commonScript = Join-Path $script:Root 'retailhub_local_common.ps1'
  if (Test-Path $commonScript) {
    . $commonScript
    if (Get-Command Set-RetailHubBackendEnv -ErrorAction SilentlyContinue) {
      Set-RetailHubBackendEnv
      return
    }
  }

  if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = 'las_chulas_retail' }
  if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = 'postgres' }
  if (-not $env:POSTGRES_HOST) { $env:POSTGRES_HOST = '127.0.0.1' }
  if (-not $env:POSTGRES_PORT) { $env:POSTGRES_PORT = '5432' }
}

function Run-BackendMigrations {
  $pythonExe = Join-Path $script:RepoDir 'api\.venv\Scripts\python.exe'
  $apiDir = Join-Path $script:RepoDir 'api'
  if (-not (Test-Path $pythonExe) -or -not (Test-Path $apiDir)) {
    return
  }

  Set-BackendEnvForMigrate

  Push-Location $apiDir
  try {
    & $pythonExe 'manage.py' migrate --noinput *> $null
    if ($LASTEXITCODE -ne 0) {
      throw 'No se pudieron ejecutar migraciones de backend (manage.py migrate).'
    }
  } finally {
    Pop-Location
  }
}

function Invoke-Check {
  param([object]$State)

  $checked = $false
  if (Should-RunFetch -State $State) {
    Invoke-GitText -Args @('fetch', '--prune', 'origin', $script:Channel) | Out-Null
    $State.last_check_at = Get-IsoUtcNow
    $checked = $true
  }

  $State.channel = $script:Channel
  $State.installed_commit = Get-HeadCommit
  $remote = Get-RemoteCommit
  if (-not [string]::IsNullOrWhiteSpace($remote)) {
    $State.remote_commit = $remote
  } elseif ([string]::IsNullOrWhiteSpace([string]$State.remote_commit)) {
    $State.remote_commit = $State.installed_commit
  }
  $State.pending = [bool]($State.installed_commit -ne $State.remote_commit)
  $State.last_error = $null
  Write-State -State $State

  return @{
    Checked = $checked
    Applied = $false
    ErrorMessage = $null
  }
}

function Invoke-ApplyOnStart {
  param([object]$State)

  $applied = $false
  $errorMessage = $null
  try {
    Invoke-GitText -Args @('fetch', '--prune', 'origin', $script:Channel) | Out-Null
    $State.last_check_at = Get-IsoUtcNow
    $State.channel = $script:Channel
    $State.installed_commit = Get-HeadCommit
    $remote = Get-RemoteCommit
    if (-not [string]::IsNullOrWhiteSpace($remote)) {
      $State.remote_commit = $remote
    } elseif ([string]::IsNullOrWhiteSpace([string]$State.remote_commit)) {
      $State.remote_commit = $State.installed_commit
    }
    $State.pending = [bool]($State.installed_commit -ne $State.remote_commit)

    if (-not [bool]$State.pending) {
      $State.last_error = $null
      Write-State -State $State
      return @{
        Checked = $true
        Applied = $false
        ErrorMessage = $null
      }
    }

    Invoke-GitText -Args @('pull', '--ff-only', 'origin', $script:Channel) | Out-Null
    Sync-BackendDependencies
    Sync-FrontendDependencies
    if (-not $SkipBackendMigrate) {
      Run-BackendMigrations
    }

    $State.channel = $script:Channel
    $State.installed_commit = Get-HeadCommit
    $remote = Get-RemoteCommit
    if (-not [string]::IsNullOrWhiteSpace($remote)) {
      $State.remote_commit = $remote
    } else {
      $State.remote_commit = $State.installed_commit
    }
    $State.pending = [bool]($State.installed_commit -ne $State.remote_commit)
    if (-not $State.pending) {
      $State.last_update_at = Get-IsoUtcNow
      $applied = $true
    }
    $State.last_error = $null
    Write-State -State $State
  } catch {
    $errorMessage = $_.Exception.Message
    $State.channel = $script:Channel
    $State.installed_commit = Get-HeadCommit
    $remote = Get-RemoteCommit
    if (-not [string]::IsNullOrWhiteSpace($remote)) {
      $State.remote_commit = $remote
    }
    $State.pending = $true
    $State.last_error = $errorMessage
    Write-State -State $State
  }

  return @{
    Checked = $false
    Applied = $applied
    ErrorMessage = $errorMessage
  }
}

function New-Result {
  param(
    [object]$State,
    [object]$Meta
  )

  return [ordered]@{
    ok = [string]::IsNullOrWhiteSpace([string]$Meta.ErrorMessage)
    mode = $script:Mode
    channel = [string]$State.channel
    pending = [bool]$State.pending
    installed_commit = [string]$State.installed_commit
    remote_commit = [string]$State.remote_commit
    last_check_at = $State.last_check_at
    last_update_at = $State.last_update_at
    last_error = if ([string]::IsNullOrWhiteSpace([string]$Meta.ErrorMessage)) { $State.last_error } else { [string]$Meta.ErrorMessage }
    checked = [bool]$Meta.Checked
    applied = [bool]$Meta.Applied
    state_file = $script:StateFile
  }
}

$script:Root = $null
$script:RepoDir = $null
$script:StateDir = $null
$script:StateFile = $null
$script:GitExe = $null
$script:Channel = [string]$Channel
$script:Mode = [string]$Mode
$script:CooldownHours = [int]$CooldownHours

$result = $null
try {
  $paths = Resolve-PathConfig
  $script:Root = $paths.Root
  $script:RepoDir = $paths.RepoDir
  $script:StateDir = $paths.StateDir
  $script:StateFile = $paths.StateFile
  $script:GitExe = Resolve-GitExe

  $state = Read-State
  $meta = if ($script:Mode -eq 'check') {
    Invoke-Check -State $state
  } else {
    Invoke-ApplyOnStart -State $state
  }
  $state = Read-State
  $result = New-Result -State $state -Meta $meta
} catch {
  $fallback = [ordered]@{
    channel = [string]$script:Channel
    installed_commit = ''
    remote_commit = ''
    pending = $false
    last_check_at = $null
    last_update_at = $null
    last_error = $_.Exception.Message
  }
  $meta = @{
    Checked = $false
    Applied = $false
    ErrorMessage = $_.Exception.Message
  }
  $result = New-Result -State $fallback -Meta $meta
}

if ($Json) {
  Write-Output ($result | ConvertTo-Json -Depth 6 -Compress)
} else {
  Write-Output $result
}
