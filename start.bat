@echo off
cd /d "%~dp0"

REM == Liberer le port 8000 si deja utilise ==
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo [INFO] Port 8000 occupe par le processus %%p, fermeture...
    taskkill /PID %%p /F >nul 2>nul
)

call venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000
pause
