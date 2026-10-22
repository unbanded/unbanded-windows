@echo off
REM Compiler le patcher Python en executable Windows (Nuitka)
cd /d "%~dp0"

where python >nul 2>&1 || (echo Python not found on PATH & exit /b 1)

REM Installer Nuitka si absent
python -c "import nuitka" >nul 2>&1
if errorlevel 1 (
    echo Installation de Nuitka...
    python -m pip install --upgrade nuitka || (echo Echec installation Nuitka & exit /b 1)
)

REM Installer imageio pour la conversion d'icone PNG
python -c "import imageio" >nul 2>&1
if errorlevel 1 (
    python -m pip install imageio || (echo Echec installation imageio & exit /b 1)
)

echo Compilation en cours...
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-disable-console ^
    --enable-plugin=tk-inter ^
    --include-data-file=logo.png=logo.png ^
    --windows-icon-from-ico=logo.png ^
    --output-filename=UnbandedPatcher.exe ^
    --remove-output ^
    main.py

if errorlevel 1 (
    echo Compilation echouee.
    exit /b 1
)

echo Compilation terminee: UnbandedPatcher.exe
pause