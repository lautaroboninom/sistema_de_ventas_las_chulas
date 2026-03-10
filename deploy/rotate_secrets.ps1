param(
  [string]$EnvFile = ".env.prod"
)

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path -Path $EnvFile -PathType Leaf)) {
  Write-Error "No existe $EnvFile"
  exit 1
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = "$EnvFile.rotated.$stamp"
Copy-Item -Path $EnvFile -Destination $outFile -Force

function New-UrlSafeSecret {
  $bytes = New-Object byte[] 48
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  $rng.Dispose()
  return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$values = @{
  "DJANGO_SECRET_KEY" = New-UrlSafeSecret
  "JWT_SECRET" = New-UrlSafeSecret
  "POSTGRES_PASSWORD" = New-UrlSafeSecret
}

$lines = Get-Content -Path $outFile -Encoding UTF8
$seen = @{}
$updated = New-Object System.Collections.Generic.List[string]

foreach ($line in $lines) {
  if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#") -or -not $line.Contains("=")) {
    $updated.Add($line)
    continue
  }

  $parts = $line.Split("=", 2)
  $key = $parts[0].Trim()
  if ($values.ContainsKey($key)) {
    $updated.Add("$key=$($values[$key])")
    $seen[$key] = $true
  } else {
    $updated.Add($line)
  }
}

foreach ($key in $values.Keys) {
  if (-not $seen.ContainsKey($key)) {
    $updated.Add("$key=$($values[$key])")
  }
}

Set-Content -Path $outFile -Value ($updated -join "`n") -Encoding UTF8
Add-Content -Path $outFile -Value ""

Write-Output "Archivo generado: $outFile"
Write-Output ""
Write-Output "Se rotaron claves internas:"
Write-Output "- DJANGO_SECRET_KEY"
Write-Output "- JWT_SECRET"
Write-Output "- POSTGRES_PASSWORD"
Write-Output ""
Write-Output "Pendiente manual (externo):"
Write-Output "- TIENDANUBE_ACCESS_TOKEN / TIENDANUBE_WEBHOOK_SECRET"
Write-Output "- credenciales/certificados ARCA"
Write-Output ""
Write-Output "Siguiente paso sugerido:"
Write-Output "1) Revisar $outFile"
Write-Output "2) Reemplazar .env.prod con ese contenido"
Write-Output "3) Reiniciar stack: docker compose -f docker-compose.prod.yml up -d --build"
