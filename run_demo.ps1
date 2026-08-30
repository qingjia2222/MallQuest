$Conda = 'D:\miniconda\Miniconda3\Scripts\conda.exe'
if (-not (Test-Path -LiteralPath $Conda)) { throw 'Miniconda not found at the audited path.' }
& $Conda run -n OpenCV python server/scripts/init_demo.py
if ($LASTEXITCODE -ne 0) { throw 'Demo initialization failed.' }
Write-Host 'Backend: http://127.0.0.1:8000  Swagger: http://127.0.0.1:8000/docs'
$Node = Get-Command node -ErrorAction SilentlyContinue
if ($Node) {
  Start-Process -WindowStyle Hidden -FilePath $Node.Source -ArgumentList 'dev-server.mjs' -WorkingDirectory (Join-Path $PSScriptRoot 'web')
  Write-Host 'Web: http://127.0.0.1:5173'
} else {
  Write-Host 'Node.js not found; start web/dev-server.mjs manually after installing Node.js.'
}
Write-Host 'Mini Program: import the app folder in WeChat DevTools; URL checks are disabled for local recording.'
& $Conda run -n OpenCV python -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000
