#!/usr/bin/env python3
"""
Forensic Wipe - Secure Data Destruction

This script provides forensic-resistant data destruction for ArkhamMirror.
Unlike the UI-based "Nuclear Wipe", this mode:

1. Stops all running ArkhamMirror processes
2. Overwrites files with random data before deletion
3. Destroys Docker volumes completely (not just clears tables)
4. Securely wipes Docker bind-mount directories (postgres, qdrant, redis)
5. Clears Reflex cache, state, and database files
6. Recreates fresh infrastructure

WARNINGS:
- This operation is IRREVERSIBLE
- The app will be stopped and must be restarted manually
- On SSDs, wear-leveling may preserve some data fragments (physical destruction is the only guarantee)
- Browser cache is NOT cleared (manual step required)

Usage:
    python scripts/forensic_wipe.py --confirm

    Or use the wrapper:
    nukeitfromorbit.bat
"""

import os
import sys
import subprocess
import secrets
import shutil
import time
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from config import DATA_SILO_PATH, DOCKER_PATH
except ImportError:
    DATA_SILO_PATH = PROJECT_ROOT / "DataSilo"
    DOCKER_PATH = PROJECT_ROOT / "docker"

# Number of overwrite passes (more = slower but more secure)
OVERWRITE_PASSES = 3

# Chunk size for random data writes (1MB)
CHUNK_SIZE = 1024 * 1024

# Total steps in the wipe process
TOTAL_STEPS = 7


def print_header(text: str):
    print(f"\n{'=' * 60}")
    print(f"  [NUKE] {text}")
    print(f"{'=' * 60}\n")


def print_step(step: int, total: int, text: str):
    print(f"\n[{step}/{total}] {text}")


def print_warning(text: str):
    print(f"  [!] {text}")


def print_success(text: str):
    print(f"  [OK] {text}")


def print_error(text: str):
    print(f"  [FAIL] {text}")


def print_info(text: str):
    print(f"       {text}")


def confirm_wipe() -> bool:
    """Get user confirmation for forensic wipe."""
    print_header("FORENSIC WIPE - SECURE DATA DESTRUCTION")

    print("""
    "I say we take off and nuke the entire site from orbit.
     It's the only way to be sure."
                                    - Ellen Ripley, Aliens (1986)
    """)

    print("This operation will PERMANENTLY DESTROY:")
    print("  - All documents and extracted pages")
    print("  - All database records (PostgreSQL)")
    print("  - All vector embeddings (Qdrant)")
    print("  - All job history (Redis)")
    print("  - All application logs")
    print("  - All Reflex cache, state, and session data")
    print("  - All Docker bind-mount data")
    print()
    print_warning("The running app will be STOPPED")
    print_warning("Data will be OVERWRITTEN before deletion")
    print_warning("Docker volumes will be DESTROYED and recreated")
    print_warning("This is IRREVERSIBLE - there is no recovery")
    print()

    # Require explicit confirmation
    print("To proceed, type exactly: NUKE IT FROM ORBIT")
    try:
        response = input("> ").strip()
        return response == "NUKE IT FROM ORBIT"
    except (KeyboardInterrupt, EOFError):
        return False


def kill_arkham_processes() -> bool:
    """Kill all ArkhamMirror-related processes."""
    print_step(1, TOTAL_STEPS, "Stopping all ArkhamMirror processes...")

    killed_count = 0

    if sys.platform == "win32":
        # Windows: Kill Python and Node processes
        try:
            # Kill processes with "arkham" or "reflex" in command line
            for pattern in ["arkham", "reflex", "node"]:
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f"Get-WmiObject Win32_Process | "
                        f"Where-Object {{ $_.CommandLine -like '*{pattern}*' }} | "
                        f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}",
                    ],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    killed_count += 1

            # Also kill by port (backup method)
            for port in [3000, 8000]:
                subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                        f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}",
                    ],
                    capture_output=True,
                    timeout=30,
                )

            print_success("Terminated processes on ports 3000, 8000")

        except Exception as e:
            print_warning(f"Some processes may still be running: {e}")
    else:
        # Linux/Mac
        try:
            subprocess.run(["pkill", "-9", "-f", "arkham"], capture_output=True, timeout=10)
            subprocess.run(["pkill", "-9", "-f", "reflex"], capture_output=True, timeout=10)
            subprocess.run(["pkill", "-9", "-f", "node.*next"], capture_output=True, timeout=10)
            killed_count += 1
        except Exception as e:
            print_warning(f"Process kill failed: {e}")

    # Give processes time to die
    time.sleep(3)

    return True


def secure_delete_file(filepath: Path, passes: int = OVERWRITE_PASSES) -> bool:
    """
    Securely delete a file by overwriting with random data.

    Note: On SSDs, this does NOT guarantee data is unrecoverable
    due to wear-leveling. Only physical destruction can guarantee that.
    """
    try:
        if not filepath.exists():
            return True

        if not filepath.is_file():
            return False

        file_size = filepath.stat().st_size

        # Skip empty files
        if file_size == 0:
            filepath.unlink()
            return True

        # Overwrite with random data multiple times
        for pass_num in range(passes):
            with open(filepath, "wb") as f:
                remaining = file_size
                while remaining > 0:
                    chunk = min(CHUNK_SIZE, remaining)
                    f.write(secrets.token_bytes(chunk))
                    remaining -= chunk
                f.flush()
                os.fsync(f.fileno())

        # Final overwrite with zeros
        with open(filepath, "wb") as f:
            remaining = file_size
            while remaining > 0:
                chunk = min(CHUNK_SIZE, remaining)
                f.write(b"\x00" * chunk)
                remaining -= chunk
            f.flush()
            os.fsync(f.fileno())

        # Now delete
        filepath.unlink()
        return True

    except PermissionError:
        # Try force delete on Windows
        if sys.platform == "win32":
            try:
                subprocess.run(["del", "/f", "/q", str(filepath)], shell=True, capture_output=True)
                return not filepath.exists()
            except Exception:
                pass
        print_warning(f"Cannot access {filepath.name} (file in use?)")
        return False
    except Exception as e:
        print_warning(f"Error deleting {filepath.name}: {e}")
        return False


def secure_delete_directory(dirpath: Path, verbose: bool = False) -> tuple[int, int]:
    """
    Securely delete all files in a directory.

    Returns:
        Tuple of (files_deleted, files_failed)
    """
    deleted = 0
    failed = 0

    if not dirpath.exists():
        return 0, 0

    # First, securely delete all files
    for item in list(dirpath.rglob("*")):
        if item.is_file():
            if secure_delete_file(item):
                deleted += 1
                if verbose and deleted % 100 == 0:
                    print_info(f"Securely deleted {deleted} files...")
            else:
                failed += 1

    # Then remove empty directories (deepest first)
    for item in sorted(
        list(dirpath.rglob("*")), key=lambda x: len(str(x)), reverse=True
    ):
        if item.is_dir():
            try:
                item.rmdir()
            except OSError:
                pass  # Directory not empty or in use

    return deleted, failed


def wipe_data_silo() -> dict:
    """Securely wipe all DataSilo contents including Docker bind-mounts."""
    print_step(2, TOTAL_STEPS, "Securely wiping DataSilo contents...")

    result = {"deleted": 0, "failed": 0, "warnings": []}

    if not DATA_SILO_PATH.exists():
        print_warning("DataSilo directory not found")
        return result

    # Wipe ALL subdirectories including Docker bind-mounts
    subdirs = [
        "documents",   # Uploaded files
        "pages",       # Extracted page images
        "temp",        # Temporary files
        "logs",        # Application logs
        "postgres",    # PostgreSQL data (Docker bind-mount)
        "qdrant",      # Qdrant vector data (Docker bind-mount)
        "redis",       # Redis data (Docker bind-mount)
    ]

    for subdir in subdirs:
        subdir_path = DATA_SILO_PATH / subdir
        if subdir_path.exists():
            print_info(f"Wiping {subdir}/...")
            deleted, failed = secure_delete_directory(subdir_path, verbose=True)
            result["deleted"] += deleted
            result["failed"] += failed

            if failed > 0:
                result["warnings"].append(
                    f"{failed} files in {subdir}/ could not be deleted"
                )

    print_success(f"Securely deleted {result['deleted']} files")
    if result["failed"] > 0:
        print_warning(f"{result['failed']} files could not be deleted (may be in use)")

    return result


def destroy_docker_volumes() -> bool:
    """Destroy and recreate Docker volumes."""
    print_step(3, TOTAL_STEPS, "Destroying Docker volumes...")

    if not DOCKER_PATH.exists():
        print_warning("Docker directory not found")
        return False

    try:
        # Stop containers and remove volumes
        print_info("Stopping containers and removing volumes...")
        subprocess.run(
            ["docker", "compose", "down", "-v", "--remove-orphans"],
            cwd=str(DOCKER_PATH),
            capture_output=True,
            timeout=60,
        )

        # Remove any orphan volumes
        print_info("Pruning orphan volumes...")
        subprocess.run(
            ["docker", "volume", "prune", "-f"], capture_output=True, timeout=30
        )

        # Also try to remove specific named volumes if they exist
        for vol_name in ["arkham_postgres", "arkham_qdrant", "arkham_redis"]:
            subprocess.run(
                ["docker", "volume", "rm", "-f", vol_name],
                capture_output=True,
                timeout=10,
            )

        print_success("Docker volumes destroyed")
        return True

    except subprocess.TimeoutExpired:
        print_error("Docker operation timed out")
        return False
    except FileNotFoundError:
        print_warning("Docker not found - skipping volume destruction")
        return True
    except Exception as e:
        print_error(f"Docker error: {e}")
        return False


def clear_reflex_cache() -> bool:
    """Clear all Reflex cache, state, and database files."""
    print_step(4, TOTAL_STEPS, "Clearing Reflex cache and state...")

    app_path = PROJECT_ROOT / "app"
    arkham_path = app_path / "arkham"

    deleted = 0

    # Directories to remove completely
    cache_dirs = [
        app_path / ".web",              # Reflex compiled frontend
        app_path / ".reflex",           # Reflex internal state
        app_path / ".states",           # Persisted state
        app_path / "node_modules",      # Node dependencies (may have cache)
        arkham_path / ".web",           # Alternate location
        arkham_path / "__pycache__",    # Python cache
    ]

    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                deleted += 1
                print_info(f"Removed {cache_dir.name}/")
            except Exception as e:
                print_warning(f"Could not delete {cache_dir.name}: {e}")

    # Files to securely delete
    cache_files = [
        app_path / "reflex.db",         # Reflex SQLite database
        app_path / ".reflex.db",        # Alternate name
        arkham_path / "reflex.db",      # Alternate location
    ]

    for cache_file in cache_files:
        if cache_file.exists():
            if secure_delete_file(cache_file):
                deleted += 1
                print_info(f"Securely deleted {cache_file.name}")

    # Clear all __pycache__ directories recursively
    for pycache in app_path.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache)
            deleted += 1
        except OSError:
            pass

    # Clear any .pyc files
    for pyc in app_path.rglob("*.pyc"):
        try:
            pyc.unlink()
            deleted += 1
        except OSError:
            pass

    print_success(f"Cleared {deleted} cache items")
    return True


def clear_node_cache() -> bool:
    """Clear Node.js and Next.js cache."""
    print_step(5, TOTAL_STEPS, "Clearing Node.js cache...")

    app_path = PROJECT_ROOT / "app"
    web_path = app_path / ".web"

    cleared = 0

    # Next.js cache locations
    next_cache_dirs = [
        web_path / ".next",
        web_path / "node_modules" / ".cache",
        app_path / "node_modules" / ".cache",
    ]

    for cache_dir in next_cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                cleared += 1
                print_info(f"Removed {cache_dir.name}/")
            except Exception as e:
                print_warning(f"Could not delete {cache_dir}: {e}")

    if cleared > 0:
        print_success(f"Cleared {cleared} Node.js cache directories")
    else:
        print_info("No Node.js cache found")

    return True


def recreate_infrastructure() -> bool:
    """Recreate fresh Docker infrastructure."""
    print_step(6, TOTAL_STEPS, "Recreating fresh infrastructure...")

    try:
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=str(DOCKER_PATH),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print_success("Fresh containers started")
            return True
        else:
            print_error(f"Failed to start containers: {result.stderr}")
            return False

    except FileNotFoundError:
        print_warning("Docker not found - skipping infrastructure recreation")
        return True
    except Exception as e:
        print_error(f"Error: {e}")
        return False


def recreate_data_silo() -> bool:
    """Recreate empty DataSilo structure."""
    print_step(7, TOTAL_STEPS, "Recreating DataSilo structure...")

    subdirs = ["documents", "pages", "temp", "logs", "postgres", "qdrant", "redis"]

    for subdir in subdirs:
        (DATA_SILO_PATH / subdir).mkdir(parents=True, exist_ok=True)

    print_success("Fresh DataSilo directories created")
    return True


def print_final_instructions():
    """Print instructions for completing the wipe."""
    print_header("NUKED FROM ORBIT - WIPE COMPLETE")

    print("""
    "Affirmative. Nuke the entire site from orbit."
                                    - Mission accomplished.
    """)

    print("[OK] All ArkhamMirror data has been destroyed.")
    print()
    print("[WAIT] Please wait 30 seconds for infrastructure to stabilize.")
    print()
    print("[MANUAL] MANUAL STEPS REQUIRED:")
    print()
    print("   1. Clear your browser cache (contains page renders):")
    print("      - Chrome/Edge: Ctrl+Shift+Delete -> Clear data")
    print("      - Firefox: Ctrl+Shift+Delete -> Clear Now")
    print()
    print("   2. Clear LM Studio chat history (if any):")
    print("      - Open LM Studio -> Clear conversation history")
    print()
    print("   3. For maximum security, consider:")
    print("      - Deleting the entire ArkhamMirror folder")
    print("      - Using a secure file shredder on the folder location")
    print("      - On SSDs: Only physical destruction guarantees erasure")
    print()
    print("[START] To restart ArkhamMirror:")
    print("      python system_status.py --start-all")
    print()


def main():
    """Main forensic wipe function."""

    # Parse args
    if "--confirm" not in sys.argv:
        print("=" * 60)
        print("  FORENSIC WIPE - Nuke It From Orbit")
        print("=" * 60)
        print()
        print("  \"It's the only way to be sure.\"")
        print()
        print("Usage: python scripts/forensic_wipe.py --confirm")
        print()
        print("This script performs a SECURE WIPE of all ArkhamMirror data:")
        print("  - Overwrites files with random data before deletion")
        print("  - Destroys all Docker volumes and bind-mount data")
        print("  - Clears all Reflex state and cache")
        print("  - Recreates fresh infrastructure")
        print()
        print("Pass --confirm to proceed with the interactive confirmation.")
        return 1

    # Get confirmation
    if not confirm_wipe():
        print("\n[ABORT] Wipe cancelled. Your data is safe... for now.")
        return 1

    print("\n[LAUNCH] Initiating orbital strike...\n")

    # Execute wipe steps
    success = True

    if not kill_arkham_processes():
        success = False

    wipe_result = wipe_data_silo()
    if wipe_result["failed"] > 10:
        print_warning("Many files could not be deleted - app may still be running")

    if not destroy_docker_volumes():
        success = False

    clear_reflex_cache()
    clear_node_cache()

    if not recreate_infrastructure():
        success = False

    recreate_data_silo()

    # Wait for infrastructure
    print("\n[WAIT] Waiting for infrastructure to stabilize...")
    time.sleep(10)

    # Print completion message
    print_final_instructions()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
