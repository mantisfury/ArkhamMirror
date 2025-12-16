#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "================================================================"
echo "   ArkhamMirror Setup Wizard"
echo "================================================================"
echo ""

# ====================================================================
# UTILITY FUNCTIONS
# ====================================================================

detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    elif grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
        echo "wsl"
    else
        echo "linux"
    fi
}

detect_arch() {
    local arch=$(uname -m)
    case $arch in
        x86_64) echo "amd64" ;;
        aarch64|arm64) echo "arm64" ;;
        *) echo "$arch" ;;
    esac
}

get_free_disk_gb() {
    # Cross-platform disk space detection
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: df outputs in 512-byte blocks by default, use -g for GB
        df -g . 2>/dev/null | tail -1 | awk '{print $4}'
    else
        # Linux: -BG flag for GB output (not available on macOS)
        df -BG . 2>/dev/null | tail -1 | awk '{gsub(/G/,"",$4); print $4}'
    fi
}

get_total_ram_gb() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS: hw.memsize returns bytes
        sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024/1024/1024)}'
    else
        # Linux: free -g returns GB directly
        # Also works in WSL
        free -g 2>/dev/null | awk '/^Mem:/{print $2}'
    fi
}

check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1 || netstat -tuln 2>/dev/null | grep -q ":$port "; then
        return 1
    fi
    return 0
}

OS=$(detect_os)
ARCH=$(detect_arch)

echo "Detected: $OS ($ARCH)"
echo ""

# ====================================================================
# PRE-FLIGHT: Disk Space Check
# ====================================================================
echo "[1/7] Checking disk space..."

FREE_GB=$(get_free_disk_gb)
if [[ -z "$FREE_GB" ]] || [[ "$FREE_GB" -lt 15 ]]; then
    echo -e "${RED}[X] Insufficient disk space. Need 15GB free, found ~${FREE_GB}GB.${NC}"
    exit 1
fi
echo -e "    ${GREEN}[OK]${NC} Disk space sufficient (~${FREE_GB}GB free)"

# ====================================================================
# PRE-FLIGHT: RAM Check
# ====================================================================
echo "[2/7] Checking RAM..."

RAM_GB=$(get_total_ram_gb)
if [[ -z "$RAM_GB" ]] || [[ "$RAM_GB" -lt 8 ]]; then
    echo -e "${RED}[X] Insufficient RAM. Need 8GB minimum, found ~${RAM_GB}GB.${NC}"
    exit 1
fi
if [[ "$RAM_GB" -lt 16 ]]; then
    echo -e "    ${YELLOW}[!]${NC} RAM is below recommended 16GB. Some features may be slow."
else
    echo -e "    ${GREEN}[OK]${NC} RAM sufficient (~${RAM_GB}GB)"
fi

# ====================================================================
# PRE-FLIGHT: Port Check
# ====================================================================
echo "[3/7] Checking required ports..."

PORTS_OK=1
for port in 3000 5435 6343 6344 6380 8000; do
    if ! check_port $port; then
        echo -e "    ${RED}[X]${NC} Port $port is already in use"
        PORTS_OK=0
    fi
done

if [[ "$PORTS_OK" -eq 0 ]]; then
    echo ""
    echo "Some required ports are in use. Please close conflicting applications."
    exit 1
fi
echo -e "    ${GREEN}[OK]${NC} All required ports available"

# ====================================================================
# PRE-FLIGHT: Existing Installation Check
# ====================================================================
echo "[4/7] Checking for existing installation..."

if [[ -f ".arkham_install_state.json" ]]; then
    echo -e "    ${YELLOW}[!]${NC} Previous installation detected."
    echo ""
    read -p "    [F]resh install, [R]esume previous, or [U]pdate? " -n 1 -r
    echo ""
    case $REPLY in
        [Ff])
            echo "    Starting fresh installation..."
            rm -rf venv .arkham_install_state.json 2>/dev/null || true
            ;;
        [Rr])
            echo "    Resuming previous installation..."
            ;;
        [Uu])
            echo "    Update mode - keeping existing data..."
            ;;
        *)
            echo "    Invalid choice. Starting fresh..."
            rm -rf venv .arkham_install_state.json 2>/dev/null || true
            ;;
    esac
fi

# ====================================================================
# PYTHON CHECK AND INSTALLATION
# ====================================================================
echo "[5/7] Checking Python..."

PYTHON_CMD=""

# Try python3 first
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
    PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)

    if [[ "$PY_MAJOR" -ge 3 ]] && [[ "$PY_MINOR" -ge 11 ]]; then
        PYTHON_CMD="python3"
    fi
fi

if [[ -z "$PYTHON_CMD" ]]; then
    echo -e "    ${YELLOW}[!]${NC} Python 3.11+ not found. Installing..."

    case $OS in
        macos)
            if ! command -v brew &> /dev/null; then
                echo "    Installing Homebrew first..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

                # Add brew to PATH for this session
                if [[ "$ARCH" == "arm64" ]]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                else
                    eval "$(/usr/local/bin/brew shellenv)"
                fi
            fi
            brew install python@3.11
            PYTHON_CMD="python3.11"
            ;;
        ubuntu|debian|pop)
            sudo apt update
            sudo apt install -y python3.11 python3.11-venv python3-pip
            PYTHON_CMD="python3.11"
            ;;
        fedora)
            sudo dnf install -y python3.11 python3.11-pip
            PYTHON_CMD="python3.11"
            ;;
        arch|manjaro)
            sudo pacman -Sy --noconfirm python python-pip
            PYTHON_CMD="python3"
            ;;
        wsl)
            sudo apt update
            sudo apt install -y python3.11 python3.11-venv python3-pip
            PYTHON_CMD="python3.11"
            ;;
        *)
            echo -e "${RED}[X] Unknown OS. Please install Python 3.11+ manually.${NC}"
            exit 1
            ;;
    esac
fi

if [[ -z "$PYTHON_CMD" ]] || ! $PYTHON_CMD --version &> /dev/null; then
    echo -e "${RED}[X] Failed to find or install Python 3.11+${NC}"
    exit 1
fi

echo -e "    ${GREEN}[OK]${NC} Python found: $PYTHON_CMD"

# ====================================================================
# DOCKER CHECK AND INSTALLATION
# ====================================================================
echo "[6/7] Checking Docker..."

if ! command -v docker &> /dev/null; then
    echo -e "    ${YELLOW}[!]${NC} Docker not found. Installing..."

    case $OS in
        macos)
            echo "    Please install Docker Desktop from https://docker.com"
            echo "    (Homebrew installation of Docker Desktop is not recommended)"
            open "https://www.docker.com/products/docker-desktop/"
            read -p "    Press Enter after Docker Desktop is installed..." -r
            ;;
        ubuntu|debian|pop)
            curl -fsSL https://get.docker.com | sudo sh
            sudo usermod -aG docker $USER
            echo -e "    ${YELLOW}[!]${NC} You may need to log out and back in for Docker permissions."
            ;;
        fedora)
            sudo dnf install -y docker-ce docker-ce-cli containerd.io
            sudo systemctl enable --now docker
            sudo usermod -aG docker $USER
            ;;
        arch|manjaro)
            sudo pacman -Sy --noconfirm docker docker-compose
            sudo systemctl enable --now docker
            sudo usermod -aG docker $USER
            ;;
        wsl)
            echo "    For WSL, please install Docker Desktop for Windows."
            echo "    Enable 'Use the WSL 2 based engine' in Docker Desktop settings."
            read -p "    Press Enter when Docker Desktop is ready..." -r
            ;;
        *)
            echo "    Please install Docker manually for your distribution."
            read -p "    Press Enter when Docker is installed..." -r
            ;;
    esac
fi

# Verify Docker is running
if ! docker info &> /dev/null; then
    echo -e "    ${YELLOW}[!]${NC} Docker is installed but not running."

    case $OS in
        macos)
            echo "    Please start Docker Desktop."
            open -a Docker 2>/dev/null || true
            ;;
        wsl)
            echo "    Please start Docker Desktop for Windows."
            ;;
        *)
            echo "    Starting Docker service..."
            sudo systemctl start docker 2>/dev/null || true
            ;;
    esac

    echo "    Waiting for Docker to start..."
    for i in {1..30}; do
        if docker info &> /dev/null; then
            break
        fi
        sleep 2
    done

    if ! docker info &> /dev/null; then
        echo -e "${RED}[X] Docker failed to start. Please start it manually and try again.${NC}"
        exit 1
    fi
fi

echo -e "    ${GREEN}[OK]${NC} Docker is ready"

# ====================================================================
# LM STUDIO CHECK
# ====================================================================
echo "[7/7] Checking LM Studio..."

NO_AI=0
if ! curl -s --connect-timeout 5 http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo -e "    ${YELLOW}[!]${NC} LM Studio server not responding."
    echo ""
    echo "    Please ensure:"
    echo "      1. LM Studio is installed (from lmstudio.ai)"
    echo "      2. A model is downloaded (recommend: qwen3-vl-8b)"
    echo "      3. The server is started (click 'Start Server' in LM Studio)"
    echo ""
    read -p "    Continue without AI assistance? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "    Please start LM Studio and run this setup again."
        exit 0
    fi
    echo "    Continuing in text-only mode..."
    NO_AI=1
else
    echo -e "    ${GREEN}[OK]${NC} LM Studio is responding"
fi

# ====================================================================
# HAND OFF TO PYTHON AI WIZARD
# ====================================================================
echo ""
echo "================================================================"
echo "   Pre-flight checks complete! Launching AI Setup Wizard..."
echo "================================================================"
echo ""

if [[ "$NO_AI" -eq 1 ]]; then
    $PYTHON_CMD scripts/ai_installer.py --no-ai
else
    $PYTHON_CMD scripts/ai_installer.py
fi

if [[ $? -ne 0 ]]; then
    echo ""
    echo -e "${RED}[X] Installation encountered an error.${NC}"
    echo "    Check the output above for details."
    echo "    You can run this script again to resume."
    exit 1
fi

echo ""
echo "================================================================"
echo "   Installation Complete!"
echo "================================================================"
echo ""
