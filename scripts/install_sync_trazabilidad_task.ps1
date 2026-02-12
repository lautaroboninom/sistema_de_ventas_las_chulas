 $taskName = "SyncTrazabilidadGeneralDaily"

 try {
     $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
     $syncScript = Join-Path $scriptDir "sync_trazabilidad_general.ps1"
     if (-not (Test-Path -LiteralPath $syncScript)) {
         Write-Error "No se encontró sync_trazabilidad_general.ps1 en $scriptDir"
         exit 1
     }

     $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$syncScript`""
     # Ejecutar todos los días a las 03:00
     $trigger = New-ScheduledTaskTrigger -Daily -At 03:00

     # Usar el usuario actual con privilegios normales (sin RunLevel Highest)
     Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Force | Out-Null
     Write-Output "Tarea programada '$taskName' creada/actualizada correctamente."
 } catch {
     Write-Error ("Error creando la tarea programada: " + $_.Exception.Message)
     exit 1
 }
