Param(
  [string]$File = "db/admin_scripts.sql",
  [string]$Container = "sepid-db",
  [string]$User = "sepid",
  [string]$Db = "servicio_tecnico"
)

if (!(Test-Path $File)) {
  Write-Error "No se encontró el archivo '$File'"; exit 1
}

Write-Host "Ejecutando SQL en contenedor '$Container' contra DB '$Db'..." -ForegroundColor Cyan

try {
  # Pasa el archivo por stdin para evitar montar rutas
  $sql = Get-Content -Path $File -Raw
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($sql)
  $stdin = [System.IO.MemoryStream]::new($bytes)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "docker"
  $psi.Arguments = "exec -i $Container psql -U $User -d $Db -v ON_ERROR_STOP=1 -q"
  $psi.RedirectStandardInput = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $stdin.CopyTo($p.StandardInput.BaseStream)
  $p.StandardInput.Close()
  $out = $p.StandardOutput.ReadToEnd()
  $err = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($p.ExitCode -ne 0) {
    Write-Error $err
    exit $p.ExitCode
  }
  Write-Host "OK" -ForegroundColor Green
  if ($out) { Write-Output $out }
} catch {
  Write-Error $_.Exception.Message
  exit 1
}

