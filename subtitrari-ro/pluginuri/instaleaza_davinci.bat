@echo off
chcp 65001 >nul
title Instalare script Subtitrari RO pentru DaVinci Resolve
set "DEST=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
if not exist "%DEST%" mkdir "%DEST%"
set "VECHI=%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit\Subtitrari RO.py"
if exist "%VECHI%" del "%VECHI%"
copy /Y "%~dp0davinci_resolve\Subtitrari RO.py" "%DEST%\" >nul
if errorlevel 1 (
    echo [EROARE] Copierea a esuat.
    pause
    exit /b 1
)
echo Gata. In DaVinci Resolve: Workspace ^> Scripts ^> Subtitrari RO
echo Resolve are nevoie de Python 3 instalat (https://www.python.org/downloads/).
pause
