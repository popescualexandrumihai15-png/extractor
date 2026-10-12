@echo off
chcp 65001 >nul
title Instalare script Subtitrari RO pentru DaVinci Resolve
set "DEST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit"
if not exist "%DEST%" mkdir "%DEST%"
copy /Y "%~dp0davinci_resolve\Subtitrari RO.py" "%DEST%\" >nul
if errorlevel 1 (
    echo [EROARE] Copierea a esuat.
    pause
    exit /b 1
)
echo Gata. In DaVinci Resolve: Workspace ^> Scripts ^> Edit ^> Subtitrari RO
echo Resolve are nevoie de Python 3 instalat (https://www.python.org/downloads/).
pause
