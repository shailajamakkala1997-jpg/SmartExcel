@echo off
echo ========================================================
echo         Starting SmartExcel Application...
echo ========================================================

cd /d "%~dp0"

echo [1/2] Launching Python FastAPI Backend on Port 8005...
start "SmartExcel Backend (Port 8005)" cmd /k "cd /d %~dp0backend && .\venv\Scripts\python.exe -m uvicorn main:app --port 8005 --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Launching React Vite Frontend on Port 3000...
start "SmartExcel Frontend (Port 3000)" cmd /k "cd /d %~dp0frontend && npm run dev"

timeout /t 2 /nobreak >nul

echo ========================================================
echo  SmartExcel is ready! Opening http://localhost:3000 ...
echo ========================================================
start http://localhost:3000

