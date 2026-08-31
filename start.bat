@echo off
title MallQuest AI Assistant - One Click Start
echo ============================================
echo   MallQuest Private AI Assistant Launcher
echo ============================================
echo.

rem ===== Your OpenCV env python (edit here if different) =====
set "PY=C:\Users\lenovo\.conda\envs\OpenCV\python.exe"
if not exist "%PY%" (
  echo [ERROR] python not found:
  echo   %PY%
  echo Edit the PY= line near the top of start.bat to your python.exe path.
  pause
  exit /b 1
)

echo [1/2] Starting BACKEND  http://127.0.0.1:8000 ...
start "MallQuest-Backend" cmd /k "cd /d %~dp0server && %PY% -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000"

echo [2/2] Starting FRONTEND  http://localhost:5173 ...
start "MallQuest-Frontend" cmd /k "cd /d %~dp0web && npm run dev"

echo.
echo ============================================
echo   Both service windows were opened.
echo   Keep BOTH windows open (closing stops a service).
echo.
echo   Open in browser:  http://localhost:5173
echo   Login:            demo / demo123
echo ============================================
echo.
pause
