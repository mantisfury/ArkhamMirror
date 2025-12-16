@echo off
setlocal enabledelayedexpansion
title ArkhamMirror Setup Wizard

echo.
 echo  ================================================================
 echo     ArkhamMirror Setup Wizard
 echo  ================================================================
 echo.

:: ====================================================================
:: PRE-FLIGHT: Disk Space Check
:: ====================================================================
 echo [1/8] Checking disk space...

:: Get free space on current drive using PowerShell (reliable across locales)
for /f %%a in ('powershell -NoProfile -Command "[math]::Floor((Get-PSDrive -Name $PWD.Drive.Name).Free / 1GB)"') do set FREE_GB=%%a
if not defined FREE_GB set FREE_GB=0

if %FREE_GB% LSS 15 (
    echo [X] Insufficient disk space. Need 15GB free, found ~%FREE_GB%GB.
    echo     Please free up disk space and try again.
    pause
    exit /b 1
)
 echo     [OK] Disk space sufficient (~%FREE_GB%GB free^)

:: ====================================================================
:: PRE-FLIGHT: RAM Check
:: ====================================================================
 echo [2/8] Checking RAM...

:: Get total RAM using PowerShell (reliable across locales, replaces fragile wmic string parsing)
for /f %%a in ('powershell -NoProfile -Command "[math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)"') do set RAM_GB=%%a
if not defined RAM_GB set RAM_GB=0

if %RAM_GB% LSS 8 (
    echo [X] Insufficient RAM. Need 8GB minimum, found ~%RAM_GB%GB.
    echo     ArkhamMirror requires at least 8GB RAM to run.
    pause
    exit /b 1
)
if %RAM_GB% LSS 16 (
    echo     [!] RAM is below recommended 16GB. Some features may be slow.
) else (
    echo     [OK] RAM sufficient (~%RAM_GB%GB^)
)

:: ====================================================================
:: PRE-FLIGHT: Port Check
:: ====================================================================
 echo [3/8] Checking required ports...

 set PORTS_OK=1
 for %%P in (3000 5435 6343 6344 6380 8000) do (
    netstat -an 2>nul | findstr ":%%P " | findstr "LISTENING" >nul
    if !errorlevel! equ 0 (
        echo     [X] Port %%P is already in use
        set PORTS_OK=0
    )
)

if %PORTS_OK% equ 0 (
    echo.
    echo     Some required ports are in use. Please close the conflicting
    echo     applications and try again.
    echo.
    echo     Common culprits:
    echo       - Port 3000: React dev servers, other web apps
    echo       - Port 8000: Django, FastAPI, other Python apps
    pause
    exit /b 1
)
 echo     [OK] All required ports available

:: ====================================================================
:: PRE-FLIGHT: Existing Installation Check
:: ====================================================================
 echo [4/8] Checking for existing installation...

if exist ".arkham_install_state.json" (
    echo     [!] Previous installation detected.
    echo.
    choice /c FRU /m "     [F]resh install, [R]esume previous, or [U]pdate"
    if errorlevel 3 goto :update_mode
    if errorlevel 2 goto :resume_mode
    if errorlevel 1 goto :fresh_mode
)
goto :fresh_mode

:fresh_mode
 echo     Starting fresh installation...
if exist "venv" rmdir /s /q "venv" 2>nul
if exist ".arkham_install_state.json" del ".arkham_install_state.json" 2>nul
goto :check_wsl

:resume_mode
 echo     Resuming previous installation...
goto :check_python

:update_mode
 echo     Update mode - keeping existing data...
goto :check_python

:: ====================================================================
:: WSL2 CHECK (Required for Docker Desktop)
:: ====================================================================
:check_wsl
 echo [5/8] Checking WSL2 (required for Docker)...

 wsl --status >nul 2>&1
if %errorlevel% neq 0 (
    echo     [!] WSL2 not installed. Installing now...
    echo.
    echo     NOTE: This will require a system restart.
    echo.

    wsl --install

    if %errorlevel% neq 0 (
        echo     [X] WSL2 installation failed. Please install manually:
        echo         1. Open PowerShell as Administrator
        echo         2. Run: wsl --install
        echo         3. Restart your computer
        echo         4. Run this setup again
        pause
        exit /b 1
    )

    :: Save state for resume after restart
    echo {"restart_required": true, "restart_reason": "wsl2"} > .arkham_install_state.json

    echo.
    echo     [!] WSL2 installed. You MUST restart your computer.
    echo         After restart, run this setup script again.
    echo.
    pause
    exit /b 0
)
 echo     [OK] WSL2 is available

:: ====================================================================
:: PYTHON CHECK AND INSTALLATION
:: ====================================================================
:check_python
 echo [6/8] Checking Python...

:: Try multiple ways to find Python
 set PYTHON_CMD=

:: Try py launcher (most reliable on Windows)
 py -3.11 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.11
    goto :python_found
)

 py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.12
    goto :python_found
)

 py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3
    goto :python_found
)

:: Try python command
 python --version 2>&1 | findstr /r "3\.1[1-9]" >nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :python_found
)

:: Try explicit paths
 for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
) do (
    if exist %%~P (
        set PYTHON_CMD=%%~P
        goto :python_found
    )
)

:: Python not found - install it
 echo     [!] Python 3.11+ not found. Installing...

:: Try winget first
 winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo     Installing Python via winget...
    winget install -e --id Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements

    if %errorlevel% equ 0 (
        :: winget install succeeded, but PATH not updated in this session
        :: Use explicit path
        set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
        if exist "!PYTHON_CMD!" goto :python_found
    )
)

:: Fallback: PowerShell direct download
 echo     [!] Trying PowerShell installer...
 powershell -ExecutionPolicy Bypass -Command ^
    "$url = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe'; ^
     $out = \"$env:TEMP\python-installer.exe\"; ^
     Write-Host 'Downloading Python 3.11.9...'; ^
     [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ^
     Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing; ^
     Write-Host 'Installing (this may take a minute)...'; ^
     Start-Process -FilePath $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1' -Wait; ^
     Remove-Item $out -ErrorAction SilentlyContinue"

:: Check if it worked
 set PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if exist "%PYTHON_CMD%" goto :python_found

:: Last resort: open browser
 echo     [X] Automatic installation failed.
 echo.
 start https://www.python.org/downloads/
 echo     Please download and install Python 3.11+ from the browser window.
 echo     IMPORTANT: Check "Add Python to PATH" during installation!
 echo.
 echo     Press any key after Python is installed...
 pause >nul

:: Try again
 py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3
    goto :python_found
)

 echo     [X] Python still not found. Please restart your computer and try again.
 pause
 exit /b 1

:python_found
 echo     [OK] Python found: %PYTHON_CMD%

:: ====================================================================
:: DOCKER CHECK AND INSTALLATION
:: ====================================================================
 echo [7/8] Checking Docker...

 docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo     [!] Docker not found. Installing...

    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo     Installing Docker Desktop via winget...
        winget install -e --id Docker.DockerDesktop --silent --accept-package-agreements --accept-source-agreements
    ) else (
        echo     [!] Please install Docker Desktop manually.
        start https://www.docker.com/products/docker-desktop/
        echo.
        echo     Press any key after Docker Desktop is installed...
        pause >nul
    )
)

:: Verify Docker is running
 docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo     [!] Docker is installed but not running.
    echo         Please start Docker Desktop and wait for it to fully load.
    echo.
    echo     Press any key when Docker Desktop shows "Engine running"...
    pause >nul

    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo     [X] Docker still not responding. Please ensure Docker Desktop
        echo         is fully started and try again.
        pause
        exit /b 1
    )
)
 echo     [OK] Docker is ready

:: ====================================================================
:: LM STUDIO CHECK
:: ====================================================================
 echo [8/8] Checking LM Studio...

:: Try to connect to LM Studio API
 powershell -Command "(Invoke-WebRequest -Uri 'http://localhost:1234/v1/models' -UseBasicParsing -TimeoutSec 5).StatusCode" >nul 2>&1
if %errorlevel% neq 0 (
    echo     [!] LM Studio server not responding.
    echo.
    echo     Please ensure:
    echo       1. LM Studio is installed (from lmstudio.ai^)
    echo       2. A model is downloaded (recommend: qwen3-vl-8b^)
    echo       3. The server is started (click "Start Server" in LM Studio^)
    echo.
    echo     The AI wizard needs LM Studio to provide guidance.
    echo     You can continue without it, but the experience won't be as good.
    echo.
    choice /c YN /m "     Continue without AI assistance"
    if errorlevel 2 (
        echo     Please start LM Studio and run this setup again.
        pause
        exit /b 0
    )
    echo     Continuing in text-only mode...
    set NO_AI=1
) else (
    echo     [OK] LM Studio is responding
    set NO_AI=0
)

:: ====================================================================
:: HAND OFF TO PYTHON AI WIZARD
:: ====================================================================
 echo.
 echo  ================================================================
 echo     Pre-flight checks complete! Launching AI Setup Wizard...
 echo  ================================================================
 echo.

if "%NO_AI%"=="1" (
    %PYTHON_CMD% scripts\ai_installer.py --no-ai
) else (
    %PYTHON_CMD% scripts\ai_installer.py
)

if %errorlevel% neq 0 (
    echo.
    echo [X] Installation encountered an error.
    echo     Check the output above for details.
    echo     You can run this script again to resume.
    pause
    exit /b 1
)

 echo.
 echo  ================================================================
 echo     Installation Complete!
 echo  ================================================================
 echo.
pause
