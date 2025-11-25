@echo off
echo Starting Arkham Worker...
REM Ensure we are in the right directory
cd /d "%~dp0"

REM Use the virtual environment python directly
start "Arkham Worker" .\venv\Scripts\python.exe run_rq_worker.py

