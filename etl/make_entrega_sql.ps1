param(
  [string]$CsvPath = "etl/out/ingresos_entrega_access.csv",
  [string]$OutPath = "tmp_apply_entrega.sql"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (!(Test-Path -LiteralPath $CsvPath)) { throw "No existe CSV: $CsvPath" }

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('CREATE TEMPORARY TABLE tmp_entrega_csv (ingreso_id INT PRIMARY KEY, fecha_entrega DATETIME NULL);') | Out-Null

$rows = Import-Csv -LiteralPath $CsvPath
foreach ($r in $rows) {
  $id = ($r.ingreso_id | ForEach-Object { $_.ToString().Trim() })
  $dt = ($r.fecha_entrega | ForEach-Object { $_.ToString().Trim() })
  if (-not $id) { continue }
  if (-not $dt) { continue }
  try { $idnum = [int]$id } catch { continue }
  $line = "INSERT INTO tmp_entrega_csv (ingreso_id, fecha_entrega) VALUES ($idnum,'$dt');"
  $lines.Add($line) | Out-Null
}

$lines.Add("UPDATE ingresos t JOIN tmp_entrega_csv e ON e.ingreso_id=t.id SET t.fecha_entrega = e.fecha_entrega WHERE t.estado='entregado';") | Out-Null
$lines.Add('DROP TEMPORARY TABLE IF EXISTS tmp_entrega_csv;') | Out-Null

Set-Content -LiteralPath $OutPath -Value ($lines -join "`n") -Encoding UTF8
Write-Host "OK: Generado -> $OutPath (" ($lines.Count) " l�neas)"

