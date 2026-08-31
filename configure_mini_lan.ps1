# Configure the mini program to use this PC's current LAN IPv4 address.
# Usage: powershell -ExecutionPolicy Bypass -File .\configure_mini_lan.ps1

$lines = ipconfig
$inWlan = $false
$lanIp = $null
foreach ($line in $lines) {
  if ($line -match '^Wireless LAN adapter WLAN:') { $inWlan = $true; continue }
  if ($inWlan -and $line -match '^\S.*adapter.*:$') { break }
  if ($inWlan -and $line -match '(\d{1,3}(?:\.\d{1,3}){3})') {
    $candidate = $Matches[1]
    if ($candidate -notlike '169.254.*') { $lanIp = $candidate; break }
  }
}
if (-not $lanIp) { throw 'No WLAN IPv4 found. Connect this PC and the phone to the same Wi-Fi.' }

$requestFile = Join-Path $PSScriptRoot 'app\utils\request.js'
$source = Get-Content -LiteralPath $requestFile -Raw -Encoding UTF8
$updated = $source -replace "const BASE_URL = 'http://[^']+:8000';", "const BASE_URL = 'http://${lanIp}:8000';"
if ($updated -eq $source -and $source -notmatch [regex]::Escape("http://${lanIp}:8000")) {
  throw 'BASE_URL was not found in app/utils/request.js.'
}
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($requestFile, $updated.TrimEnd() + [Environment]::NewLine, $utf8NoBom)

Write-Host "Mini Program API: http://${lanIp}:8000"
Write-Host 'Recompile/upload the mini program and keep run_demo.ps1 running.'
