#!/bin/bash
# ============================================================================
#  NUKE IT FROM ORBIT - Forensic Data Wipe for ArkhamMirror
# ============================================================================
#
#  "I say we take off and nuke the entire site from orbit.
#   It's the only way to be sure."
#                                       - Ellen Ripley, Aliens (1986)
#
#  This script performs a SECURE WIPE of all ArkhamMirror data:
#    - Overwrites files with random data before deletion
#    - Destroys all Docker volumes and bind-mount data
#    - Clears all Reflex state and cache
#    - Recreates fresh infrastructure
#
#  WARNING: This operation is IRREVERSIBLE. There is no recovery.
#
# ============================================================================

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

clear

echo ""
echo "============================================================"
echo ""
echo "       _   _ _   _ _  _______   ___ _____ "
echo "      | \ | | | | | |/ / ____| |_ _|_   _|"
echo "      |  \| | | | | ' /| |__     | |  | |  "
echo "      | . \` | | | | . \| __ \    | |  | |  "
echo "      | |\  | |_| | |\ \ ___) |  | |  | |  "
echo "      |_| \_|\___/|_| \_\____/  |___| |_|  "
echo ""
echo "       _____ ____   ___  __  __    ___  ____  ____ ___ _____ "
echo "      |  _  |  _ \ / _ \|  \/  |  / _ \|  _ \| __ )_ _|_   _|"
echo "      | |_) | |_) | | | | |\/| | | | | | |_) |  _ \| |  | |  "
echo "      |  __/|  _ < | |_| | |  | | | |_| |  _ < |_) | |  | |  "
echo "      |_|   |_| \_\\\___/|_|  |_|  \___/|_| \_\____/___| |_|  "
echo ""
echo "============================================================"
echo ""
echo "    \"It's the only way to be sure.\""
echo ""
echo "============================================================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Python not found."
    echo "Please install Python 3.10+ and try again."
    exit 1
fi

# Determine python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Check if the forensic_wipe.py script exists
if [ ! -f "$SCRIPT_DIR/scripts/forensic_wipe.py" ]; then
    echo -e "${RED}[ERROR]${NC} scripts/forensic_wipe.py not found."
    echo "Please run this script from the ArkhamMirror root directory."
    exit 1
fi

echo -e "${YELLOW}This will PERMANENTLY DESTROY all ArkhamMirror data.${NC}"
echo ""
echo "Press Enter to continue, or Ctrl+C to abort..."
read -r

# Run the forensic wipe script
cd "$SCRIPT_DIR"
$PYTHON_CMD scripts/forensic_wipe.py --confirm
EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "============================================================"
    echo -e "${GREEN}  MISSION ACCOMPLISHED - Data has been nuked from orbit.${NC}"
    echo "============================================================"
else
    echo "============================================================"
    echo -e "${YELLOW}  MISSION ABORTED or encountered errors.${NC}"
    echo "============================================================"
fi

echo ""
