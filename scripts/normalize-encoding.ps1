Param(
  [Parameter(Mandatory=$false)][string]$Root = ".",
  [string[]]$Extensions = @(".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html", ".md", ".json"),
  [switch]$WhatIf
)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function ShouldProcessFile($path) {
  $ext = [IO.Path]::GetExtension($path)
  return $Extensions -contains $ext.ToLower()
}

$files = Get-ChildItem -Recurse -File $Root
$changed = 0
$skipped = 0
foreach ($f in $files) {
  if (-not (ShouldProcessFile $f.FullName)) { $skipped++ ; continue }
  try {
    $bytes = [IO.File]::ReadAllBytes($f.FullName)
    # Detect UTF-8 BOM
    $hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
    # Decode as UTF-8 regardless (preserves content; does not try to fix legacy encodings)
    $start = 0; $len = $bytes.Length
    if ($hasBom) { $start = 3; $len = $bytes.Length - 3 }
    $text = [Text.UTF8Encoding]::UTF8.GetString($bytes, $start, $len)
    if ($WhatIf) {
      if ($hasBom) { Write-Output "BOM->rewrite: $($f.FullName)" }
      continue
    }
    # Always write back as UTF-8 without BOM only when: had BOM or round‑trip changed byte-length
    $newBytes = $utf8NoBom.GetBytes($text)
    $needsRewrite = $hasBom -or ($newBytes.Length -ne $bytes.Length)
    if ($needsRewrite) {
      [IO.File]::WriteAllBytes($f.FullName, $newBytes)
      $changed++
    }
  } catch {
    Write-Warning "Skip (error): $($f.FullName) - $($_.Exception.Message)"
  }
}
Write-Output "Normalized files (UTF-8 no BOM): $changed; Skipped: $skipped"
