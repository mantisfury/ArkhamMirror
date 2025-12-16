#!/usr/bin/env python
"""
ArkhamMirror Reflex Startup Script

Handles port cleanup gracefully before starting the Reflex application.
Works around Windows TIME_WAIT socket state issues.

Usage:
    python start_reflex.py          # Normal start
    python start_reflex.py --force  # Kill processes without asking
    python start_reflex.py --wait   # Wait longer for ports (60s vs 30s)
"""

import subprocess
import time
import sys
import os
import argparse

# Add project root to path for central config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BACKEND_PORT, FRONTEND_PORT, DOCKER_PATH

# Configuration
DEFAULT_MAX_WAIT = 30


def get_pid_on_port(port: int) -> list[int]:
    """Get list of PIDs listening on a specific port."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, shell=True
        )
        pids = set()
        for line in result.stdout.split("\n"):
            if f":{port}" in line and "LISTENING" in line:
                # Extract PID from the last column
                parts = line.strip().split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        pids.add(pid)
                    except ValueError:
                        pass
        return list(pids)
    except Exception as e:
        print(f"  Warning: Could not check port {port}: {e}")
        return []


def kill_process(pid: int) -> bool:
    """Kill a process by PID."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)], capture_output=True, shell=True
        )
        return True
    except Exception as e:
        print(f"  Warning: Could not kill PID {pid}: {e}")
        return False


def wait_for_port_free(port: int, max_wait: int) -> bool:
    """Wait for a port to become free."""
    for i in range(max_wait):
        pids = get_pid_on_port(port)
        if not pids:
            return True
        print(f"  Port {port} still in use, waiting... ({i + 1}/{max_wait}s)")
        time.sleep(1)
    return False


def check_docker_services():
    """Check if Docker services are running."""
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "{{.Status}}"],
            capture_output=True,
            text=True,
            cwd=str(DOCKER_PATH),
            shell=True,
        )
        if "running" in result.stdout.lower():
            return True
        return False
    except Exception:
        return False


def start_docker_services():
    """Start Docker services."""
    print("  Starting Docker services...")
    subprocess.run(["docker", "compose", "up", "-d"], cwd=str(DOCKER_PATH), shell=True)
    time.sleep(3)


def main():
    parser = argparse.ArgumentParser(
        description="Start ArkhamMirror Reflex Application"
    )
    parser.add_argument(
        "--force", action="store_true", help="Kill processes without asking"
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=DEFAULT_MAX_WAIT,
        help=f"Max seconds to wait for ports (default: {DEFAULT_MAX_WAIT})",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("  ArkhamMirror Startup Script")
    print("=" * 50)
    print()

    # Step 1: Check and kill existing processes
    print("[1/4] Checking for existing processes...")

    for port in [BACKEND_PORT, FRONTEND_PORT]:
        pids = get_pid_on_port(port)
        if pids:
            print(f"  Port {port} in use by PIDs: {pids}")
            for pid in pids:
                print(f"    Killing PID {pid}...")
                kill_process(pid)

    # Also try to kill node.exe processes
    subprocess.run(
        ["taskkill", "/F", "/IM", "node.exe"], capture_output=True, shell=True
    )

    print("  Done.")
    print()

    # Step 2: Wait for ports to clear
    print("[2/4] Waiting for ports to clear...")

    ports_clear = True
    for port in [BACKEND_PORT, FRONTEND_PORT]:
        if not wait_for_port_free(port, args.wait):
            print(f"  WARNING: Port {port} still in use after {args.wait} seconds")
            ports_clear = False

    if not ports_clear:
        if not args.force:
            response = input("  Continue anyway? (y/n): ").strip().lower()
            if response != "y":
                print("  Aborting.")
                sys.exit(1)
    else:
        print("  All ports are clear!")
    print()

    # Step 3: Check Docker services
    print("[3/6] Verifying Docker services...")
    if check_docker_services():
        print("  Docker services already running.")
    else:
        start_docker_services()
    print()

    # Step 4: Ensure database is initialized
    print("[4/6] Checking database initialization...")
    try:
        from arkham.services.db.db_init import ensure_database_ready

        if ensure_database_ready():
            print("  Database is ready.")
        else:
            print("  WARNING: Database initialization failed!")
            print("  The app may not work correctly.")
    except Exception as e:
        print(f"  WARNING: Could not initialize database: {e}")
        print("  Continuing anyway...")
    print()

    # Step 5: Ensure .web directory is clean
    print("[5/6] Checking frontend cache...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(script_dir, ".web")
    cache_dir = os.path.join(web_dir, "cache")

    # Ensure directories exist (including nocompile which Granian expects)
    if not os.path.exists(web_dir):
        os.makedirs(web_dir, exist_ok=True)
        print("  Created .web directory")

    # Create nocompile file - Granian's file watcher expects this to exist
    # Note: This must be a FILE, not directory. Reflex calls unlink() on it.
    nocompile_path = os.path.join(web_dir, "nocompile")
    if not os.path.exists(nocompile_path):
        from pathlib import Path

        Path(nocompile_path).touch()
        print("  Created .web/nocompile file")

    # Clear cache if it might be corrupted
    if os.path.exists(cache_dir):
        try:
            import shutil

            shutil.rmtree(cache_dir, ignore_errors=True)
            print("  Cleared frontend cache")
        except Exception:
            pass

    print("  Done.")
    print()

    # Step 6: Start Reflex
    print("[6/6] Starting Reflex application...")
    print()
    print("=" * 50)
    print(f"  Frontend: http://localhost:{FRONTEND_PORT}")
    print(f"  Backend:  http://localhost:{BACKEND_PORT}")
    print("=" * 50)
    print()

    # Change to arkham directory
    os.chdir(script_dir)

    # Disable Granian and use uvicorn instead to avoid file watcher bug on Windows
    # Granian's watchfiles tries to watch paths that may not exist
    os.environ["REFLEX_USE_GRANIAN"] = "false"

    # Start Reflex (this will block until Ctrl+C)
    try:
        subprocess.run([sys.executable, "-m", "reflex", "run"])
    except KeyboardInterrupt:
        print("\n  Shutting down...")


if __name__ == "__main__":
    main()
