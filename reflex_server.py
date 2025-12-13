#!/usr/bin/env python
"""
Reflex Server Manager - Easily control the Reflex frontend and backend.

Usage:
    python reflex_server.py start   # Start both frontend and backend
    python reflex_server.py stop    # Stop both frontend and backend
    python reflex_server.py restart # Restart both
    python reflex_server.py status  # Check if running
"""

import os
import sys
import subprocess
import time
import psutil
from pathlib import Path

# Add project root to path for central config
sys.path.insert(0, str(Path(__file__).parent))

from config import BACKEND_PORT, FRONTEND_PORT, ARKHAM_REFLEX_PATH

REFLEX_DIR = ARKHAM_REFLEX_PATH
PID_FILE = Path(__file__).parent / ".reflex.pid"
PORT_BACKEND = BACKEND_PORT
PORT_FRONTEND = FRONTEND_PORT


def get_process_on_port(port):
    """Find process using a specific port."""
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr.port == port and conn.status == "LISTEN":
            try:
                proc = psutil.Process(conn.pid)
                return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return None


def is_running():
    """Check if Reflex server is running."""
    backend = get_process_on_port(PORT_BACKEND)
    frontend = get_process_on_port(PORT_FRONTEND)

    return {
        "backend": backend,
        "frontend": frontend,
        "running": backend is not None or frontend is not None,
    }


def get_reflex_processes():
    """Get all Python processes that look like Reflex."""
    reflex_procs = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            if proc.info["name"] == "python.exe" or proc.info["name"] == "python":
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "reflex" in cmdline.lower() and "reflex_server.py" not in cmdline:
                    reflex_procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return reflex_procs


def start():
    """Start Reflex server."""
    status = is_running()

    if status["running"]:
        print("[!]  Reflex server already running!")
        print_status()
        return

    print("[>>] Starting Reflex server...")
    print(f"   Directory: {REFLEX_DIR}")
    print(f"   Backend will be on: http://localhost:{PORT_BACKEND}")
    print(f"   Frontend will be on: http://localhost:{PORT_FRONTEND}")
    print()

    # Change to reflex directory
    os.chdir(REFLEX_DIR)

    # Start Reflex (detached process)
    if sys.platform == "win32":
        # Windows: Use START to launch in new window
        subprocess.Popen(
            ["start", "cmd", "/k", sys.executable, "-m", "reflex", "run"],
            shell=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    else:
        # Linux/Mac: Use nohup
        subprocess.Popen(
            ["nohup", "python", "-m", "reflex", "run", "&"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    print("... Waiting for server to start...")
    for i in range(30):
        time.sleep(1)
        status = is_running()
        if status["backend"]:
            print(f"[OK] Backend started (PID: {status['backend'].pid})")
            break

    for i in range(30):
        time.sleep(1)
        status = is_running()
        if status["frontend"]:
            print(f"[OK] Frontend started (PID: {status['frontend'].pid})")
            break

    print()
    print_status()


def stop():
    """Stop Reflex server."""
    print("[STOP] Stopping Reflex server...")

    status = is_running()
    stopped = []

    # Stop backend
    if status["backend"]:
        print(f"   Stopping backend (PID: {status['backend'].pid})...")
        try:
            status["backend"].terminate()
            status["backend"].wait(timeout=5)
            stopped.append(f"Backend (PID: {status['backend'].pid})")
        except psutil.TimeoutExpired:
            print("   [!]  Backend didn't stop gracefully, forcing...")
            status["backend"].kill()
            stopped.append(f"Backend (PID: {status['backend'].pid}) [FORCED]")

    # Stop frontend
    if status["frontend"]:
        print(f"   Stopping frontend (PID: {status['frontend'].pid})...")
        try:
            status["frontend"].terminate()
            status["frontend"].wait(timeout=5)
            stopped.append(f"Frontend (PID: {status['frontend'].pid})")
        except psutil.TimeoutExpired:
            print("   [!]  Frontend didn't stop gracefully, forcing...")
            status["frontend"].kill()
            stopped.append(f"Frontend (PID: {status['frontend'].pid}) [FORCED]")

    # Also check for any other Reflex processes
    other_procs = get_reflex_processes()
    for proc in other_procs:
        if proc.pid not in [
            status["backend"].pid if status["backend"] else None,
            status["frontend"].pid if status["frontend"] else None,
        ]:
            print(f"   Found orphaned Reflex process (PID: {proc.pid}), stopping...")
            try:
                proc.terminate()
                proc.wait(timeout=5)
                stopped.append(f"Orphaned process (PID: {proc.pid})")
            except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                try:
                    proc.kill()
                    stopped.append(f"Orphaned process (PID: {proc.pid}) [FORCED]")
                except psutil.NoSuchProcess:
                    pass

    if PID_FILE.exists():
        PID_FILE.unlink()

    print()
    if stopped:
        print("[OK] Stopped:")
        for item in stopped:
            print(f"   - {item}")
    else:
        print("[i]  No Reflex processes were running")


def print_status():
    """Print current status."""
    status = is_running()

    print("=" * 60)
    print("REFLEX SERVER STATUS")
    print("=" * 60)

    if status["backend"]:
        print(f"[+] Backend:  RUNNING (PID: {status['backend'].pid})")
        print(f"   Port: {PORT_BACKEND}")
        print(f"   URL:  http://localhost:{PORT_BACKEND}")
    else:
        print("[-] Backend:  NOT RUNNING")

    print()

    if status["frontend"]:
        print(f"[+] Frontend: RUNNING (PID: {status['frontend'].pid})")
        print(f"   Port: {PORT_FRONTEND}")
        print(f"   URL:  http://localhost:{PORT_FRONTEND}")
    else:
        print("[-] Frontend: NOT RUNNING")

    # Check for orphaned processes
    other_procs = get_reflex_processes()
    backend_pid = status["backend"].pid if status["backend"] else None
    frontend_pid = status["frontend"].pid if status["frontend"] else None

    orphaned = [p for p in other_procs if p.pid not in [backend_pid, frontend_pid]]

    if orphaned:
        print()
        print(f"[!]  Orphaned Reflex processes found: {len(orphaned)}")
        for proc in orphaned:
            cmdline = " ".join(proc.cmdline())[:60]
            print(f"   - PID {proc.pid}: {cmdline}...")

    print("=" * 60)


def restart():
    """Restart Reflex server."""
    print("[RESTART] Restarting Reflex server...")
    stop()
    time.sleep(2)
    start()


def main():
    if len(sys.argv) < 2:
        print("Usage: python reflex_server.py {start|stop|restart|status}")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "start":
        start()
    elif command == "stop":
        stop()
    elif command == "restart":
        restart()
    elif command == "status":
        print_status()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python reflex_server.py {start|stop|restart|status}")
        sys.exit(1)


if __name__ == "__main__":
    main()
