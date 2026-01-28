"""
ArkhamFrame FastAPI Application.

The main entry point for the Frame REST API.
"""

from contextlib import asynccontextmanager
import os
import sys
import socket
import subprocess
import platform
import re
from pathlib import Path
import time
from time import perf_counter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Load .env file before anything else accesses environment variables
from dotenv import load_dotenv

# Look for .env in project root (3 levels up from this file)
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    print(f"Loaded environment from {_env_path}")


def check_port_available(host: str, port: int) -> bool:
    """
    Check if a port is available on the given host.
    
    Returns True if port is available, False if already in use.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result != 0  # 0 means connection successful (port in use)
    except Exception:
        # If we can't check, assume it's available (let uvicorn handle the error)
        return True


def get_uvicorn_host_port() -> tuple[str, int]:
    """
    Extract host and port from uvicorn command line arguments or environment variables.
    
    Returns (host, port) tuple. Defaults to ('127.0.0.1', 8000).
    """
    host = '127.0.0.1'
    port = 8000
    
    # Check command line arguments (uvicorn passes them via sys.argv)
    args = sys.argv
    for i, arg in enumerate(args):
        if arg == '--host' and i + 1 < len(args):
            host = args[i + 1]
        elif arg == '--port' and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass
    
    # Check environment variables (uvicorn also respects these)
    host = os.environ.get('UVICORN_HOST', host)
    port_str = os.environ.get('UVICORN_PORT', str(port))
    try:
        port = int(port_str)
    except ValueError:
        pass
    
    return host, port


def find_process_using_port(host: str, port: int) -> list[int]:
    """
    Find process IDs using the specified port.
    
    Returns a list of process IDs. Empty list if no process found or error.
    """
    pids = []
    
    try:
        if platform.system() == "Windows":
            # Windows: use netstat to find PID
            # Format: TCP    0.0.0.0:8100    0.0.0.0:0    LISTENING    12345
            result = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    # Look for LISTENING state and port match
                    line_upper = line.upper()
                    if f":{port}" in line and "LISTENING" in line_upper:
                        # Extract PID (last column)
                        parts = line.split()
                        if parts:
                            try:
                                pid = int(parts[-1])
                                if pid not in pids:  # Avoid duplicates
                                    pids.append(pid)
                            except (ValueError, IndexError):
                                pass
        else:
            # Linux/macOS: try multiple methods for finding PIDs
            # Method 1: Try ss (modern Linux, faster than netstat)
            if platform.system() == "Linux":
                try:
                    # ss -tlnp shows listening TCP sockets with process info
                    # Format: LISTEN 0 128 0.0.0.0:8100 0.0.0.0:* users:(("python",pid=12345,fd=3))
                    result = subprocess.run(
                        ["ss", "-tlnp"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if f":{port}" in line and "LISTEN" in line:
                                # Extract PID from users:((process,pid=12345,...))
                                pid_match = re.search(r'pid=(\d+)', line)
                                if pid_match:
                                    try:
                                        pid = int(pid_match.group(1))
                                        if pid not in pids:
                                            pids.append(pid)
                                    except ValueError:
                                        pass
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
            
            # Method 2: Try lsof (works on Linux and macOS)
            if not pids:
                try:
                    result = subprocess.run(
                        ["lsof", "-ti", f":{port}"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for pid_str in result.stdout.strip().split('\n'):
                            if pid_str.strip():
                                try:
                                    pid = int(pid_str.strip())
                                    if pid not in pids:
                                        pids.append(pid)
                                except ValueError:
                                    pass
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
            
            # Method 3: Try fuser (Linux fallback, may require root)
            if not pids:
                try:
                    # fuser outputs to stderr, not stdout
                    result = subprocess.run(
                        ["fuser", f"{port}/tcp"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # fuser returns 0 if processes found, 1 if none
                    # Output format can be: "8100/tcp: 12345 67890" or just PIDs
                    # Sometimes output is in stderr
                    output = result.stderr if result.stderr else result.stdout
                    if result.returncode == 0 or output:
                        # Parse PIDs from output
                        # Look for numbers that could be PIDs
                        for match in re.finditer(r'\b(\d{2,})\b', output):
                            try:
                                pid = int(match.group(1))
                                # Reasonable PID range (Linux PIDs start at 1)
                                if 1 <= pid <= 4194304 and pid not in pids:
                                    pids.append(pid)
                            except ValueError:
                                pass
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
            
            # Method 4: Try netstat (fallback, available on most systems)
            if not pids:
                try:
                    result = subprocess.run(
                        ["netstat", "-tlnp"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if f":{port}" in line and "LISTEN" in line:
                                # Format: "tcp 0 0 0.0.0.0:8100 0.0.0.0:* LISTEN 12345/python"
                                # Look for PID/processname pattern at end
                                parts = line.split()
                                if parts:
                                    last_part = parts[-1]
                                    # Extract PID from "PID/processname" format
                                    if '/' in last_part:
                                        pid_str = last_part.split('/')[0]
                                    else:
                                        pid_str = last_part
                                    
                                    # Match digits only
                                    pid_match = re.match(r'^(\d+)$', pid_str)
                                    if pid_match:
                                        try:
                                            pid = int(pid_match.group(1))
                                            if pid not in pids:
                                                pids.append(pid)
                                        except ValueError:
                                            pass
                except FileNotFoundError:
                    pass
                except Exception:
                    pass
    except Exception as e:
        print(f"Warning: Could not find process using port {port}: {e}")
    
    return pids


def kill_processes(pids: list[int]) -> bool:
    """
    Kill processes by their PIDs.
    
    Returns True if all processes were killed successfully, False otherwise.
    """
    if not pids:
        return True
    
    success = True
    is_windows = platform.system() == "Windows"
    current_pid = os.getpid()
    
    for pid in pids:
        # Safety check: don't kill our own process
        if pid == current_pid:
            print(f"Warning: Skipping PID {pid} (current process)")
            continue
        
        try:
            if is_windows:
                # Windows: taskkill /PID <pid> /F
                result = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    print(f"Killed process {pid}")
                else:
                    error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                    # Check for common Windows errors
                    if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                        print(f"Process {pid} no longer exists (may have already terminated)")
                    else:
                        print(f"Warning: Could not kill process {pid}: {error_msg}")
                        success = False
            else:
                # Linux/macOS: Try SIGTERM first (graceful), then SIGKILL if needed
                # First attempt: SIGTERM (allows process to clean up)
                result = subprocess.run(
                    ["kill", "-TERM", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode != 0:
                    # If SIGTERM failed, try SIGKILL (force kill)
                    result = subprocess.run(
                        ["kill", "-9", str(pid)],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                
                if result.returncode == 0:
                    print(f"Killed process {pid}")
                else:
                    error_msg = result.stderr.strip() if result.stderr else ""
                    # Check for common Linux errors
                    if "No such process" in error_msg or result.returncode == 1:
                        print(f"Process {pid} no longer exists (may have already terminated)")
                    elif "Operation not permitted" in error_msg:
                        print(f"Warning: Permission denied killing process {pid} (may require root)")
                        success = False
                    else:
                        print(f"Warning: Could not kill process {pid}: {error_msg}")
                        success = False
        except FileNotFoundError:
            print(f"Error: kill command not found (unexpected on Unix-like system)")
            success = False
        except Exception as e:
            print(f"Error killing process {pid}: {e}")
            success = False
    
    return success


def has_force_flag() -> bool:
    """
    Check if force port kill is enabled via environment variable.
    
    Set ARKHAM_FORCE_PORT_KILL=true to enable automatic killing of processes
    using the target port before startup.
    """
    return os.environ.get("ARKHAM_FORCE_PORT_KILL", "false").lower() == "true"


# Check port availability as early as possible, before any heavy initialization
# This check runs when the module is imported by uvicorn
# We detect uvicorn startup by checking if uvicorn-related args are in sys.argv
_is_uvicorn_startup = any(
    "uvicorn" in arg.lower() or 
    "arkham_frame.main" in arg
    for arg in sys.argv
)

if _is_uvicorn_startup:
    try:
        host, port = get_uvicorn_host_port()
        force_flag = has_force_flag()
        
        if not check_port_available(host, port):
            if force_flag:
                print(f"Port {port} on {host} is already in use. ARKHAM_FORCE_PORT_KILL=true detected.")
                print(f"Attempting to kill process(es) using port {port}...")
                
                pids = find_process_using_port(host, port)
                if pids:
                    if kill_processes(pids):
                        print(f"Successfully killed process(es) using port {port}.")
                        # Wait a moment for the port to be released
                        time.sleep(0.5)
                        
                        # Verify port is now available
                        if check_port_available(host, port):
                            print(f"Port {port} is now available. Proceeding with startup...")
                        else:
                            print(f"Warning: Port {port} may still be in use. Continuing anyway...")
                    else:
                        print(f"Warning: Failed to kill some processes. Continuing anyway...")
                else:
                    print(f"Warning: Could not find process using port {port}. Continuing anyway...")
            else:
                print(f"ERROR: Port {port} on {host} is already in use.")
                print(f"Another instance of ArkhamFrame may be running.")
                print(f"Please stop the existing instance, use a different port, or set ARKHAM_FORCE_PORT_KILL=true to kill it.")
                sys.exit(1)
    except Exception as e:
        # If check fails, log warning but continue (let uvicorn handle port binding)
        print(f"Warning: Could not check port availability: {e}")

from .frame import ArkhamFrame

logger = logging.getLogger(__name__)

# Global frame instance
frame: ArkhamFrame = None


async def load_shards(frame: ArkhamFrame, app: FastAPI) -> None:
    """
    Load and initialize available shards using entry points.

    Shards register themselves via pyproject.toml:
        [project.entry-points."arkham.shards"]
        dashboard = "arkham_shard_dashboard:DashboardShard"
        ingest = "arkham_shard_ingest:IngestShard"
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:
        from importlib_metadata import entry_points

    # Allow disabling shard loading (useful for faster dev startup / debugging)
    if os.environ.get("ARKHAM_DISABLE_SHARDS", "false").lower() == "true":
        logger.info("Shard loading disabled via ARKHAM_DISABLE_SHARDS=true")
        return

    # Allow limiting which shards are loaded (comma-separated names)
    shard_allowlist_env = os.environ.get("ARKHAM_SHARDS", "").strip()
    shard_allowlist = None
    if shard_allowlist_env:
        shard_allowlist = {s.strip() for s in shard_allowlist_env.split(",") if s.strip()}
        logger.info(f"Limiting shard loading to: {sorted(shard_allowlist)}")

    # Discover shards via entry points
    eps = entry_points(group="arkham.shards")

    for ep in eps:
        shard_name = ep.name
        if shard_allowlist is not None and shard_name not in shard_allowlist:
            logger.info(f"Skipping shard (not allowlisted): {shard_name}")
            continue
        try:
            logger.info(f"Loading shard: {shard_name}")

            # Load the shard class
            shard_class = ep.load()

            # Instantiate (no args) and initialize with frame
            shard = shard_class()
            await shard.initialize(frame)

            # Register routes if shard has them
            router = shard.get_routes() or shard.get_api_router()

            if router:
                # Routes already include /api prefix
                app.include_router(
                    router,
                    tags=[shard_name.capitalize()],
                )

            frame.shards[shard_name] = shard
            logger.info(f"Shard loaded: {shard_name}")

        except Exception as e:
            logger.warning(f"Failed to load shard {shard_name}: {e}")
            import traceback
            traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Frame lifecycle."""
    global frame

    # Startup
    logger.info("Starting ArkhamFrame...")
    startup_t0 = perf_counter()
    frame = ArkhamFrame()
    t0 = perf_counter()
    await frame.initialize()
    logger.info(f"ArkhamFrame.initialize() completed in {(perf_counter() - t0):.2f}s")

    # Initialize auth database tables
    from .auth import create_db_and_tables
    from .auth.dependencies import async_session_maker
    from .auth.audit import ensure_audit_schema
    if os.environ.get("ARKHAM_SKIP_AUTH_DB_INIT", "false").lower() == "true":
        logger.warning("Skipping auth DB init via ARKHAM_SKIP_AUTH_DB_INIT=true (auth may break)")
    else:
        t0 = perf_counter()
        await create_db_and_tables()
        logger.info(f"Auth create_db_and_tables() completed in {(perf_counter() - t0):.2f}s")

        # Create audit tables
        t0 = perf_counter()
        async with async_session_maker() as session:
            await ensure_audit_schema(session)
            await session.commit()
        logger.info(f"Auth audit schema ensured in {(perf_counter() - t0):.2f}s")

    # Store app reference on frame for shards to access
    frame.app = app

    # Load shards
    t0 = perf_counter()
    await load_shards(frame, app)
    logger.info(f"Shard loading completed in {(perf_counter() - t0):.2f}s")

    # Set up SPA static serving AFTER shards are loaded
    # This ensures shard routes have priority over the catch-all
    if os.environ.get("ARKHAM_SERVE_SHELL", "false").lower() == "true":
        setup_static_serving()

    logger.info(f"ArkhamFrame startup complete in {(perf_counter() - startup_t0):.2f}s")
    yield

    # Shutdown shards
    for name, shard in frame.shards.items():
        try:
            await shard.shutdown()
            logger.info(f"Shard {name} shut down")
        except Exception as e:
            logger.error(f"Error shutting down shard {name}: {e}")

    # Shutdown frame
    logger.info("Stopping ArkhamFrame...")
    await frame.shutdown()


def get_cors_origins() -> list[str]:
    """Get allowed CORS origins from environment or defaults."""
    origins_env = os.environ.get("CORS_ORIGINS", "")
    if origins_env:
        return [o.strip() for o in origins_env.split(",") if o.strip()]

    # Default: allow localhost for development
    return [
        "http://localhost:5173",
        "http://localhost:8100",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8100",
    ]


# Create FastAPI app
app = FastAPI(
    title="ArkhamFrame",
    description="ArkhamMirror Shattered Frame - Core Infrastructure API",
    version="0.1.0",
    lifespan=lifespan,
)

# Security middleware
from .middleware import SecurityHeadersMiddleware, limiter, rate_limit_handler, TenantContextMiddleware
from slowapi.errors import RateLimitExceeded

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TenantContextMiddleware)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# CORS middleware - configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID"],
)


# Include API routes
from .api import health, shards, events, frame as frame_api
from .api import export, notifications, scheduler
# NOTE: templates import removed - templates shard handles /api/templates routes

# Authentication routes (must be before other protected routes)
from .auth import auth_router
app.include_router(auth_router)

app.include_router(health.router, tags=["Health"])
# NOTE: Frame's documents router removed - documents shard handles /api/documents routes
# NOTE: Frame's entities router removed - entities shard handles /api/entities routes
# NOTE: Frame's projects router removed - projects shard handles /api/projects routes
# Active project management moved to /api/frame/active-project
app.include_router(shards.router, prefix="/api/shards", tags=["Shards"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(frame_api.router, prefix="/api/frame", tags=["Frame"])

# Output Services API routes
# NOTE: export router removed - export shard handles /api/export routes
# NOTE: templates router removed - templates shard handles /api/templates routes
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["Scheduler"])


# Static file serving for Shell UI
# In production/Docker, Frame serves the built React app
def setup_static_serving():
    """Set up static file serving for the Shell UI."""
    import os
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Look for Shell dist directory
    # Try multiple paths for different deployment scenarios
    possible_paths = [
        # Docker container path
        Path("/app/frontend/dist"),
        # Development paths (relative to Frame package)
        Path(__file__).parent.parent.parent / "arkham-shard-shell" / "dist",
        Path(__file__).parent.parent.parent.parent / "arkham-shard-shell" / "dist",
        # CWD-relative paths
        Path.cwd() / "packages" / "arkham-shard-shell" / "dist",
        Path.cwd() / "arkham-shard-shell" / "dist",
        Path.cwd() / "frontend" / "dist",
    ]

    shell_dist = None
    for path in possible_paths:
        if path.exists() and (path / "index.html").exists():
            shell_dist = path
            break

    if shell_dist:
        logger.info(f"Serving Shell UI from: {shell_dist}")

        # Mount static assets
        assets_path = shell_dist / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

        # Serve index.html for all non-API routes (SPA fallback)
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            # API routes are handled by routers above
            if path.startswith("api/"):
                return {"error": "Not found"}

            # Serve static files if they exist
            file_path = shell_dist / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)

            # SPA fallback - serve index.html
            return FileResponse(shell_dist / "index.html")
    else:
        logger.info("Shell UI dist not found - static serving disabled")
        logger.info("Build the Shell with 'npm run build' in arkham-shard-shell/")
        logger.info(f"Searched paths: {[str(p) for p in possible_paths]}")


def get_frame() -> ArkhamFrame:
    """Get the global Frame instance."""
    if frame is None:
        raise RuntimeError("Frame not initialized")
    return frame
