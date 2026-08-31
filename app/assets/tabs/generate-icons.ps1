Add-Type -AssemblyName System.Drawing

function New-TabIcon([string]$Name, [string]$Color, [scriptblock]$Draw) {
  $bitmap = [System.Drawing.Bitmap]::new(81, 81)
  $bitmap.SetResolution(96, 96)
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $pen = [System.Drawing.Pen]::new([System.Drawing.ColorTranslator]::FromHtml($Color), 5)
  $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
  $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
  & $Draw $graphics $pen
  $bitmap.Save((Join-Path $PSScriptRoot $Name), [System.Drawing.Imaging.ImageFormat]::Png)
  $pen.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}

$chat = { param($g,$p) $g.DrawRectangle($p,15,16,51,37); $g.DrawLines($p,[System.Drawing.Point[]]@([System.Drawing.Point]::new(27,53),[System.Drawing.Point]::new(20,65),[System.Drawing.Point]::new(39,53))); $g.DrawLine($p,27,29,54,29); $g.DrawLine($p,27,40,45,40) }
$map = { param($g,$p) $g.DrawLines($p,[System.Drawing.Point[]]@([System.Drawing.Point]::new(12,22),[System.Drawing.Point]::new(30,13),[System.Drawing.Point]::new(50,22),[System.Drawing.Point]::new(69,13),[System.Drawing.Point]::new(69,59),[System.Drawing.Point]::new(50,68),[System.Drawing.Point]::new(30,59),[System.Drawing.Point]::new(12,68),[System.Drawing.Point]::new(12,22))); $g.DrawLine($p,30,13,30,59); $g.DrawLine($p,50,22,50,68) }
$profile = { param($g,$p) $g.DrawEllipse($p,28,12,25,25); $g.DrawArc($p,15,39,51,36,190,160) }
$homeIcon = { param($g,$p) $g.DrawLines($p,[System.Drawing.Point[]]@([System.Drawing.Point]::new(12,39),[System.Drawing.Point]::new(40,14),[System.Drawing.Point]::new(69,39))); $g.DrawRectangle($p,19,36,43,31); $g.DrawRectangle($p,34,49,13,18) }

New-TabIcon 'home.png' '#9CA3AF' $homeIcon
New-TabIcon 'home-active.png' '#7C3AED' $homeIcon
New-TabIcon 'chat.png' '#9CA3AF' $chat
New-TabIcon 'chat-active.png' '#7C3AED' $chat
New-TabIcon 'map.png' '#9CA3AF' $map
New-TabIcon 'map-active.png' '#7C3AED' $map
New-TabIcon 'profile.png' '#9CA3AF' $profile
New-TabIcon 'profile-active.png' '#7C3AED' $profile
