#!/usr/bin/env python3
"""
ArkhamMirror Setup Script

One-command setup for new installations.
Handles virtual environment, dependencies, Docker, and model downloads.

Usage:
    python scripts/setup.py
"""

import sys
import subprocess
from pathlib import Path

# Get project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).parent.parent


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_step(step: int, text: str):
    """Print a step indicator."""
    print(f"\n[{step}/6] {text}")


def print_success(text: str):
    """Print a success message."""
    print(f"  ✓ {text}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"  ⚠ {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"  ✗ {text}")


def check_python_version() -> bool:
    """Check if Python version is 3.10+."""
    if sys.version_info < (3, 10):
        print_error(f"Python 3.10+ required, found {sys.version}")
        return False
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def check_docker() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print_success("Docker is running")
            return True
        else:
            print_error("Docker is installed but not running")
            print_warning("Please start Docker Desktop and try again")
            return False
    except FileNotFoundError:
        print_error("Docker not found")
        print_warning(
            "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
        )
        return False
    except subprocess.TimeoutExpired:
        print_error("Docker check timed out")
        return False


def create_venv() -> bool:
    """Create virtual environment if needed."""
    venv_path = PROJECT_ROOT / "venv"

    if venv_path.exists():
        print_success("Virtual environment already exists")
        return True

    try:
        print("  Creating virtual environment...")
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True,
        )
        print_success("Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to create venv: {e}")
        return False


def get_pip_executable() -> str:
    """Get the pip executable path."""
    venv_path = PROJECT_ROOT / "venv"
    if sys.platform == "win32":
        return str(venv_path / "Scripts" / "pip.exe")
    else:
        return str(venv_path / "bin" / "pip")


def get_python_executable() -> str:
    """Get the Python executable path in venv."""
    venv_path = PROJECT_ROOT / "venv"
    if sys.platform == "win32":
        return str(venv_path / "Scripts" / "python.exe")
    else:
        return str(venv_path / "bin" / "python")


def install_dependencies() -> bool:
    """Install Python dependencies."""
    pip = get_pip_executable()
    requirements = PROJECT_ROOT / "app" / "requirements.txt"

    if not requirements.exists():
        print_error(f"Requirements not found: {requirements}")
        return False

    try:
        print("  Installing dependencies (this may take a few minutes)...")
        subprocess.run(
            [pip, "install", "-r", str(requirements), "--quiet"],
            check=True,
            capture_output=True,
            text=True,
        )
        print_success("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print_error(
            f"Failed to install dependencies: {e.stderr[:200] if e.stderr else e}"
        )
        print_warning("Try running manually: pip install -r app/requirements.txt")
        return False


def start_docker_services() -> bool:
    """Start Docker containers."""
    docker_path = PROJECT_ROOT / "docker"

    if not (docker_path / "docker-compose.yml").exists():
        print_error(f"docker-compose.yml not found in {docker_path}")
        return False

    try:
        print("  Starting Docker containers...")
        subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=str(docker_path),
            check=True,
            capture_output=True,
        )
        print_success("Docker containers started (PostgreSQL, Qdrant, Redis)")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start containers: {e}")
        return False


def download_spacy_model() -> bool:
    """Download spaCy language model."""
    python = get_python_executable()

    try:
        # Check if already installed
        result = subprocess.run(
            [python, "-c", "import spacy; spacy.load('en_core_web_sm')"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print_success("spaCy model already installed")
            return True
    except Exception:
        pass

    try:
        print("  Downloading spaCy language model...")
        subprocess.run(
            [python, "-m", "spacy", "download", "en_core_web_sm"],
            check=True,
            capture_output=True,
        )
        print_success("spaCy model downloaded")
        return True
    except subprocess.CalledProcessError as e:
        print_warning("spaCy model download failed (optional for NER)")
        return True  # Non-critical


def run_health_check() -> bool:
    """Run health check to verify setup."""
    python = get_python_executable()
    db_init = PROJECT_ROOT / "app" / "arkham" / "services" / "db" / "db_init.py"

    try:
        print("  Verifying database connection...")
        result = subprocess.run(
            [python, str(db_init)], capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print_success("Database initialized and ready")
            return True
        else:
            print_error("Database initialization failed")
            print(result.stderr[:500] if result.stderr else "")
            return False
    except subprocess.TimeoutExpired:
        print_error("Health check timed out")
        return False
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False


def main():
    """Main setup function."""
    print_header("🔮 ArkhamMirror Setup")
    print("Setting up your local investigation platform...")

    # Step 1: Check Python
    print_step(1, "Checking Python version")
    if not check_python_version():
        return 1

    # Step 2: Check Docker
    print_step(2, "Checking Docker")
    if not check_docker():
        return 1

    # Step 3: Create venv
    print_step(3, "Setting up Python environment")
    if not create_venv():
        return 1

    # Step 4: Install dependencies
    print_step(4, "Installing dependencies")
    if not install_dependencies():
        return 1

    # Step 5: Start Docker
    print_step(5, "Starting infrastructure")
    if not start_docker_services():
        return 1

    # Give Docker a moment to start
    import time

    print("  Waiting for services to start...")
    time.sleep(5)

    # Step 6: Health check
    print_step(6, "Verifying setup")
    download_spacy_model()
    if not run_health_check():
        print_warning(
            "Setup completed with issues - services may need more time to start"
        )

    # Done!
    print_header("🎉 Setup Complete!")

    print("To start ArkhamMirror:")
    print()
    if sys.platform == "win32":
        print("    .\\venv\\Scripts\\activate")
    else:
        print("    source venv/bin/activate")
    print("    cd app")
    print("    python start_app.py --force")
    print()
    print("Then open: http://localhost:3000")
    print()
    print("Optional: Start LM Studio for AI features")
    print("  https://lmstudio.ai/")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
