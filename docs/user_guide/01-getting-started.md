# Getting Started

## Prerequisites

ArkhamMirror is designed to run on standard consumer hardware, but AI features require decent specs.

### Minimum Requirements

* **OS**: Windows 10/11, macOS, or Linux
* **RAM**: 8GB (16GB recommended)
* **Storage**: 20GB free space
* **Software**:
  * [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Required for database)
  * [Python 3.10+](https://www.python.org/downloads/)

### Recommended for AI Features

* **NVIDIA GPU** (6GB+ VRAM)
* **[LM Studio](https://lmstudio.ai/)** (Free local LLM server)

---

## 🚀 Quick Install (Windows)

We provide a "Smart Installer" that handles most configuration for you.

1. **Download & Extract** the latest release.
2. Double-click `setup.bat`.
3. Follow the prompts from the **AI Setup Wizard**.

The installer will:

* Check your RAM and Disk space.
* Verify Docker and Python versions.
* Configure your local environment.

---

## 🐧 Quick Install (Mac / Linux)

1. Open your terminal.
2. Navigate to the project folder.
3. Run the setup script:

    ```bash
    chmod +x setup.sh
    ./setup.sh
    ```

---

## 🛠️ Manual Installation

If you prefer to configure things yourself:

1. **Start Infrastructure**:

    ```bash
    cd docker
    docker compose up -d
    ```

2. **Create Python Environment**:

    ```bash
    python -m venv venv
    source venv/bin/activate  # or .\venv\Scripts\activate on Windows
    pip install -r app/requirements.txt
    ```

3. **Run the Application**:

    ```bash
    cd app
    python start_app.py --force
    ```

---

## 🤖 Setting up Local AI (Optional)

To enable "Chat with Data", "Speculation Mode", and "Qwen-VL OCR":

1. Install **LM Studio**.
2. Download a model (e.g., `Qwen2.5-14B-Instruct` or `Llama-3-8B`).
3. Go to the **Developer/Server** tab (↔️ icon).
4. Start the Server on port `1234` (default).

ArkhamMirror will automatically detect the server and enable AI features.
