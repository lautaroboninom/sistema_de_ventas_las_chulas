$ErrorActionPreference = 'Stop'
param(
  [string]$AccessPath,
  [string]$OutDir
)

if (-not $AccessPath) { $AccessPath = 'Z:\Servicio Tecnico\1_SISTEMA REPARACIONES\2025-06\Tablas2025 MG-SEPID 2.0.accdb' }
if (-not $OutDir) { $OutDir = 'etl/out/access_export' }

if (-not (Test-Path $AccessPath)) { throw "Access file not found: $AccessPath" }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }

Add-Type -AssemblyName System.Data
$cs = 'Provider=Microsoft.ACE.OLEDB.12.0;Data Source=' + $AccessPath + ';Persist Security Info=False;'
$conn = New-Object System.Data.OleDb.OleDbConnection($cs)
$conn.Open()

function Export-Table([string]$table, [string]$outfile) {
  $cmd = $conn.CreateCommand()
  $cmd.CommandText = ('SELECT * FROM [{0}]' -f $table)
  $da = New-Object System.Data.OleDb.OleDbDataAdapter($cmd)
  $dt = New-Object System.Data.DataTable
  [void]$da.Fill($dt)
  $dt | Export-Csv -Path $outfile -NoTypeInformation -Encoding UTF8
}

Export-Table -table 'Clientes' -outfile (Join-Path $OutDir 'Clientes.csv')
Export-Table -table 'Proveedores' -outfile (Join-Path $OutDir 'Proveedores.csv')
Export-Table -table 'Marca' -outfile (Join-Path $OutDir 'Marca.csv')
Export-Table -table 'Modelo' -outfile (Join-Path $OutDir 'Modelo.csv')
Export-Table -table 'Tecnicos' -outfile (Join-Path $OutDir 'Tecnicos.csv')

$conn.Close()
Write-Output "Exported CSVs to $OutDir"
