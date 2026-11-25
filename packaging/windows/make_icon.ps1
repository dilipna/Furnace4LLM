# Own Furnace wordmark, drawn with Windows primitives; no third-party artwork.
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object Drawing.Bitmap 64,64
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([Drawing.ColorTranslator]::FromHtml('#b83723'))
$font = New-Object Drawing.Font 'Segoe UI',48,([Drawing.FontStyle]::Bold),([Drawing.GraphicsUnit]::Pixel)
$graphics.DrawString('F',$font,[Drawing.Brushes]::White,13,0)
$icon = [Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream = [IO.File]::Create((Join-Path $PSScriptRoot 'furnace.ico'))
try { $icon.Save($stream) } finally { $stream.Dispose(); $icon.Dispose(); $font.Dispose(); $graphics.Dispose(); $bitmap.Dispose() }
