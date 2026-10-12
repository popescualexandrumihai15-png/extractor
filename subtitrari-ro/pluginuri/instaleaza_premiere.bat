@echo off
chcp 65001 >nul
title Instalare panou Subtitrari RO pentru Premiere Pro
set "SURSA=%~dp0premiere_pro\com.subtitrari.ro"
set "DEST=%APPDATA%\Adobe\CEP\extensions\com.subtitrari.ro"

echo [1/2] Copiez panoul in %DEST% ...
xcopy /E /I /Y "%SURSA%" "%DEST%" >nul
if errorlevel 1 (
    echo [EROARE] Copierea a esuat.
    pause
    exit /b 1
)

echo [2/2] Permit panourile nesemnate (PlayerDebugMode) ...
for %%V in (9 10 11 12) do reg add "HKCU\Software\Adobe\CSXS.%%V" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul

echo.
echo Gata. Reporneste Premiere Pro, apoi deschide: Window ^> Extensions ^> Subtitrari RO
pause
