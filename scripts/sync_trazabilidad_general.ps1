param(
    [string]$Source = "Z:\MG BIO\TRAZABILIDAD\@GENERAL.xlsx",
    [string]$TargetDir = "C:\trazabilidad_general",
    [string]$TargetFile = "C:\trazabilidad_general\@GENERAL.xlsx"
)

try {
    if (-not (Test-Path -LiteralPath $Source)) {
        Write-Error "Archivo de origen no encontrado: $Source"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $TargetDir)) {
        New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $TargetFile -Force
    Write-Output "Actualizado: $TargetFile"
} catch {
    Write-Error ("Error sincronizando trazabilidad: " + $_.Exception.Message)
    exit 1
}
