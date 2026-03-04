param(
  [string]$Source = "web/public/branding/las-chulas-mark.png"
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Source)) {
  Write-Error "No se encontro la imagen de origen: $Source. Copia el logo PNG y pasa -Source si usas otra ruta."
}

$outDir = Join-Path 'web/public' 'icons'
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

Add-Type -AssemblyName System.Drawing

function Export-Size {
  param(
    [System.Drawing.Image]$Img,
    [int]$Size,
    [string]$OutPath,
    [double]$Pad = 0.12
  )
  $bmp = New-Object System.Drawing.Bitmap $Size, $Size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.SmoothingMode = 'HighQuality'
  $g.Clear([System.Drawing.Color]::FromArgb(0,0,0,0))

  $w = $Img.Width; $h = $Img.Height
  $safe = [int]([math]::Round($Size * (1 - $Pad)))
  $scale = [Math]::Min($safe / $w, $safe / $h)
  if ($scale -le 0) { $scale = 1 }
  $nw = [int]([math]::Round($w * $scale))
  $nh = [int]([math]::Round($h * $scale))
  $x = [int](($Size - $nw) / 2)
  $y = [int](($Size - $nh) / 2)

  $rect = New-Object System.Drawing.Rectangle $x, $y, $nw, $nh
  $g.DrawImage($Img, $rect)
  $bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
}

$img = [System.Drawing.Image]::FromFile($Source)

Export-Size -Img $img -Size 16  -OutPath (Join-Path $outDir 'logo-app-16.png')  -Pad 0.18
Export-Size -Img $img -Size 32  -OutPath (Join-Path $outDir 'logo-app-32.png')  -Pad 0.18
Export-Size -Img $img -Size 180 -OutPath (Join-Path $outDir 'logo-app-180.png') -Pad 0.12
Export-Size -Img $img -Size 192 -OutPath (Join-Path $outDir 'logo-app-192.png') -Pad 0.12
Export-Size -Img $img -Size 512 -OutPath (Join-Path $outDir 'logo-app-512.png') -Pad 0.12
Export-Size -Img $img -Size 512 -OutPath (Join-Path $outDir 'logo-app-512-maskable.png') -Pad 0.24

$img.Dispose()

Write-Host "Listo. Iconos generados en $outDir"
