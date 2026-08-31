# Configure the mini program to use this PC's current LAN IPv4 address.
# Usage: powershell -ExecutionPolicy Bypass -File .\configure_mini_lan.ps1

$activeInterfaces = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
  Where-Object { $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up }

function Get-UsableIPv4($networkInterface) {
  $properties = $networkInterface.GetIPProperties()
  $address = $properties.UnicastAddresses |
    Where-Object {
      $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
      $_.Address.IPAddressToString -ne '127.0.0.1' -and
      -not $_.Address.IPAddressToString.StartsWith('169.254.')
    } |
    Select-Object -First 1

  if ($address) { return $address.Address.IPAddressToString }
  return $null
}

# Prefer the active physical WLAN adapter. This works on both Chinese and
# English Windows and does not depend on ipconfig's localized headings.
$selectedInterface = $activeInterfaces |
  Where-Object {
    $_.NetworkInterfaceType -eq [System.Net.NetworkInformation.NetworkInterfaceType]::Wireless80211 -and
    (Get-UsableIPv4 $_)
  } |
  Select-Object -First 1

$lanIp = if ($selectedInterface) { Get-UsableIPv4 $selectedInterface } else { $null }
if (-not $lanIp) { throw 'No active WLAN IPv4 found. Connect this PC and the phone to the same Wi-Fi.' }

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
