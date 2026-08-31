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

# ---- 2) Init demo data ----
& $Python server/scripts/init_demo.py
Write-Host 'Backend: http://127.0.0.1:8000  Swagger: http://127.0.0.1:8000/docs'

# ---- 3) Start Web dev server ----
$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($Npm) {
  Start-Process -WindowStyle Hidden -FilePath $Npm.Source -ArgumentList 'run','dev','--','--host','127.0.0.1' -WorkingDirectory (Join-Path $PSScriptRoot 'web')
  Write-Host 'Web: http://127.0.0.1:5173'
} else {
  Write-Host 'npm not found; run npm install and npm run dev inside web manually.'
}
Write-Host 'Mini Program: import the app folder in WeChat DevTools; URL checks are disabled.'

# ---- 4) Run backend in foreground ----
& $Python -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
