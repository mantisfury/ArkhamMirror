#!/usr/bin/env python
"""
ArkhamMirror System Status - Check all services at once.

Shows status of:
- Docker services (PostgreSQL, Qdrant, Redis)
- Reflex server (Frontend + Backend)
- RQ Workers
- Queue status
"""

import os
import sys
import subprocess
from pathlib import Path

# Import the individual managers
sys.path.insert(0, str(Path(__file__).parent))
from reflex_server import is_running as reflex_status, PORT_BACKEND, PORT_FRONTEND
from worker_manager import get_worker_processes, get_queue_status


def check_docker_services():
    """Check Docker services status."""
    try:
        result = subprocess.run(
            ['docker', 'compose', 'ps'],
            cwd=Path(__file__).parent / "arkham_mirror",
            capture_output=True,
            text=True,
            timeout=5
        )

        services = {}
        lines = result.stdout.strip().split('\n')

        # Parse docker compose ps output
        for line in lines[1:]:  # Skip header
            if line.strip() and not line.startswith('time='):
                # Join the whole line and check for "Up" anywhere in it
                if 'postgres' in line.lower():
                    services['postgres'] = 'Up' in line
                elif 'qdrant' in line.lower():
                    services['qdrant'] = 'Up' in line
                elif 'redis' in line.lower():
                    services['redis'] = 'Up' in line

        return services
    except Exception as e:
        return {'error': str(e)}


def print_full_status():
    """Print complete system status."""
    print("\n" + "=" * 80)
    print(" " * 25 + "ARKHAMMIRROR SYSTEM STATUS")
    print("=" * 80)

    # Docker Services
    print("\n[DOCKER SERVICES]")
    print("-" * 80)
    docker_services = check_docker_services()

    if 'error' in docker_services:
        print(f"   [X] Error: {docker_services['error']}")
        print(f"   [!] Run: cd arkham_mirror && docker compose up -d")
    else:
        postgres_status = "[+] RUNNING" if docker_services.get('postgres') else "[-] STOPPED"
        qdrant_status = "[+] RUNNING" if docker_services.get('qdrant') else "[-] STOPPED"
        redis_status = "[+] RUNNING" if docker_services.get('redis') else "[-] STOPPED"

        print(f"   PostgreSQL:  {postgres_status}  (Port 5435)")
        print(f"   Qdrant:      {qdrant_status}  (Ports 6343, 6344)")
        print(f"   Redis:       {redis_status}  (Port 6380)")

        all_running = all([
            docker_services.get('postgres'),
            docker_services.get('qdrant'),
            docker_services.get('redis')
        ])

        if not all_running:
            print(f"\n   [!] To start: cd arkham_mirror && docker compose up -d")

    # Reflex Server
    print("\n REFLEX SERVER")
    print("-" * 80)
    reflex = reflex_status()

    if reflex['backend']:
        print(f"   Backend:   [+] RUNNING  (PID: {reflex['backend'].pid}, Port: {PORT_BACKEND})")
        print(f"              http://localhost:{PORT_BACKEND}")
    else:
        print(f"   Backend:   [-] STOPPED")

    if reflex['frontend']:
        print(f"   Frontend:  [+] RUNNING  (PID: {reflex['frontend'].pid}, Port: {PORT_FRONTEND})")
        print(f"              http://localhost:{PORT_FRONTEND}")
    else:
        print(f"   Frontend:  [-] STOPPED")

    if not reflex['running']:
        print(f"\n   [!] To start: python reflex_server.py start")

    # RQ Workers
    print("\n  RQ WORKERS")
    print("-" * 80)
    workers = get_worker_processes()

    if workers:
        print(f"   Active Workers: [+] {len(workers)}")
        for i, worker in enumerate(workers, 1):
            print(f"      Worker {i}: PID {worker['pid']} ({worker['memory_mb']:.1f} MB)")
    else:
        print(f"   Active Workers: [-] 0")
        print(f"\n   [!] To start: python worker_manager.py start")

    # Queue Status
    print("\n JOB QUEUE")
    print("-" * 80)
    queue = get_queue_status()

    if 'error' not in queue:
        print(f"   Queued:     {queue['queued']}")
        print(f"   Processing: {queue['processing']}")
        print(f"   Completed:  {queue['completed']}")
        print(f"   Failed:     {queue['failed']}")

        total_jobs = queue['queued'] + queue['processing']
        if total_jobs > 0 and len(workers) == 0:
            print(f"\n   [!]  WARNING: {total_jobs} job(s) exist but no workers running!")
            print(f"   [!] Run: python worker_manager.py start")
    else:
        print(f"   [X] Cannot connect to queue: {queue['error']}")

    # Quick Actions
    print("\n" + "=" * 80)
    print("QUICK ACTIONS")
    print("=" * 80)
    print("   Start Everything:    python system_status.py --start-all")
    print("   Stop Everything:     python system_status.py --stop-all")
    print()
    print("   Reflex Controls:     python reflex_server.py {start|stop|restart|status}")
    print("   Worker Controls:     python worker_manager.py {start|stop|restart|status}")
    print("   Docker Controls:     cd arkham_mirror && docker compose {up -d|down|ps}")
    print("=" * 80)
    print()


def start_all():
    """Start all services."""
    print("[>>] Starting all ArkhamMirror services...")
    print()

    # Start Docker
    print("1. Starting Docker services...")
    try:
        subprocess.run(
            ['docker', 'compose', 'up', '-d'],
            cwd=Path(__file__).parent / "arkham_mirror",
            check=True
        )
        print("   [OK] Docker services started")
    except Exception as e:
        print(f"   [X] Error: {e}")

    print()

    # Start Reflex
    print("2. Starting Reflex server...")
    subprocess.run([sys.executable, str(Path(__file__).parent / "reflex_server.py"), "start"])

    print()

    # Start worker
    print("3. Starting RQ worker...")
    subprocess.run([sys.executable, str(Path(__file__).parent / "worker_manager.py"), "start"])

    print()
    print("[OK] All services started!")
    print()


def stop_all():
    """Stop all services."""
    print("[STOP] Stopping all ArkhamMirror services...")
    print()

    # Stop workers
    print("1. Stopping RQ workers...")
    subprocess.run([sys.executable, str(Path(__file__).parent / "worker_manager.py"), "stop"])

    print()

    # Stop Reflex
    print("2. Stopping Reflex server...")
    subprocess.run([sys.executable, str(Path(__file__).parent / "reflex_server.py"), "stop"])

    print()

    # Stop Docker
    print("3. Stopping Docker services...")
    try:
        subprocess.run(
            ['docker', 'compose', 'down'],
            cwd=Path(__file__).parent / "arkham_mirror",
            check=True
        )
        print("   [OK] Docker services stopped")
    except Exception as e:
        print(f"   [X] Error: {e}")

    print()
    print("[OK] All services stopped!")
    print()


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == '--start-all':
            start_all()
        elif sys.argv[1] == '--stop-all':
            stop_all()
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Usage: python system_status.py [--start-all|--stop-all]")
            sys.exit(1)
    else:
        print_full_status()


if __name__ == "__main__":
    main()
