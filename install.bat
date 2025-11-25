@echo off
echo ==========================================
echo      ArkhamMirror Installation Script
echo ==========================================
echo.

REM Check for Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not installed or not in PATH.
    echo Please install Docker Desktop and try again.
    pause
    exit /b
)

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b
)

echo [1/4] Creating Virtual Environment...
if not exist "venv" (
    python -m venv venv
    echo    - venv created.
) else (
    echo    - venv already exists.
)

echo [2/4] Installing Dependencies...
call .\venv\Scripts\activate
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b
)

echo [3/4] Starting Infrastructure (Docker)...
docker compose up -d
if %errorlevel% neq 0 (
    echo [ERROR] Failed to start Docker containers.
    pause
    exit /b
)

echo [4/4] Setting up Environment...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo    - Created .env from example.
    ) else (
        echo    - [WARNING] .env.example not found. Please create .env manually.
    )
)

echo.
echo ==========================================
echo      Installation Complete!
echo ==========================================
echo.
echo To start the application:
echo   1. Run 'streamlit run streamlit_app/Search.py'
echo   2. Run 'run_workers.bat' in a new terminal
echo.
pause
