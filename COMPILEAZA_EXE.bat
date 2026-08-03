@echo off
chcp 65001 >nul
title Compilare ExtractorPoze.exe
echo ============================================
echo   Compilare ExtractorPoze.exe
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [EROARE] Python nu este instalat sau nu este in PATH.
    echo Descarca Python de la: https://www.python.org/downloads/
    echo Asigura-te ca bifezi "Add Python to PATH" la instalare.
    pause
    exit /b 1
)

echo [1/3] Instalare PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [EROARE] Nu s-a putut instala PyInstaller.
    pause
    exit /b 1
)

echo [2/3] Compilare aplicatie...
pyinstaller --onefile --windowed --name "ExtractorPoze" extractor_poze.py
if errorlevel 1 (
    echo [EROARE] Compilarea a esuat.
    pause
    exit /b 1
)

echo.
echo [3/3] Gata! Fisierul ExtractorPoze.exe se afla in folderul "dist\".
echo.
echo Poti copia ExtractorPoze.exe oriunde vrei si il rulezi direct.
echo.
pause
