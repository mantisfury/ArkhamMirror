import reflex as rx
import os
import sys
from pathlib import Path
from .design_tokens import SPACING, FONT_SIZE

# Add project root to path for central config
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from config import APP_PATH, REDIS_URL, PYTHON_EXECUTABLE, LOGS_DIR


class WorkerState(rx.State):
    """State for worker management."""

    worker_count: int = 0
    queue_stats: dict[str, int] = {}
    is_loading: bool = False

    # Phase 2.2: Enhanced worker tracking
    worker_details: list[dict[str, str]] = []  # List of worker info dicts
    worker_logs: str = ""  # Last N lines of worker logs

    def check_worker_status(self):
        """Check if workers are running and get queue stats."""
        import logging
        from datetime import datetime, timezone

        logger = logging.getLogger(__name__)

        self.is_loading = True
        try:
            from redis import Redis

            # Check Redis queues
            redis_url = REDIS_URL
            r = Redis.from_url(redis_url, decode_responses=True)

            # Get queue lengths
            queue_names = [
                "default",
                "ingest",
                "splitter",
                "ocr",
                "parser",
                "embed",
                "clustering",
                "failed",
            ]
            stats = {}
            for queue_name in queue_names:
                queue_len = r.llen(f"rq:queue:{queue_name}")
                if queue_len > 0:
                    stats[queue_name] = queue_len

            self.queue_stats = stats

            # Check actual RQ workers with heartbeat verification
            worker_keys = r.keys("rq:worker:*")

            active_workers = []
            stale_workers = []
            worker_info_list = []  # Phase 2.2: Collect detailed worker info
            now = datetime.now(timezone.utc)

            for key in worker_keys:
                key_str = key if isinstance(key, str) else key.decode("utf-8")
                parts = key_str.split(":")

                if len(parts) == 3:  # rq:worker:WORKER_ID
                    worker_data = r.hgetall(key_str)

                    if worker_data:
                        # Check heartbeat freshness (workers send heartbeat every 30s)
                        heartbeat_str = worker_data.get("last_heartbeat", "")
                        if heartbeat_str:
                            try:
                                heartbeat = datetime.fromisoformat(
                                    heartbeat_str.replace("Z", "+00:00")
                                )
                                age = (now - heartbeat).total_seconds()

                                # Worker is alive if heartbeat is less than 60 seconds old
                                if age < 60:
                                    active_workers.append(key_str)
                                    logger.debug(
                                        f"Active worker: {key_str} (heartbeat {age:.0f}s ago)"
                                    )

                                    # Phase 2.2: Extract worker details
                                    worker_id = parts[2]
                                    # Worker ID format: hostname.pid.uuid
                                    worker_id_parts = worker_id.split(".")
                                    pid = (
                                        worker_id_parts[1]
                                        if len(worker_id_parts) > 1
                                        else "Unknown"
                                    )

                                    # Get queue assignments
                                    queues_str = worker_data.get("queues", "default")
                                    queues_list = (
                                        queues_str.split(",")
                                        if queues_str
                                        else ["default"]
                                    )

                                    # Get current job
                                    current_job = worker_data.get("current_job", "Idle")

                                    worker_info_list.append(
                                        {
                                            "worker_id": worker_id,
                                            "pid": pid,
                                            "queues": ", ".join(queues_list),
                                            "heartbeat_age": f"{int(age)}s ago",
                                            "status": "Active",
                                            "current_job": current_job
                                            if current_job
                                            else "Idle",
                                        }
                                    )
                                else:
                                    stale_workers.append(key_str)
                                    logger.warning(
                                        f"Stale worker: {key_str} (heartbeat {age:.0f}s ago)"
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Could not parse heartbeat for {key_str}: {e}"
                                )
                                stale_workers.append(key_str)

            # Clean up stale workers
            for stale_key in stale_workers:
                try:
                    r.delete(stale_key)
                    logger.info(f"Cleaned up stale worker: {stale_key}")
                except Exception as e:
                    logger.error(f"Failed to delete stale worker {stale_key}: {e}")

            self.worker_count = len(active_workers)
            self.worker_details = worker_info_list  # Phase 2.2: Store worker details
            logger.info(f"Worker check: {self.worker_count} active RQ workers found")

            # Note: Ingestion status refresh is handled by the UI's auto-refresh
            # Do not yield state classes here - it causes Reflex errors

        except Exception as e:
            logger.error(f"Failed to check worker status: {e}", exc_info=True)
            self.worker_count = 0
            self.queue_stats = {}
            self.worker_details = []  # Phase 2.2: Clear worker details on error
        finally:
            self.is_loading = False

    def start_worker(self):
        """Start a new RQ worker and verify it registered."""
        import subprocess
        import time
        import logging

        logger = logging.getLogger(__name__)

        try:
            app_dir = APP_PATH

            if sys.platform == "win32":
                # Start worker directly in new console window
                venv_python = PYTHON_EXECUTABLE
                process = subprocess.Popen(
                    [
                        "cmd",
                        "/k",
                        venv_python,
                        "run_rq_worker.py",
                        "default",
                        "splitter",
                        "ocr",
                        "parser",
                        "embed",
                        "clustering",
                    ],
                    cwd=str(app_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                # Unix-like systems
                process = subprocess.Popen(
                    [
                        "python",
                        "-m",
                        "rq.worker",
                        "default",
                        "splitter",
                        "ocr",
                        "parser",
                        "embed",
                        "clustering",
                    ],
                    cwd=str(app_dir),
                )

            logger.info(f"Started worker process with PID: {process.pid}")

            # Wait briefly and verify worker registered in Redis
            time.sleep(2)

            # Check if worker actually registered
            from redis import Redis

            redis_url = REDIS_URL
            r = Redis.from_url(redis_url, decode_responses=True)
            worker_keys_before = len(
                [k for k in r.keys("rq:worker:*") if len(k.split(":")) == 3]
            )

            time.sleep(1)

            worker_keys_after = len(
                [k for k in r.keys("rq:worker:*") if len(k.split(":")) == 3]
            )

            # Auto-refresh status
            self.check_worker_status()

            # Note: Ingestion status will auto-refresh via background task
            # No need to manually trigger refresh here

            # Prepare success message based on verification result
            if worker_keys_after > worker_keys_before:
                logger.info(f"Worker verified: {worker_keys_after} workers now running")
                yield rx.window_alert(
                    f"Worker started successfully! {worker_keys_after} worker(s) now running."
                )
            else:
                logger.warning(
                    "Worker process started but did not register in Redis yet"
                )
                yield rx.window_alert(
                    "Worker process started. Check console window for any errors."
                )

        except Exception as e:
            logger.error(f"Failed to start worker: {e}", exc_info=True)
            return rx.window_alert(f"Failed to start worker: {str(e)}")

    def kill_all_workers(self):
        """Kill all RQ worker processes by finding them via command line."""
        import psutil
        import logging

        logger = logging.getLogger(__name__)

        try:
            from redis import Redis

            redis_url = REDIS_URL
            r = Redis.from_url(redis_url, decode_responses=True)

            # Find all Python processes running run_rq_worker.py
            killed_count = 0
            failed_pids = []

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    # Check if it's a Python process
                    if proc.info["name"] and "python" in proc.info["name"].lower():
                        cmdline = proc.info["cmdline"]
                        if cmdline and any(
                            "run_rq_worker" in str(arg) for arg in cmdline
                        ):
                            pid = proc.info["pid"]
                            try:
                                proc_obj = psutil.Process(pid)
                                proc_obj.terminate()
                                proc_obj.wait(timeout=3)
                                killed_count += 1
                                logger.info(f"Terminated worker process PID {pid}")
                            except psutil.TimeoutExpired:
                                proc_obj.kill()
                                killed_count += 1
                                logger.info(f"Force killed worker process PID {pid}")
                            except Exception as e:
                                logger.error(f"Failed to kill PID {pid}: {e}")
                                failed_pids.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Clean up ALL worker registrations in Redis
            worker_keys = r.keys("rq:worker:*")
            for key in worker_keys:
                key_str = key if isinstance(key, str) else key.decode("utf-8")
                parts = key_str.split(":")
                if len(parts) == 3:
                    try:
                        r.delete(key_str)
                        logger.debug(f"Deleted worker registration: {key_str}")
                    except Exception as e:
                        logger.error(f"Failed to delete Redis key {key_str}: {e}")

            # Auto-refresh status
            self.check_worker_status()

            # Note: Ingestion status refresh is handled by the UI's auto-refresh
            # Do not yield state classes here - it causes Reflex errors

            # Show result message
            if failed_pids:
                yield rx.window_alert(
                    f"Stopped {killed_count} worker(s), but failed to kill PIDs: {failed_pids}"
                )
            elif killed_count > 0:
                yield rx.window_alert(f"Successfully stopped {killed_count} worker(s).")
            else:
                yield rx.window_alert("No worker processes found running.")

        except Exception as e:
            logger.error(f"Failed to stop workers: {e}", exc_info=True)
            return rx.window_alert(f"Failed to stop workers: {str(e)}")

    def restart_all_workers(self):
        """Phase 2.2: Restart all workers (stop then start)."""
        import time
        import logging

        logger = logging.getLogger(__name__)

        try:
            # First, stop all workers
            logger.info("Restarting workers: stopping existing workers...")
            # Kill workers inline instead of calling generator method
            import subprocess
            import psutil
            from redis import Redis

            redis_url = REDIS_URL
            r = Redis.from_url(redis_url, decode_responses=True)

            # Kill processes
            killed_count = 0
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    if proc.info["name"] and "python" in proc.info["name"].lower():
                        cmdline = proc.info["cmdline"]
                        if cmdline and any(
                            "run_rq_worker" in str(arg) for arg in cmdline
                        ):
                            pid = proc.info["pid"]
                            proc_obj = psutil.Process(pid)
                            proc_obj.terminate()
                            try:
                                proc_obj.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                proc_obj.kill()
                            killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Clean up Redis registrations
            for key in r.keys("rq:worker:*"):
                key_str = key if isinstance(key, str) else key.decode("utf-8")
                if len(key_str.split(":")) == 3:
                    r.delete(key_str)

            logger.info(f"Stopped {killed_count} workers")
            time.sleep(2)

            # Start a new worker
            logger.info("Restarting workers: starting new worker...")
            app_dir = APP_PATH
            if sys.platform == "win32":
                venv_python = PYTHON_EXECUTABLE
                subprocess.Popen(
                    [
                        "cmd",
                        "/k",
                        venv_python,
                        "run_rq_worker.py",
                        "default",
                        "splitter",
                        "ocr",
                        "parser",
                        "embed",
                        "clustering",
                    ],
                    cwd=str(app_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(
                    [
                        "python",
                        "-m",
                        "rq.worker",
                        "default",
                        "splitter",
                        "ocr",
                        "parser",
                        "embed",
                        "clustering",
                    ],
                    cwd=str(app_dir),
                )

            time.sleep(2)
            self.check_worker_status()
            yield rx.window_alert("Workers restarted successfully!")

        except Exception as e:
            logger.error(f"Failed to restart workers: {e}", exc_info=True)
            return rx.window_alert(f"Failed to restart workers: {str(e)}")

    def load_worker_logs(self):
        """Phase 2.2: Load last 20 lines from worker logs."""
        import logging
        import glob

        logger = logging.getLogger(__name__)
        self.is_loading = True

        try:
            log_dir = LOGS_DIR
            log_files = glob.glob(str(log_dir / "worker*.log"))

            if not log_files:
                self.worker_logs = "No worker log files found."
                return

            # Get the most recent log file
            latest_log = max(log_files, key=os.path.getmtime)

            # Read last 20 lines
            with open(latest_log, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                last_lines = lines[-20:] if len(lines) > 20 else lines
                self.worker_logs = "".join(last_lines)

            logger.info(f"Loaded worker logs from: {latest_log}")

        except Exception as e:
            logger.error(f"Failed to load worker logs: {e}", exc_info=True)
            self.worker_logs = f"Error loading logs: {str(e)}"
        finally:
            self.is_loading = False


def worker_management_component() -> rx.Component:
    """Worker management UI component with Phase 2.2 enhancements."""
    return rx.card(
        rx.vstack(
            rx.heading("Worker Management", size="4"),
            # Status Section
            rx.hstack(
                rx.badge(
                    rx.cond(
                        WorkerState.worker_count > 0,
                        f"{WorkerState.worker_count} Worker(s) Running",
                        "No Workers Running",
                    ),
                    color_scheme=rx.cond(WorkerState.worker_count > 0, "green", "red"),
                    variant="soft",
                    size="2",
                ),
                rx.button(
                    "Refresh Status",
                    on_click=WorkerState.check_worker_status,
                    size="1",
                    variant="soft",
                    loading=WorkerState.is_loading,
                ),
                spacing=SPACING["md"],
                align="center",
                width="100%",
                justify="between",
            ),
            # Phase 2.2: Worker Details Table
            rx.cond(
                WorkerState.worker_details != [],
                rx.vstack(
                    rx.text(
                        "Active Workers:",
                        font_size=FONT_SIZE["sm"],
                        font_weight="600",
                        color="gray.11",
                    ),
                    rx.box(
                        rx.foreach(
                            WorkerState.worker_details,
                            lambda worker: rx.card(
                                rx.vstack(
                                    rx.hstack(
                                        rx.badge(
                                            "PID",
                                            color_scheme="gray",
                                            variant="soft",
                                            size="1",
                                        ),
                                        rx.text(
                                            worker["pid"],
                                            font_size=FONT_SIZE["xs"],
                                            color="gray.11",
                                        ),
                                        rx.badge(
                                            "Status",
                                            color_scheme="gray",
                                            variant="soft",
                                            size="1",
                                        ),
                                        rx.badge(
                                            worker["status"],
                                            color_scheme="green",
                                            variant="soft",
                                            size="1",
                                        ),
                                        rx.text(
                                            worker["heartbeat_age"],
                                            font_size=FONT_SIZE["xs"],
                                            color="gray.10",
                                        ),
                                        spacing=SPACING["xs"],
                                        wrap="wrap",
                                    ),
                                    rx.hstack(
                                        rx.badge(
                                            "Queues",
                                            color_scheme="gray",
                                            variant="soft",
                                            size="1",
                                        ),
                                        rx.text(
                                            worker["queues"],
                                            font_size=FONT_SIZE["xs"],
                                            color="blue.11",
                                        ),
                                        spacing=SPACING["xs"],
                                    ),
                                    rx.hstack(
                                        rx.badge(
                                            "Job",
                                            color_scheme="gray",
                                            variant="soft",
                                            size="1",
                                        ),
                                        rx.text(
                                            worker["current_job"],
                                            font_size=FONT_SIZE["xs"],
                                            color="gray.10",
                                        ),
                                        spacing=SPACING["xs"],
                                    ),
                                    spacing=SPACING["xs"],
                                    width="100%",
                                ),
                                padding=SPACING["sm"],
                                margin_y=SPACING["xs"],
                            ),
                        ),
                        width="100%",
                        max_height="200px",
                        overflow_y="auto",
                    ),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
            ),
            # Queue Stats with Warning
            rx.cond(
                WorkerState.queue_stats != {},
                rx.vstack(
                    rx.text(
                        "Active Queues:",
                        font_size=FONT_SIZE["sm"],
                        font_weight="600",
                        color="gray.11",
                    ),
                    rx.foreach(
                        WorkerState.queue_stats.items(),
                        lambda item: rx.hstack(
                            rx.badge(item[0], variant="soft", color_scheme="blue"),
                            rx.text(
                                f"{item[1]} jobs",
                                font_size=FONT_SIZE["sm"],
                                color="gray.11",
                            ),
                            spacing=SPACING["xs"],
                        ),
                    ),
                    # Warning if jobs are queued but no workers (Phase 2.2 - already existed)
                    rx.cond(
                        WorkerState.worker_count == 0,
                        rx.callout(
                            "Jobs are queued but no workers are running! Start a worker to process them.",
                            icon="triangle_alert",
                            color_scheme="red",
                            size="1",
                        ),
                    ),
                    spacing=SPACING["xs"],
                    width="100%",
                ),
            ),
            # Phase 2.2: Worker Logs (collapsible)
            rx.card(
                rx.vstack(
                    rx.hstack(
                        rx.text(
                            "Worker Logs", font_size=FONT_SIZE["sm"], font_weight="600"
                        ),
                        rx.button(
                            "Refresh Logs",
                            on_click=WorkerState.load_worker_logs,
                            size="1",
                            variant="soft",
                            loading=WorkerState.is_loading,
                        ),
                        spacing=SPACING["sm"],
                        align="center",
                        width="100%",
                        justify="between",
                    ),
                    rx.box(
                        rx.cond(
                            WorkerState.worker_logs != "",
                            rx.code_block(
                                WorkerState.worker_logs,
                                language="log",
                                font_size=FONT_SIZE["xs"],
                                max_height="200px",
                                overflow_y="auto",
                            ),
                            rx.text(
                                "Click 'Refresh Logs' to load logs",
                                font_size=FONT_SIZE["xs"],
                                color="gray.10",
                            ),
                        ),
                        padding_top=SPACING["sm"],
                    ),
                    width="100%",
                    spacing=SPACING["sm"],
                ),
                width="100%",
                size="2",
            ),
            # Action Buttons (Phase 2.2: Added Restart)
            rx.hstack(
                rx.button(
                    "Start Worker",
                    on_click=WorkerState.start_worker,
                    color="white",
                    bg="green.9",
                    size="2",
                ),
                rx.button(
                    "Restart All",
                    on_click=WorkerState.restart_all_workers,
                    color="white",
                    bg="orange.9",
                    size="2",
                ),
                rx.button(
                    "Stop All Workers",
                    on_click=WorkerState.kill_all_workers,
                    color="white",
                    bg="red.9",
                    size="2",
                ),
                spacing=SPACING["sm"],
                width="100%",
                wrap="wrap",
            ),
            rx.text(
                "Note: Workers process jobs from the queue. At least one worker must be running for ingestion to complete.",
                font_size=FONT_SIZE["xs"],
                color="amber.11",
            ),
            spacing=SPACING["md"],
            width="100%",
        ),
        padding=SPACING["md"],
        margin_bottom=SPACING["md"],
    )
