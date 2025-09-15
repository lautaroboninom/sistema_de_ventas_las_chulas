param(
  [string]$DbPath = "Z:\\Servicio Tecnico\\1_SISTEMA REPARACIONES\\2025-06\\Tablas2025 MG-SEPID 2.0.accdb",
  [string]$OutDir = "etl/out"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (!(Test-Path -LiteralPath $DbPath)) { throw "No existe el archivo Access: $DbPath" }
if (!(Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

function New-OleDbConnection([string]$path) {
  $providers = @('Microsoft.ACE.OLEDB.16.0','Microsoft.ACE.OLEDB.12.0')
  foreach ($p in $providers) {
    try { $cn = New-Object System.Data.OleDb.OleDbConnection("Provider=$p;Data Source=$path;Persist Security Info=False;"); $cn.Open(); return $cn } catch { if ($cn) { $cn.Dispose() } }
  }
  throw "No se pudo abrir la base Access (ACE 16/12)."
}
function Write-CsvUtf8([System.Data.DataTable]$dt, [string]$path, [string[]]$columns, [scriptblock]$rowMap) {
  $sb = New-Object System.Text.StringBuilder
  [void]$sb.AppendLine(($columns -join ','))
  foreach ($row in $dt.Rows) {
    $vals = & $rowMap $row
    $escaped = $vals | ForEach-Object {
      $s = [string]$_
      if ($s -match '[,\"\n\r]') { '"' + ($s -replace '"','""') + '"' } else { $s }
    }
    [void]$sb.AppendLine(($escaped -join ','))
  }
  Set-Content -LiteralPath $path -Value $sb.ToString() -Encoding UTF8
}
function To-Str([object]$v) { if ($null -eq $v) { return '' } ([string]$v).Trim() }
function To-Bool01([object]$v){ if ($null -eq $v) { return '' }; $s = ($v.ToString() | ForEach-Object { $_.Trim().ToLower() }); if ($s -in @('true','-1','1','si','sí','ok','x','y')) { return '1' }; if ($s -in @('false','0','no')) { return '0' }; return '' }

$cn = New-OleDbConnection -path $DbPath
try {
  # Tecnicos
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [IdTecnico], [Nombre], [Baja] FROM [Tecnicos]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtTec = New-Object System.Data.DataTable; [void]$adp.Fill($dtTec)
  $outFile = Join-Path $OutDir 'tecnicos_access.csv'; $cols = @('id_tecnico','nombre','baja')
  Write-CsvUtf8 $dtTec $outFile $cols { param($r) @((To-Str $r['IdTecnico']),(To-Str $r['Nombre']),(To-Bool01 $r['Baja'])) }
  Write-Host "OK: Exportado -> $outFile"

  # IdEmpleado por ingreso
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id] AS ingreso_id, [IdEmpleado] FROM [Servicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtIE = New-Object System.Data.DataTable; [void]$adp.Fill($dtIE)
  $outFile = Join-Path $OutDir 'ingresos_empleado_access.csv'; $cols = @('ingreso_id','id_empleado')
  Write-CsvUtf8 $dtIE $outFile $cols { param($r) @((To-Str $r['ingreso_id']),(To-Str $r['IdEmpleado'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Motivo por ingreso (Id numérico)
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id] AS ingreso_id, [Motivo] AS motivo_id FROM [Servicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtIM = New-Object System.Data.DataTable; [void]$adp.Fill($dtIM)
  $outFile = Join-Path $OutDir 'ingresos_motivo_access.csv'; $cols = @('ingreso_id','motivo_id')
  Write-CsvUtf8 $dtIM $outFile $cols { param($r) @((To-Str $r['ingreso_id']),(To-Str $r['motivo_id'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Estado + Entregado por ingreso (para resolución y cierre)
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id] AS ingreso_id, [Estado], [Entregado] FROM [Servicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtSE = New-Object System.Data.DataTable; [void]$adp.Fill($dtSE)
  $outFile = Join-Path $OutDir 'ingresos_estado_entrega_access.csv'; $cols = @('ingreso_id','estado_nombre','entregado')
  Write-CsvUtf8 $dtSE $outFile $cols { param($r) @((To-Str $r['ingreso_id']),(To-Str $r['Estado']),(To-Bool01 $r['Entregado'])) }
  Write-Host "OK: Exportado -> $outFile"

} finally { if ($cn) { $cn.Close(); $cn.Dispose() } }
