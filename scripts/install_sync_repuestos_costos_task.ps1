$taskName = "SyncRepuestosCostosDaily"

try {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $syncScript = Join-Path $scriptDir "sync_repuestos_costos.ps1"
    if (-not (Test-Path -LiteralPath $syncScript)) {
        Write-Error "sync_repuestos_costos.ps1 not found in $scriptDir"
        exit 1
    }

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$syncScript`"" -WorkingDirectory $scriptDir
    $trigger = New-ScheduledTaskTrigger -Daily -At 03:15

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Force | Out-Null
    Write-Output "Scheduled task '$taskName' created/updated."
} catch {
    Write-Error ("Error creating scheduled task: " + $_.Exception.Message)
    exit 1
}
