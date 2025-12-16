#!/usr/bin/env python
"""
RQ Worker Manager - Easily control background workers.

Usage:
    python worker_manager.py start [count]   # Start worker(s) (default: 1)
    python worker_manager.py stop [pid]      # Stop worker(s) (all or specific PID)
    python worker_manager.py restart         # Restart all workers
    python worker_manager.py status          # Show worker status
    python worker_manager.py list            # List all workers with PIDs
"""

import sys
import subprocess
import time
import psutil
from pathlib import Path

# Add project root to path for central config
sys.path.insert(0, str(Path(__file__).parent))

from config import ARKHAM_MIRROR_PATH, REDIS_URL

ARKHAM_MIRROR_DIR = ARKHAM_MIRROR_PATH
WORKER_SCRIPT = ARKHAM_MIRROR_DIR / "run_rq_worker.py"
WORKER_PID_DIR = Path(__file__).parent / ".worker_pids"


def get_worker_processes():
    """Get all RQ worker processes."""
    workers = []
    for proc in psutil.process_iter(
        ["pid", "name", "cmdline", "create_time", "memory_info"]
    ):
        try:
            if proc.info["name"] in ["python.exe", "python"]:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "run_rq_worker" in cmdline or "rq worker" in cmdline:
                    workers.append(
                        {
                            "pid": proc.info["pid"],
                            "cmdline": cmdline,
                            "started": proc.info["create_time"],
                            "memory_mb": proc.info["memory_info"].rss / (1024 * 1024)
                            if proc.info["memory_info"]
                            else 0,
                            "proc": proc,
                        }
                    )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return workers


def get_queue_status():
    """Get RQ queue status from Redis."""
    try:
        from redis import Redis
        from rq import Queue

        redis_conn = Redis.from_url(REDIS_URL)
        q = Queue(connection=redis_conn)

        return {
            "queued": len(q),
            "processing": len(q.started_job_registry),
            "completed": len(q.finished_job_registry),
            "failed": len(q.failed_job_registry),
        }
    except Exception as e:
        return {"error": str(e)}


def start_workers(count=1):
    """Start worker(s)."""
    print(f"[>>] Starting {count} RQ worker(s)...")
    print(f"   Script: {WORKER_SCRIPT}")
    print()

    WORKER_PID_DIR.mkdir(exist_ok=True)

    started = []
    for i in range(count):
        if sys.platform == "win32":
            # Windows: Start in new console with title
            title = f"RQ_Worker_{i + 1}"  # No spaces to avoid quoting issues
            cmd = f'start "{title}" cmd /k {sys.executable} {WORKER_SCRIPT}'
            proc = subprocess.Popen(cmd, shell=True, cwd=str(ARKHAM_MIRROR_DIR))
            time.sleep(2)  # Give it time to start

            # Try to find the new worker process
            workers = get_worker_processes()
            if workers:
                new_worker = max(workers, key=lambda w: w["started"])
                started.append(new_worker["pid"])
                print(f"[OK] Worker {i + 1} started (PID: {new_worker['pid']})")

                # Save PID to file
                with open(WORKER_PID_DIR / f"worker_{new_worker['pid']}.pid", "w") as f:
                    f.write(f"{new_worker['pid']}\n{time.time()}\n")
            else:
                print(f"[!]  Worker {i + 1} started but couldn't get PID")

        else:
            # Linux/Mac
            proc = subprocess.Popen(
                ["python", str(WORKER_SCRIPT)],
                cwd=str(ARKHAM_MIRROR_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            started.append(proc.pid)
            print(f"[OK] Worker {i + 1} started (PID: {proc.pid})")

            # Save PID to file
            with open(WORKER_PID_DIR / f"worker_{proc.pid}.pid", "w") as f:
                f.write(f"{proc.pid}\n{time.time()}\n")

    print()
    print_status()


def stop_workers(pid=None):
    """Stop worker(s)."""
    workers = get_worker_processes()

    if not workers:
        print("[i]  No workers are running")
        return

    if pid:
        # Stop specific worker
        worker = next((w for w in workers if w["pid"] == pid), None)
        if not worker:
            print(f"[X] No worker found with PID {pid}")
            return

        print(f"[STOP] Stopping worker (PID: {pid})...")
        try:
            worker["proc"].terminate()
            worker["proc"].wait(timeout=5)
            print(f"[OK] Worker stopped (PID: {pid})")

            # Remove PID file
            pid_file = WORKER_PID_DIR / f"worker_{pid}.pid"
            if pid_file.exists():
                pid_file.unlink()

        except psutil.TimeoutExpired:
            print("[!]  Worker didn't stop gracefully, forcing...")
            worker["proc"].kill()
            print(f"[OK] Worker killed (PID: {pid})")
    else:
        # Stop all workers
        print(f"[STOP] Stopping {len(workers)} worker(s)...")
        for worker in workers:
            try:
                print(f"   Stopping PID {worker['pid']}...")
                worker["proc"].terminate()
                worker["proc"].wait(timeout=5)
                print(f"   [OK] Stopped (PID: {worker['pid']})")

                # Remove PID file
                pid_file = WORKER_PID_DIR / f"worker_{worker['pid']}.pid"
                if pid_file.exists():
                    pid_file.unlink()

            except psutil.TimeoutExpired:
                print(f"   [!]  Forcing kill (PID: {worker['pid']})...")
                worker["proc"].kill()

        print()
        print("[OK] All workers stopped")


def print_status():
    """Print worker and queue status."""
    workers = get_worker_processes()
    queue_status = get_queue_status()

    print("=" * 70)
    print("RQ WORKER STATUS")
    print("=" * 70)

    if workers:
        print(f"[+] Active Workers: {len(workers)}")
        print()
        for i, worker in enumerate(workers, 1):
            age = time.time() - worker["started"]
            age_str = f"{int(age // 3600)}h {int((age % 3600) // 60)}m {int(age % 60)}s"
            print(f"   Worker {i}:")
            print(f"      PID:    {worker['pid']}")
            print(f"      Memory: {worker['memory_mb']:.1f} MB")
            print(f"      Uptime: {age_str}")
            print()
    else:
        print("[-] Active Workers: 0")
        print()

    if "error" not in queue_status:
        print("Queue Status:")
        print(f"   Queued:     {queue_status['queued']}")
        print(f"   Processing: {queue_status['processing']}")
        print(f"   Completed:  {queue_status['completed']}")
        print(f"   Failed:     {queue_status['failed']}")

        # Warning if jobs exist but no workers
        total_jobs = queue_status["queued"] + queue_status["processing"]
        if total_jobs > 0 and len(workers) == 0:
            print()
            print("[!]  WARNING: Jobs exist but no workers are running!")
            print("   Run: python worker_manager.py start")
    else:
        print(f"[!]  Could not connect to Redis: {queue_status['error']}")

    print("=" * 70)


def list_workers():
    """List all workers with details."""
    workers = get_worker_processes()

    if not workers:
        print("No workers are currently running")
        return

    print(f"\nFound {len(workers)} worker(s):\n")
    print(f"{'PID':<8} {'Memory':<12} {'Uptime':<15} {'Command':<50}")
    print("-" * 85)

    for worker in workers:
        age = time.time() - worker["started"]
        age_str = f"{int(age // 3600)}h {int((age % 3600) // 60)}m {int(age % 60)}s"
        cmdline = (
            worker["cmdline"][:47] + "..."
            if len(worker["cmdline"]) > 50
            else worker["cmdline"]
        )

        print(
            f"{worker['pid']:<8} {worker['memory_mb']:<10.1f}MB {age_str:<15} {cmdline}"
        )


def restart_workers():
    """Restart all workers."""
    workers = get_worker_processes()
    count = len(workers) if workers else 1

    print("[RESTART] Restarting workers...")
    stop_workers()
    time.sleep(2)
    start_workers(count)


def main():
    if len(sys.argv) < 2:
        print("Usage: python worker_manager.py {start|stop|restart|status|list} [args]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "start":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        start_workers(count)

    elif command == "stop":
        pid = int(sys.argv[2]) if len(sys.argv) > 2 else None
        stop_workers(pid)

    elif command == "restart":
        restart_workers()

    elif command == "status":
        print_status()

    elif command == "list":
        list_workers()

    else:
        print(f"Unknown command: {command}")
        print("Usage: python worker_manager.py {start|stop|restart|status|list} [args]")
        sys.exit(1)


if __name__ == "__main__":
    main()
