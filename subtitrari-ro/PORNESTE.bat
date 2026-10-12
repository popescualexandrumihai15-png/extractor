@echo off
chcp 65001 >nul
title Subtitrari RO
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [EROARE] Python nu este instalat sau nu este in PATH.
    echo Descarca Python 3.10 sau mai nou de la: https://www.python.org/downloads/
    echo La instalare bifeaza "Add Python to PATH".
    pause
    exit /b 1
)

echo Verific componentele (prima data dureaza cateva minute)...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [EROARE] Nu am putut instala componentele. Verifica conexiunea la internet.
    pause
    exit /b 1
)

start "" pythonw -m subtitrari_ro
