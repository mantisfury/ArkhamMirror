@echo off
REM ============================================================================
REM  NUKE IT FROM ORBIT - Forensic Data Wipe for ArkhamMirror
REM ============================================================================
REM
REM  "I say we take off and nuke the entire site from orbit.
REM   It's the only way to be sure."
REM                                       - Ellen Ripley, Aliens (1986)
REM
REM  This script performs a SECURE WIPE of all ArkhamMirror data:
REM    - Overwrites files with random data before deletion
REM    - Destroys all Docker volumes and bind-mount data
REM    - Clears all Reflex state and cache
REM    - Recreates fresh infrastructure
REM
REM  WARNING: This operation is IRREVERSIBLE. There is no recovery.
REM
REM ============================================================================

title NUKE IT FROM ORBIT - ArkhamMirror Forensic Wipe

echo.
echo  ============================================================
echo.
echo        _   _ _   _ _  _______   ___ _____
echo       ^| \ ^| ^| ^| ^| ^| ^|/ / ____^| ^|_ _^|_   _^|
echo       ^|  \^| ^| ^| ^| ^| ' /^| ^|__     ^| ^|  ^| ^|
echo       ^| . ` ^| ^| ^| ^| . \^| __ \    ^| ^|  ^| ^|
echo       ^| ^|\  ^| ^|_^| ^| ^|\ \ ___) ^|  ^| ^|  ^| ^|
echo       ^|_^| \_^|\___/^|_^| \_\____/  ^|___^| ^|_^|
echo.
echo        _____ ____   ___  __  __    ___  ____  ____ ___ _____
echo       ^|  _  ^|  _ \ / _ \^|  \/  ^|  / _ \^|  _ \^| __ )_ _^|_   _^|
echo       ^| ^|_) ^| ^|_) ^| ^| ^| ^| ^|\/^| ^| ^| ^| ^| ^| ^|_) ^|  _ \^| ^|  ^| ^|
echo       ^|  __/^|  _ ^< ^| ^|_^| ^| ^|  ^| ^| ^| ^|_^| ^|  _ ^< ^|_) ^| ^|  ^| ^|
echo       ^|_^|   ^|_^| \_\\___/^|_^|  ^|_^|  \___/^|_^| \_\____/___^| ^|_^|
echo.
echo  ============================================================
echo.
echo     "It's the only way to be sure."
echo.
echo  ============================================================
echo.

REM Check if Python is available
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Check if the forensic_wipe.py script exists
if not exist "%SCRIPT_DIR%scripts\forensic_wipe.py" (
    echo [ERROR] scripts\forensic_wipe.py not found.
    echo Please run this script from the ArkhamMirror root directory.
    pause
    exit /b 1
)

echo This will PERMANENTLY DESTROY all ArkhamMirror data.
echo.
echo Press any key to continue, or Ctrl+C to abort...
pause >nul

REM Run the forensic wipe script
cd /d "%SCRIPT_DIR%"
python scripts\forensic_wipe.py --confirm

echo.
if %ERRORLEVEL% equ 0 (
    echo ============================================================
    echo  MISSION ACCOMPLISHED - Data has been nuked from orbit.
    echo ============================================================
) else (
    echo ============================================================
    echo  MISSION ABORTED or encountered errors.
    echo ============================================================
)

echo.
pause
