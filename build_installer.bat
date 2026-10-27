@echo off
REM Build script for Encrypted Messaging Installer
REM Requires NSIS (Nullsoft Scriptable Install System) installed
REM Download from: https://nsis.sourceforge.io/Download

set PROJECT_DIR=%CD%
set NSIS_PATH="C:\Program Files (x86)\NSIS\makensis.exe"
set OUTPUT_DIR=%PROJECT_DIR%\dist

echo Building Encrypted Messaging Installer...
echo Project directory: %PROJECT_DIR%
echo Output directory: %OUTPUT_DIR%

REM Check if NSIS is installed
if not exist %NSIS_PATH% (
    echo NSIS not found at %NSIS_PATH%
    echo Please install NSIS from https://nsis.sourceforge.io/Download
    exit /b 1
)

REM Check if executables exist
if not exist "%PROJECT_DIR%\dist\encrypted-messaging-gui\encrypted-messaging-gui.exe" (
    echo GUI executable not found. Please run build first.
    exit /b 1
)

if not exist "%PROJECT_DIR%\dist\encrypted-messaging-tui\encrypted-messaging-tui.exe" (
    echo TUI executable not found. Please run build first.
    exit /b 1
)

if not exist "%PROJECT_DIR%\dist\encrypted-messaging-server\encrypted-messaging-server.exe" (
    echo Server executable not found. Please run build first.
    exit /b 1
)

REM Create LICENSE.txt if it doesn't exist
if not exist "%PROJECT_DIR%\LICENSE.txt" (
    echo MIT License > "%PROJECT_DIR%\LICENSE.txt"
    echo. >> "%PROJECT_DIR%\LICENSE.txt"
    echo Copyright (c) 2024 Encrypted Messaging Project >> "%PROJECT_DIR%\LICENSE.txt"
    echo. >> "%PROJECT_DIR%\LICENSE.txt"
    echo Permission is hereby granted... >> "%PROJECT_DIR%\LICENSE.txt"
)

REM Run NSIS
echo Running NSIS compiler...
%NSIS_PATH% /DVERSION=1.0.0 "%PROJECT_DIR%\installer.nsi"

if errorlevel 1 (
    echo NSIS compilation failed!
    exit /b 1
)

echo.
echo Installer created successfully!
echo Output: %OUTPUT_DIR%\EncryptedMessaging-Setup.exe
pause