@echo off
echo Starting Ingest Watcher...
call ./venv/Scripts/activate
cmd /k "python -m backend.workers.ingest_worker --watch"
