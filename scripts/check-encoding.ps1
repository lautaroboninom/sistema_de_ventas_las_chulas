Param(
  [Parameter(Mandatory=$false)][string]$Root = ".",
  [string[]]$Extensions = @(".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html", ".md", ".json"),
  [switch]$FailOnIssues
)

function ShouldProcessFile($path) {
  $ext = [IO.Path]::GetExtension($path)
  return $Extensions -contains $ext.ToLower()
}

$bad = @()
$withBom = @()
$files = Get-ChildItem -Recurse -File $Root
foreach ($f in $files) {
  if (-not (ShouldProcessFile $f.FullName)) { continue }
  try {
    $bytes = [IO.File]::ReadAllBytes($f.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
      $withBom += $f.FullName
    }
    $text = [Text.UTF8Encoding]::UTF8.GetString($bytes)
    if ($text.Contains([char]0xFFFD)) { $bad += $f.FullName }
  } catch {
    Write-Warning "Skip (error): $($f.FullName) - $($_.Exception.Message)"
  }
}

if ($withBom.Count -gt 0) {
  Write-Output "Files with UTF-8 BOM:"; $withBom | ForEach-Object { Write-Output "  $_" }
}
if ($bad.Count -gt 0) {
  Write-Output "Files containing U+FFFD (replacement char):"; $bad | ForEach-Object { Write-Output "  $_" }
}

if ($FailOnIssues -and ($withBom.Count -gt 0 -or $bad.Count -gt 0)) { exit 1 }
Write-Output "Check done. BOM: $($withBom.Count); ReplacementChar: $($bad.Count)"
