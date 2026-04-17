@echo off
cd /d "%~dp0"

REM == Liberer le port 2309 si deja utilise ==
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":2309 " ^| findstr "LISTENING"') do (
    echo [INFO] Port 2309 occupe, fermeture de l'instance precedente...
    taskkill /PID %%p /F >nul 2>nul
)

REM == Detecter l'adresse IP locale ==
call venv\Scripts\activate >nul 2>nul
python get_ip.py > "%TEMP%\yc_ip.txt" 2>nul
set /p LOCAL_IP=<"%TEMP%\yc_ip.txt"
del "%TEMP%\yc_ip.txt" >nul 2>nul
if "%LOCAL_IP%"=="" set LOCAL_IP=localhost

echo.
echo  ============================================
echo   YumsCUT est en cours de demarrage...
echo  ============================================
echo.
echo  Votre application sera accessible a :
echo.
echo      http://%LOCAL_IP%:2309
echo.
echo  Le navigateur va s'ouvrir automatiquement.
echo.
echo  [!] NE FERMEZ PAS cette fenetre.
echo      Minimisez-la pour garder YumsCUT actif.
echo.
echo  Pour ARRETER YumsCUT : fermez cette fenetre.
echo  Pour RELANCER        : double-cliquez sur start.bat.
echo.
echo  ============================================
echo.

REM == Ouvrir le navigateur apres 3 secondes (non-bloquant) ==
start "" powershell -WindowStyle Hidden -Command "Start-Sleep 3; Start-Process 'http://%LOCAL_IP%:2309'"

REM == Lancer l'application (bloquant) ==
uvicorn main:app --host 0.0.0.0 --port 2309
pause
