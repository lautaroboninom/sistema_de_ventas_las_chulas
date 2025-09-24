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
  throw "No se pudo abrir la base Access. Instalar Microsoft Access Database Engine (ACE) 16/12."
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
function Fmt-DT([object]$v, [string]$fmt) { $d = $v -as [datetime]; if ($d) { return $d.ToString($fmt) } return '' }
function Get-Col([object]$row, [string]$name) { try { if ($row.Table.Columns.Contains($name)) { return $row[$name] } } catch {}; return $null }
function To-Bool01([object]$v){ if ($null -eq $v) { return '' }; $s = ($v.ToString() | ForEach-Object { $_.Trim().ToLower() }); if ($s -in @('true','-1','1','si','sí','ok','x','y')) { return '1' }; if ($s -in @('false','0','no')) { return '0' }; return '' }

$cn = New-OleDbConnection -path $DbPath
try {
  # Customers
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [CodEmpresa], [NombreEmpresa], [Contacto], [Telefono 1], [Telefono 2], [E-mail] FROM [Clientes]";
  $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dt = New-Object System.Data.DataTable; [void]$adp.Fill($dt)
  $outFile = Join-Path $OutDir 'customers.csv'; $cols = @('id','cod_empresa','razon_social','cuit','contacto','telefono','telefono_2','email')
  Write-CsvUtf8 $dt $outFile $cols { param($r) @('',(To-Str $r['CodEmpresa']),(To-Str $r['NombreEmpresa']),'',(To-Str $r['Contacto']),(To-Str $r['Telefono 1']),(To-Str $r['Telefono 2']),((To-Str $r['E-mail']).ToLower())) }
  Write-Host "OK: Exportado -> $outFile"

  # Presupuestos
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT * FROM [Presupuestos]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtPresu = New-Object System.Data.DataTable; [void]$adp.Fill($dtPresu)
  $outFile = Join-Path $OutDir 'presupuestos_access.csv'; $cols = @('ingreso_id','costo_cliente','costo_cliente2','fecha_emision','fecha_aprobado','forma_pago','mant_oferta','plazo_entrega','garant','altern2','emitido_por','presupuestado')
  Write-CsvUtf8 $dtPresu $outFile $cols { param($r) @((To-Str (Get-Col $r 'Id')),(To-Str (Get-Col $r 'CostoCliente')),(To-Str (Get-Col $r 'CostoCliente2')),(Fmt-DT (Get-Col $r 'FechaEmision') 'yyyy-MM-dd HH:mm:ss'),(Fmt-DT (Get-Col $r 'FechaAprobado') 'yyyy-MM-dd HH:mm:ss'),(To-Str (Get-Col $r 'FormaPago')),(To-Str (Get-Col $r 'MantOferta')),(To-Str (Get-Col $r 'PlazoEntrega')),(To-Str (Get-Col $r 'Garant')),(To-Str (Get-Col $r 'Altern2')),(To-Str (Get-Col $r 'EmitidoPor')),(To-Bool01 (Get-Col $r 'Presupuestado'))) }
  Write-Host "OK: Exportado -> $outFile"

  # Registros de servicio: costos
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id], [CostoManodeObra], [CostoRepuestos], [CostoTotal], [AutorizadoPor], [PiezasReemplazadas] FROM [RegistrosdeServicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtReg = New-Object System.Data.DataTable; [void]$adp.Fill($dtReg)
  $outFile = Join-Path $OutDir 'reg_serv_costos_access.csv'; $cols = @('ingreso_id','costo_mano_obra','costo_repuestos','costo_total','autorizado_por')
  Write-CsvUtf8 $dtReg $outFile $cols { param($r) @((To-Str $r['Id']),(To-Str $r['CostoManodeObra']),(To-Str $r['CostoRepuestos']),(To-Str $r['CostoTotal']),(To-Str $r['AutorizadoPor'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Registros de servicio: textos (detecta columna de descripción)
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT * FROM [RegistrosdeServicio] WHERE 1=0"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtSchema = New-Object System.Data.DataTable; [void]$adp.Fill($dtSchema)
  $descCol = $null; foreach($c in $dtSchema.Columns){ if(($c.ColumnName -match 'Problema') -and ($c.ColumnName -match 'Descr')){ $descCol = $c.ColumnName; break } }; if(-not $descCol){ $descCol = 'DescripcionProblema' }
  $safe = $descCol -replace ']' , ']]'
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id], [${safe}] AS DescTxt, [PiezasReemplazadas] FROM [RegistrosdeServicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtRegText = New-Object System.Data.DataTable; [void]$adp.Fill($dtRegText)
  $outFile = Join-Path $OutDir 'ingresos_textos_access.csv'; $cols = @('ingreso_id','descripcion_problema','piezas_reemplazadas')
  Write-CsvUtf8 $dtRegText $outFile $cols { param($r) @((To-Str $r['Id']),(To-Str $r['DescTxt']),(To-Str $r['PiezasReemplazadas'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Catálogos: marcas (desde tabla Marca)
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT DISTINCT TRIM([Marca]) AS Marca FROM [Marca] WHERE [Marca] IS NOT NULL AND TRIM([Marca])<>''"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtMarca = New-Object System.Data.DataTable; [void]$adp.Fill($dtMarca)
  $outFile = Join-Path $OutDir 'marcas_access.csv'; $cols = @('nombre'); Write-CsvUtf8 $dtMarca $outFile $cols { param($r) @((To-Str $r['Marca'])) }; Write-Host "OK: Exportado -> $outFile"

  # Modelos por marca (desde Servicio)
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT DISTINCT TRIM([Marca]) AS Marca, TRIM([Modelo]) AS Modelo FROM [Servicio] WHERE [Marca] IS NOT NULL AND TRIM([Marca])<>'' AND [Modelo] IS NOT NULL AND TRIM([Modelo])<>''"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtMM = New-Object System.Data.DataTable; [void]$adp.Fill($dtMM)
  $outFile = Join-Path $OutDir 'models_access.csv'; $cols = @('marca_nombre','nombre'); Write-CsvUtf8 $dtMM $outFile $cols { param($r) @((To-Str $r['Marca']), (To-Str $r['Modelo'])) }; Write-Host "OK: Exportado -> $outFile"

  # Proveedores externos
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT TRIM([NombreEmpresa]) AS Nombre FROM [Proveedores] WHERE [NombreEmpresa] IS NOT NULL AND TRIM([NombreEmpresa])<>''"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtProv = New-Object System.Data.DataTable; [void]$adp.Fill($dtProv)
  $outFile = Join-Path $OutDir 'proveedores_externos_access.csv'; $cols = @('nombre','contacto'); Write-CsvUtf8 $dtProv $outFile $cols { param($r) @((To-Str $r['Nombre']), '') }; Write-Host "OK: Exportado -> $outFile"

  # Motivo map
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id], TRIM([MotivoIngreso]) AS Mot FROM [Motivo]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtMot = New-Object System.Data.DataTable; [void]$adp.Fill($dtMot)
  $motMap = @{}; foreach($row in $dtMot.Rows){ $id = [int]$row['Id']; switch($id){ 1 { $motMap[$id] = 'reparación' } 2 { $motMap[$id] = 'service preventivo' } 3 { $motMap[$id] = 'baja alquiler' } 4 { $motMap[$id] = 'reparación alquiler' } 5 { $motMap[$id] = 'otros' } 6 { $motMap[$id] = 'devolución demo' } Default { $motMap[$id] = 'otros' } } }

  # Servicio base
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT * FROM [Servicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtServ = New-Object System.Data.DataTable; [void]$adp.Fill($dtServ)

  # Devices
  $outFile = Join-Path $OutDir 'devices_access.csv'; $cols = @('id','customer_cod_empresa','marca_nombre','modelo_nombre','numero_serie','propietario','garantia_bool','etiq_garantia_ok','n_de_control','alquilado')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r) @((To-Str $r['Id']),(To-Str $r['CodEmpresa']),(To-Str $r['Marca']),(To-Str $r['Modelo']),(To-Str $r['NumeroSerie']),(To-Str $r['Propietario']),(To-Bool01 $r['Garantia']),(To-Bool01 $r['EtiqGarantia']),(To-Str $r['NdeControl']),(To-Bool01 $r['Alquilado'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Ingresos
  $outFile = Join-Path $OutDir 'ingresos_access.csv'; $cols = @('id','device_id','estado','motivo','fecha_ingreso','fecha_creacion','informe_preliminar','accesorios','remito_ingreso','comentarios','propietario_nombre','propietario_contacto','presupuesto_estado')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r)
    $estado = (([string]$r['Estado']).Trim().ToLower()); $flags = @{ 'entregado'=(To-Bool01 $r['Entregado']); 'derivado'=(To-Bool01 $r['Derivado']); 'reparado'=(To-Bool01 $r['Reparado']); 'reparar'=(To-Bool01 $r['Reparar']) }
    if ($flags['entregado'] -eq '1') { $estado = 'entregado' } elseif ($flags['derivado'] -eq '1') { $estado = 'derivado' } elseif ($flags['reparado'] -eq '1') { $estado = 'reparado' } elseif ($flags['reparar'] -eq '1') { $estado = 'reparar' } if (-not $estado) { $estado = 'ingresado' }
    $mot = $motMap[[int]([string]$r['Motivo'])]; if(-not $mot){ $mot = 'otros' }
    $presu = 'pendiente'
    if ((To-Bool01 $r['IndicPresup']) -eq '1' -or (To-Bool01 $r['Presupuestar']) -eq '1' -or (([string]$r['NuPresup']).Trim() -ne '')) { $presu = 'presupuestado' }
    @((To-Str $r['Id']),(To-Str $r['Id']),$estado,$mot,(Fmt-DT $r['Fecha Ingreso'] 'yyyy-MM-dd HH:mm:ss'),(To-Str $r['Informepreliminar']),(To-Str $r['Accesorios']),(To-Str $r['RemitoIngreso']),(To-Str $r['Comentarios']),(To-Str $r['Propietario']),(To-Str $r['TelefContacto']),$presu)
  }
  Write-Host "OK: Exportado -> $outFile"

  # Derivados
  $outFile = Join-Path $OutDir 'equipos_derivados_access.csv'; $cols = @('ingreso_id','proveedor_nombre','remit_deriv','fecha_deriv','fecha_entrega')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r) @((To-Str $r['Id']),(To-Str $r['DerivadoAProveedor']),(To-Str $r['RemitDerivac']),(Fmt-DT $r['FechaDeriv'] 'yyyy-MM-dd'),(Fmt-DT $r['FechaEntregDeriv'] 'yyyy-MM-dd')) }
  Write-Host "OK: Exportado -> $outFile"

  # Handoffs (facturación / remitos)
  $outFile = Join-Path $OutDir 'handoffs_access.csv'; $cols = @('ingreso_id','n_factura','factura_url','remito_impreso','fecha_impresion_remito','impresion_remito_url','orden_taller')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r)
    $rem = (To-Bool01 ($r['ImpresionRemito']))
    if(-not $rem){ $tmp = (([string]$r['ImpreRemito']).Trim()); if ([string]::IsNullOrWhiteSpace($tmp)) { $rem = '0' } else { $rem = '1' } }
    @((To-Str $r['Id']),(To-Str $r['NFactura']),(To-Str $r['Factura']),$rem,(Fmt-DT $r['FechaImpre'] 'yyyy-MM-dd'),(To-Str $r['ImpreRemito']),(To-Str $r['OrdenTaller'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Tecnicos (id, nombre, baja)
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [IdTecnico], [Nombre], [Baja] FROM [Tecnicos]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtTec = New-Object System.Data.DataTable; [void]$adp.Fill($dtTec)
  $outFile = Join-Path $OutDir 'tecnicos_access.csv'; $cols = @('id_tecnico','nombre','baja')
  Write-CsvUtf8 $dtTec $outFile $cols { param($r) @((To-Str $r['IdTecnico']),(To-Str $r['Nombre']),(To-Bool01 $r['Baja'])) }
  Write-Host "OK: Exportado -> $outFile"

  # IdEmpleado por ingreso
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [Id] AS ingreso_id, [IdEmpleado] FROM [Servicio]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtIE = New-Object System.Data.DataTable; [void]$adp.Fill($dtIE)
  $outFile = Join-Path $OutDir 'ingresos_empleado_access.csv'; $cols = @('ingreso_id','id_empleado')
  Write-CsvUtf8 $dtIE $outFile $cols { param($r) @((To-Str $r['ingreso_id']),(To-Str $r['IdEmpleado'])) }
  Write-Host "OK: Exportado -> $outFile"

  # Fecha de entrega (histrica)
  $outFile = Join-Path $OutDir 'ingresos_entrega_access.csv'; $cols = @('ingreso_id','fecha_entrega')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r) @((To-Str $r['Id']),(Fmt-DT $r['FechaEntrega'] 'yyyy-MM-dd HH:mm:ss')) }
  Write-Host "OK: Exportado -> $outFile"

  # Datos de alquiler (por ingreso)
  $outFile = Join-Path $OutDir 'ingresos_alquiler_access.csv'; $cols = @('ingreso_id','alquilado_flag','recibe_alquiler','cargo_alquiler')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r) @((To-Str $r['Id']),(To-Bool01 (Get-Col $r 'Alquilado')),(To-Str (Get-Col $r 'RecibeAlquiler')),(To-Str (Get-Col $r 'CargoAlquiler'))) }
  Write-Host "OK: Exportado -> $outFile"

  # Estados numericos + flags (para mapeo ubicaciones/estado/resolucion)
  $outFile = Join-Path $OutDir 'ingresos_estado_access.csv';
  $cols = @('id','estado_num','entregado','alquilado','indic_presup','presupuestar','nu_presup','impresion_remito','impre_remito')
  Write-CsvUtf8 $dtServ $outFile $cols { param($r)
    @(
      (To-Str $r['Id']),
      (To-Str $r['Estado']),
      (To-Bool01 $r['Entregado']),
      (To-Bool01 $r['Alquilado']),
      (To-Bool01 $r['IndicPresup']),
      (To-Bool01 $r['Presupuestar']),
      (To-Str  $r['NuPresup']),
      (To-Bool01 (Get-Col $r 'ImpresionRemito')),
      (To-Str (Get-Col $r 'ImpreRemito'))
    )
  }
  Write-Host "OK: Exportado -> $outFile"

  # Mapeo Servicio.IdEquipo -> (marca, modelo) -> models.tipo_equipo
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT [IdEquipos], [Equipo] FROM [Equipos]"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtEq = New-Object System.Data.DataTable; [void]$adp.Fill($dtEq)
  $eqMap = @{}; foreach($row in $dtEq.Rows){ $eqMap[[int]$row['IdEquipos']] = (To-Str $row['Equipo']) }
  $cmd = $cn.CreateCommand(); $cmd.CommandText = "SELECT DISTINCT [Marca], [Modelo], [IdEquipo] FROM [Servicio] WHERE [Marca] IS NOT NULL AND [Modelo] IS NOT NULL AND [IdEquipo] IS NOT NULL"; $adp = New-Object System.Data.OleDb.OleDbDataAdapter($cmd); $dtMM = New-Object System.Data.DataTable; [void]$adp.Fill($dtMM)
  $outFile = Join-Path $OutDir 'model_tipo_equipo_access.csv'; $cols = @('marca_nombre','modelo_nombre','tipo_equipo')
  Write-CsvUtf8 $dtMM $outFile $cols { param($r)
    $tipo = ''
    try { $tipo = (To-Str ($eqMap[[int]([string]$r['IdEquipo'])])) } catch { $tipo = '' }
    @((To-Str $r['Marca']),(To-Str $r['Modelo']),$tipo)
  }
  Write-Host "OK: Exportado -> $outFile"

} finally { if ($cn) { $cn.Close(); $cn.Dispose() } }
