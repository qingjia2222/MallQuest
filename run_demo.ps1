# 星河里 Demo one-click launcher (auto-detect OpenCV env python)
# Usage (from project root D:\shixi\MallQuest):
#   powershell -ExecutionPolicy Bypass -File run_demo.ps1

# ---- 1) Locate the OpenCV env python ----
# Try candidate paths in order, use the first that exists.
$candidates = @(
  'C:\Users\lenovo\.conda\envs\OpenCV\python.exe',
  'D:\miniconda\Miniconda3\envs\OpenCV\python.exe',
  'D:\miniconda\Miniconda3\Scripts\conda.exe',
  'C:\Users\lenovo\miniconda3\envs\OpenCV\python.exe',
  'C:\Users\lenovo\anaconda3\envs\OpenCV\python.exe'
)
$Python = $null
foreach ($c in $candidates) {
  if (Test-Path -LiteralPath $c) {
    if ($c -like '*conda.exe') {
      $Python = 'conda run -n OpenCV python'
    } else {
      $Python = $c
    }
    break
  }
}
if (-not $Python) {
  $condaCmd = Get-Command conda -ErrorAction SilentlyContinue
  if ($condaCmd) { $Python = 'conda run -n OpenCV python' }
}
if (-not $Python) {
  throw 'OpenCV env not found. Please add your python path to $candidates in run_demo.ps1.'
}
Write-Host "Using Python: $Python"

# ---- 1.5) Replace stale demo listeners from an earlier run ----
# Without this, a newly launched backend can fail to bind while the browser
# silently keeps talking to an old API process.
function Stop-DemoListener([int]$Port, [string[]]$AllowedProcessNames) {
  $listenerPids = @()
  foreach ($line in (netstat -ano -p tcp)) {
    if ($line -match "^\s*TCP\s+\S+:${Port}\s+\S+\s+LISTENING\s+(\d+)\s*$") {
      $listenerPids += [int]$Matches[1]
    }
  }
  foreach ($processId in ($listenerPids | Sort-Object -Unique)) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    if ($AllowedProcessNames -notcontains $process.ProcessName) {
      throw "Port $Port is occupied by $($process.ProcessName) (PID $processId). Close it before starting the demo."
    }
    Write-Host "Stopping stale $($process.ProcessName) on port $Port (PID $processId)"
    Stop-Process -Id $processId -Force
  }
}

Stop-DemoListener 8000 @('python','pythonw')
Stop-DemoListener 5173 @('node')

# ---- 2) Init demo data ----
& $Python server/scripts/init_demo.py
$LanAddress = '192.168.40.24'
$LanConfig = Join-Path $PSScriptRoot 'configure_mini_lan.ps1'
if (Test-Path -LiteralPath $LanConfig) {
  & $LanConfig
  $RequestSource = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'app\utils\request.js') -Raw
  if ($RequestSource -match "BASE_URL = 'http://([^']+):8000'") { $LanAddress = $Matches[1] }
}
Write-Host "Backend (PC): http://127.0.0.1:8000  Swagger: http://127.0.0.1:8000/docs"
Write-Host "Backend (phone): http://${LanAddress}:8000"

# ---- 3) Start Web dev server ----
$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($Npm) {
  Start-Process -WindowStyle Hidden -FilePath $Npm.Source -ArgumentList 'run','dev','--','--host','0.0.0.0' -WorkingDirectory (Join-Path $PSScriptRoot 'web')
  Write-Host "Web (PC): http://127.0.0.1:5173  Web (phone): http://${LanAddress}:5173"
} else {
  Write-Host 'npm not found; run npm install and npm run dev inside web manually.'
}
Write-Host 'Mini Program: import the app folder in WeChat DevTools; URL checks are disabled.'

# ---- 4) Run backend in foreground ----
& $Python -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
