@echo off
cd /d "%~dp0"

echo.
echo  ============================================
echo   YumsCUT - Installation automatique
echo  ============================================
echo.

REM == 1. Verifier Python ==
python --version 1>nul 2>nul
if errorlevel 1 goto NO_PYTHON
echo [OK] Python detecte.
goto CHECK_FFMPEG

:NO_PYTHON
echo [ERREUR] Python n'est pas installe ou absent du PATH.
echo.
echo Installez Python 3.10 ou superieur depuis :
echo   https://www.python.org/downloads/
echo.
echo IMPORTANT : cochez "Add Python to PATH" lors de l'installation.
pause
exit /b 1

REM == 2. Verifier ffmpeg ==
:CHECK_FFMPEG
ffmpeg -version 1>nul 2>nul
if errorlevel 1 goto NO_FFMPEG
echo [OK] ffmpeg detecte.
goto CHECK_VENV

:NO_FFMPEG
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

REM == 3. Creer le venv ==
:CHECK_VENV
if exist "venv\" goto VENV_EXISTS
echo.
echo [1/4] Creation de l'environnement virtuel Python...
python -m venv venv
if errorlevel 1 goto VENV_ERROR
echo [OK] Environnement virtuel cree.
goto INSTALL_DEPS

:VENV_ERROR
echo [ERREUR] Impossible de creer le venv.
pause
exit /b 1

:VENV_EXISTS
echo [OK] Environnement virtuel deja present.

REM == 4. Installer les dependances ==
:INSTALL_DEPS
echo.
echo [2/4] Installation des dependances (peut prendre quelques minutes)...
call venv\Scripts\activate.bat
pip install -q --no-cache-dir -r requirements.txt
pip install -q -U yt-dlp
echo [OK] Dependances installees.

REM == 5. Configurer .env ==
if exist ".env" goto ENV_EXISTS
echo.
echo [3/4] Creation du fichier de configuration .env...
set APPDIR=%~dp0
(
    echo VAPID_PRIVATE_KEY=REMPLACER_PAR_CLE_GENEREE_CI_DESSOUS
    echo VAPID_PUBLIC_KEY=REMPLACER_PAR_CLE_GENEREE_CI_DESSOUS
    echo VAPID_CLAIMS_EMAIL=votre@email.com
    echo.
    echo DB_PATH=%APPDIR%data\app.db
    echo DATA_DIR=%APPDIR%data
    echo FONT_PATH=C:\Windows\Fonts\arialbd.ttf
) > .env
echo [OK] Fichier .env cree.
goto GEN_KEYS

:ENV_EXISTS
echo [OK] Fichier .env deja present.

REM == 6. Generer les cles VAPID ==
:GEN_KEYS
echo.
echo [4/4] Generation des cles VAPID...
echo.
echo  +----------------------------------------------------------+
echo  ^|  Copiez ces valeurs dans le fichier .env qui va s'ouvrir ^|
echo  +----------------------------------------------------------+
echo.
python generate_keys.py
echo.

REM == 7. Ouvrir .env ==
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
