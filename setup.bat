@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  ============================================
echo   YumsCUT - Installation automatique
echo  ============================================
echo.

REM ── 1. Verifier Python ──────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe ou absent du PATH.
    echo.
    echo Installez Python 3.10 ou superieur depuis :
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT : cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER% detecte.

REM ── 2. Verifier ffmpeg ───────────────────────────────────────────────────────
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERREUR] ffmpeg n'est pas installe ou absent du PATH.
    echo.
    echo Option 1 - Avec winget (Windows 11 recommande) :
    echo   winget install Gyan.FFmpeg
    echo.
    echo Option 2 - Telechargement manuel :
    echo   https://www.gyan.dev/ffmpeg/builds/
    echo   Decompressez l'archive et ajoutez le dossier bin\ au PATH.
    echo.
    pause
    exit /b 1
)
echo [OK] ffmpeg detecte.

REM ── 3. Creer le venv ─────────────────────────────────────────────────────────
if not exist "venv\" (
    echo.
    echo [1/4] Creation de l'environnement virtuel Python...
    python -m venv venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer le venv.
        pause
        exit /b 1
    )
    echo [OK] Environnement virtuel cree.
) else (
    echo [OK] Environnement virtuel deja present.
)

REM ── 4. Installer les dependances ─────────────────────────────────────────────
echo.
echo [2/4] Installation des dependances (peut prendre quelques minutes)...
call venv\Scripts\activate.bat
pip install -q --no-cache-dir -r requirements.txt
pip install -q -U yt-dlp
echo [OK] Dependances installees (yt-dlp : derniere version).

REM ── 5. Configurer .env ───────────────────────────────────────────────────────
if not exist ".env" (
    echo.
    echo [3/4] Creation du fichier de configuration .env...

    REM Determiner la police : Arial Bold est presente sur tout Windows
    set FONT=C:\Windows\Fonts\arialbd.ttf

    REM Ecrire le .env avec les chemins Windows relatifs au dossier du projet
    (
        echo VAPID_PRIVATE_KEY=REMPLACER_PAR_CLE_GENEREE_CI_DESSOUS
        echo VAPID_PUBLIC_KEY=REMPLACER_PAR_CLE_GENEREE_CI_DESSOUS
        echo VAPID_CLAIMS_EMAIL=votre@email.com
        echo.
        echo DB_PATH=%~dp0data\app.db
        echo DATA_DIR=%~dp0data
        echo FONT_PATH=!FONT!
    ) > .env

    echo [OK] Fichier .env cree.
) else (
    echo [OK] Fichier .env deja present, configuration conservee.
)

REM ── 6. Generer les cles VAPID ────────────────────────────────────────────────
echo.
echo [4/4] Generation des cles VAPID pour les notifications push...
echo.
echo  ┌─────────────────────────────────────────────────────────┐
echo  │  Copiez ces valeurs dans le fichier .env qui va s'ouvrir│
echo  └─────────────────────────────────────────────────────────┘
echo.
python generate_keys.py
echo.

REM ── 7. Ouvrir .env dans le Bloc-notes ────────────────────────────────────────
echo  Ouverture de .env dans le Bloc-notes...
echo  Remplacez REMPLACER_PAR_CLE_GENEREE_CI_DESSOUS par les cles ci-dessus.
echo  Remplacez aussi votre@email.com par votre adresse email.
echo.
start notepad .env

echo  ============================================
echo   Installation terminee !
echo  ============================================
echo.
echo  Une fois .env rempli et sauvegarde, lancez start.bat
echo  puis ouvrez http://localhost:8000 dans votre navigateur.
echo.
pause
