@echo off
cd /d "%~dp0"

echo.
echo  ============================================
echo   YumsCUT - Desinstallation
echo  ============================================
echo.
echo  ATTENTION : Cette operation va supprimer :
echo    - L'application YumsCUT et tous ses fichiers
echo    - Vos videos traitees et la base de donnees
echo    - L'environnement Python (venv)
echo.
echo  Cette action est IRREVERSIBLE.
echo.
set /p CONFIRM=  Tapez OUI pour confirmer :
if /i "%CONFIRM%" neq "OUI" goto CANCEL

echo.
echo  Arret de YumsCUT si en cours d'execution...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":2309 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>nul
)

echo  Suppression des fichiers en cours...
set APP_DIR=%~dp0

REM On se deplace hors du dossier avant de le supprimer
cd /d %TEMP%

powershell -NoProfile -Command "Start-Sleep 1; Remove-Item -Path '%APP_DIR%' -Recurse -Force -ErrorAction SilentlyContinue"

echo.
echo  YumsCUT a ete desinstalle avec succes.
echo  Vous pouvez fermer cette fenetre.
echo.
pause
exit /b 0

:CANCEL
echo.
echo  Desinstallation annulee.
echo.
pause
