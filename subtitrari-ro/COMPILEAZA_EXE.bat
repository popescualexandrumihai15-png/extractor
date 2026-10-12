@echo off
chcp 65001 >nul
title Compilare SubtitrariRO.exe
cd /d "%~dp0"
echo ============================================
echo   Compilare SubtitrariRO.exe
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [EROARE] Python nu este instalat sau nu este in PATH.
    echo Descarca Python de la: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Instalare componente si PyInstaller...
python -m pip install --quiet -r requirements.txt pyinstaller
if errorlevel 1 (
    echo [EROARE] Instalarea a esuat.
    pause
    exit /b 1
)

echo [2/3] Compilare aplicatie (cateva minute)...
pyinstaller --noconfirm --windowed --name "SubtitrariRO" ^
    --collect-all customtkinter ^
    --collect-data faster_whisper ^
    --collect-binaries ctranslate2 ^
    porneste.py
if errorlevel 1 (
    echo [EROARE] Compilarea a esuat.
    pause
    exit /b 1
)

if exist ffmpeg xcopy /E /I /Y ffmpeg "dist\SubtitrariRO\ffmpeg" >nul

echo.
echo [3/3] Gata! Aplicatia este in folderul "dist\SubtitrariRO\".
echo Porneste SubtitrariRO.exe. Copiaza tot folderul, nu doar fisierul .exe.
echo Daca nu ai pus ffmpeg langa proiect, pune folderul "ffmpeg" (cu bin\ffmpeg.exe)
echo in "dist\SubtitrariRO\".
echo.
pause
