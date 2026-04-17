@echo off
cd /d "%~dp0"

echo.
echo  ============================================
echo   YumsCUT - Export des cookies YouTube
echo  ============================================
echo.
echo  Ce script exporte vos cookies YouTube dans cookies.txt
echo  pour eviter le blocage "Sign in to confirm you're not a bot".
echo.
echo  IMPORTANT : Fermez completement votre navigateur avant
echo  de continuer (Chrome, Opera, Edge...).
echo.
pause

REM Essayer Chrome
set BROWSER_FOUND=0
if exist "%LOCALAPPDATA%\Google\Chrome\User Data" (
    echo  Tentative avec Chrome...
    call venv\Scripts\activate.bat >nul 2>nul
    yt-dlp --cookies-from-browser chrome --cookies cookies.txt --skip-download "https://www.youtube.com" >nul 2>&1
    if exist "cookies.txt" (
        set BROWSER_FOUND=1
        echo  [OK] Cookies Chrome exportes dans cookies.txt
        goto SUCCESS
    )
    echo  [INFO] Chrome echoue, essai suivant...
)

REM Essayer Opera
if exist "%APPDATA%\Opera Software\Opera Stable" (
    echo  Tentative avec Opera...
    yt-dlp --cookies-from-browser opera --cookies cookies.txt --skip-download "https://www.youtube.com" >nul 2>&1
    if exist "cookies.txt" (
        set BROWSER_FOUND=1
        echo  [OK] Cookies Opera exportes dans cookies.txt
        goto SUCCESS
    )
    echo  [INFO] Opera echoue, essai suivant...
)

REM Essayer Edge
if exist "%LOCALAPPDATA%\Microsoft\Edge\User Data" (
    echo  Tentative avec Edge...
    yt-dlp --cookies-from-browser edge --cookies cookies.txt --skip-download "https://www.youtube.com" >nul 2>&1
    if exist "cookies.txt" (
        set BROWSER_FOUND=1
        echo  [OK] Cookies Edge exportes dans cookies.txt
        goto SUCCESS
    )
    echo  [INFO] Edge echoue, essai suivant...
)

REM Essayer Firefox
if exist "%APPDATA%\Mozilla\Firefox\Profiles" (
    echo  Tentative avec Firefox...
    yt-dlp --cookies-from-browser firefox --cookies cookies.txt --skip-download "https://www.youtube.com" >nul 2>&1
    if exist "cookies.txt" (
        set BROWSER_FOUND=1
        echo  [OK] Cookies Firefox exportes dans cookies.txt
        goto SUCCESS
    )
)

echo.
echo  [ERREUR] Impossible d'exporter les cookies automatiquement.
echo.
echo  Solutions :
echo   1. Verifiez que votre navigateur est bien ferme et relancez ce script.
echo   2. Installez l'extension "Get cookies.txt LOCALLY" dans Chrome,
echo      exportez les cookies de youtube.com et enregistrez le fichier
echo      sous le nom cookies.txt dans le dossier de YumsCUT.
echo.
pause
exit /b 1

:SUCCESS
echo.
echo  ============================================
echo   Export termine !
echo  ============================================
echo.
echo  YumsCUT utilisera automatiquement cookies.txt au prochain demarrage.
echo  Relancez start.bat si l'application etait deja ouverte.
echo.
echo  Note : les cookies expirent apres quelques semaines.
echo  Relancez ce script si l'erreur "Sign in" reapparait.
echo.
pause
