#!/usr/bin/env python3
"""
ArkhamMirror AI-Assisted Installer
"""

import sys
import os
import json
import time
import shutil
import platform
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Constants
PROJECT_ROOT = Path(__file__).parent.parent
STATE_FILE = PROJECT_ROOT / ".arkham_install_state.json"
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
MODEL_URL = "http://localhost:1234/v1/models"
PERSONA_FILE = PROJECT_ROOT / "scripts" / "prompts" / "installer_persona.txt"


# Colors
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_ai(text: str):
    """Print AI response in a distinct color."""
    print(
        f"\n{Colors.CYAN}{Colors.BOLD}ARKHAM:{Colors.ENDC} {Colors.CYAN}{text}{Colors.ENDC}\n"
    )


def print_info(text: str):
    print(f"{Colors.BLUE}[INFO]{Colors.ENDC} {text}")


def print_success(text: str):
    print(f"{Colors.GREEN}[OK]{Colors.ENDC} {text}")


def print_error(text: str):
    print(f"{Colors.FAIL}[ERROR]{Colors.ENDC} {text}")


def print_warning(text: str):
    print(f"{Colors.WARNING}[WARN]{Colors.ENDC} {text}")


# -----------------------------------------------------------------------------
# State Management
# -----------------------------------------------------------------------------
class InstallerState:
    def __init__(self):
        self.data = {
            "version": "2.0",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "platform": self._get_platform_info(),
            "completed_steps": [],
            "failed_step": None,
            "config_choices": {},
        }
        self.load()

    def _get_platform_info(self) -> Dict[str, Any]:
        return {
            "os": platform.system().lower(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version,
        }

    def load(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "r") as f:
                    saved = json.load(f)
                    # Merge saved state (prefer saved values for completed_steps)
                    self.data.update(saved)
            except Exception as e:
                print_warning(f"Could not load state file: {e}")

    def save(self):
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print_warning(f"Could not save state file: {e}")

    def mark_complete(self, step_id: str):
        if step_id not in self.data["completed_steps"]:
            self.data["completed_steps"].append(step_id)
            self.data["failed_step"] = None
            self.save()

    def mark_failed(self, step_id: str, error: str):
        self.data["failed_step"] = step_id
        self.data["last_error"] = error
        self.save()

    def is_complete(self, step_id: str) -> bool:
        return step_id in self.data["completed_steps"]


# -----------------------------------------------------------------------------
# AI Client
# -----------------------------------------------------------------------------
class AIClient:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.model = self._detect_model() if enabled else None
        self.persona = self._load_persona()

    def _load_persona(self) -> str:
        if PERSONA_FILE.exists():
            return PERSONA_FILE.read_text(encoding="utf-8")
        return "You are a helpful installer assistant."

    def _detect_model(self) -> Optional[str]:
        try:
            req = urllib.request.Request(MODEL_URL)
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    models = data.get("data", [])
                    if models:
                        # Prefer qwen
                        for m in models:
                            if "qwen" in m["id"].lower():
                                return m["id"]
                        return models[0]["id"]
        except Exception:
            pass
        return None

    def say(self, message: str, context: str = ""):
        if not self.enabled or not self.model:
            # Fallback text if AI is disabled or offline
            print(f"\n{message}\n")
            return

        system_prompt = f"{self.persona}\n\nCONTEXT:\n{context}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Generate a short response for: {message}",
                },
            ],
            "temperature": 0.7,
            "max_tokens": 150,
        }

        try:
            req = urllib.request.Request(
                LM_STUDIO_URL,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    content = data["choices"][0]["message"]["content"]
                    print_ai(content)
                else:
                    print(f"\n{message}\n")
        except Exception:
            print(f"\n{message}\n")


# -----------------------------------------------------------------------------
# Steps
# -----------------------------------------------------------------------------
def get_python_exec() -> str:
    # In venv
    if sys.platform == "win32":
        return str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
    return str(PROJECT_ROOT / "venv" / "bin" / "python")


def get_pip_exec() -> str:
    if sys.platform == "win32":
        return str(PROJECT_ROOT / "venv" / "Scripts" / "pip.exe")
    return str(PROJECT_ROOT / "venv" / "bin" / "pip")


def step_create_venv(state: InstallerState, ai: AIClient):
    if state.is_complete("create_venv"):
        return

    ai.say(
        "Creating a dedicated Python environment for ArkhamMirror.", "Step: Create venv"
    )

    venv_path = PROJECT_ROOT / "venv"
    if venv_path.exists():
        print_info("Virtual environment exists.")
    else:
        print_info("Creating venv...")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        except subprocess.CalledProcessError as e:
            state.mark_failed("create_venv", str(e))
            raise

    state.mark_complete("create_venv")


def step_install_deps(state: InstallerState, ai: AIClient):
    if state.is_complete("install_deps"):
        return

    ai.say(
        "Installing dependencies. This might take a few minutes.",
        "Step: Install Dependencies",
    )

    pip = get_pip_exec()
    req_file = PROJECT_ROOT / "app" / "requirements.txt"

    try:
        # Upgrade pip first
        subprocess.run([pip, "install", "--upgrade", "pip"], check=True)
        # Install deps
        print_info("Installing requirements...")
        subprocess.run([pip, "install", "-r", str(req_file)], check=True)
    except subprocess.CalledProcessError as e:
        state.mark_failed("install_deps", str(e))
        ai.say(f"Failed to install dependencies. Error: {e}", "Error: Install Deps")
        raise

    state.mark_complete("install_deps")


def step_start_docker(state: InstallerState, ai: AIClient):
    if state.is_complete("start_docker"):
        return

    ai.say(
        "Spinning up the database and vector store containers.", "Step: Start Docker"
    )

    docker_dir = PROJECT_ROOT / "docker"
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d"], cwd=str(docker_dir), check=True
        )
        # Wait for them to be healthy-ish
        time.sleep(5)
    except subprocess.CalledProcessError as e:
        state.mark_failed("start_docker", str(e))
        ai.say("Docker failed to start containers.", "Error: Start Docker")
        raise

    state.mark_complete("start_docker")


def step_download_spacy(state: InstallerState, ai: AIClient):
    if state.is_complete("download_spacy"):
        return

    ai.say(
        "Downloading the language model for entity recognition.", "Step: Spacy Model"
    )

    python = get_python_exec()
    try:
        subprocess.run(
            [python, "-m", "spacy", "download", "en_core_web_sm"], check=True
        )
    except subprocess.CalledProcessError:
        print_warning("Spacy download failed, but continuing.")

    state.mark_complete("download_spacy")


def step_init_db(state: InstallerState, ai: AIClient):
    if state.is_complete("init_db"):
        return

    ai.say("Initializing the database schema.", "Step: Init DB")

    python = get_python_exec()
    db_init_script = PROJECT_ROOT / "app" / "arkham" / "services" / "db" / "db_init.py"

    # We need to set PYTHONPATH so it can import 'app' and 'config'
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    try:
        subprocess.run([python, str(db_init_script)], env=env, check=True)
    except subprocess.CalledProcessError as e:
        # Try running setup.py logic instead if direct script fails?
        # Or maybe just importing the app triggers init?
        # db_init.py is designed to be run directly?
        # The path in setup.py was: app/arkham/services/db/db_init.py
        # Let's trust it.
        state.mark_failed("init_db", str(e))
        raise

    state.mark_complete("init_db")


def step_finish(state: InstallerState, ai: AIClient):
    ai.say("Installation complete! You can now launch ArkhamMirror.", "Step: Finish")
    print_success("Setup finished successfully!")
    print("\nTo start the app:")
    print("  1. cd app")
    print("  2. ..\\venv\\Scripts\\python start_app.py --force  (Windows)")
    print("     or ../venv/bin/python start_app.py --force   (Linux/Mac)")
    print("\nTROUBLESHOOTING:")
    print(
        "  If the frontend fails to load, you may need to install legacy dependencies:"
    )
    print("  1. cd app/.web")
    print("  2. npm install --legacy-peer-deps")

    # Open browser?
    # webbrowser.open("http://localhost:3000")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    use_ai = "--no-ai" not in sys.argv

    state = InstallerState()
    ai = AIClient(enabled=use_ai)

    if use_ai and not ai.model:
        print_warning(
            "AI requested but no model found in LM Studio. Falling back to text mode."
        )
        ai.enabled = False

    ai.say(
        f"Welcome to the ArkhamMirror setup. I see you're on {state.data['platform']['os']}.",
        "Intro",
    )

    steps = [
        step_create_venv,
        step_install_deps,
        step_start_docker,
        step_download_spacy,
        step_init_db,
        step_finish,
    ]

    for step in steps:
        try:
            step(state, ai)
        except Exception as e:
            print_error(f"Step failed: {e}")
            ai.say(f"I ran into an issue: {e}", "Error")
            sys.exit(1)


if __name__ == "__main__":
    main()
