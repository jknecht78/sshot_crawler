#!/bin/bash

# Speed Project Installer Script
# Sets up virtual environment, installs dependencies, and configures the project

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_BIN="$HOME/.local/bin"

echo "=== Speed Project Installer ==="
echo "Project directory: $PROJECT_DIR"
echo ""

# Step 1: Create virtual environment
echo "[1/6] Installing system dependencies for Chromium..."
sudo apt-get update

pick_pkg() {
    local choices="$1"
    local IFS='|'
    for pkg in $choices; do
        if apt-cache show "$pkg" >/dev/null 2>&1; then
            echo "$pkg"
            return 0
        fi
    done
    return 1
}

PKG_CHOICES=(
    "build-essential"
    "python3.12-dev|python3-dev"
    "libnss3"
    "libx11-6"
    "libxext6"
    "libxrender1"
    "libxrandr2"
    "libasound2t64|libasound2"
    "libpangocairo-1.0-0"
    "libpango-1.0-0"
    "libgdk-pixbuf2.0-0"
    "libfontconfig1"
    "libfreetype6"
    "libxinerama1"
    "libxi6"
    "libxtst6"
    "libxss1"
    "libxcursor1"
    "libxdamage1"
    "libatk1.0-0t64|libatk1.0-0"
    "libatk-bridge2.0-0t64|libatk-bridge2.0-0"
    "libgbm1"
    "libgtk-3-0t64|libgtk-3-0"
    "libnspr4"
)

INSTALL_PKGS=()
for choice in "${PKG_CHOICES[@]}"; do
    pkg="$(pick_pkg "$choice")" || {
        echo "ERROR: Could not resolve package from choices: $choice"
        exit 1
    }
    INSTALL_PKGS+=("$pkg")
done

sudo apt-get install -y "${INSTALL_PKGS[@]}"

echo "[2/6] Creating Python virtual environment..."
if command -v python3.12 &> /dev/null; then
    python3.12 -m venv "$VENV_DIR" --without-pip
elif command -v python3 &> /dev/null; then
    python3 -m venv "$VENV_DIR" --without-pip
else
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Step 3: Install pip
echo "[3/6] Installing pip..."
source "$VENV_DIR/bin/activate"
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
rm get-pip.py
pip install --upgrade pip

# Step 4: Install dependencies
echo "[4/6] Installing project dependencies..."
pip install -r requirements.txt

# Step 5: Install Playwright browsers
echo "[5/6] Installing Playwright chromium..."
python -m playwright install chromium

# Step 6: Create run symlink
echo "[6/6] Creating run symlink..."
chmod +x "$PROJECT_DIR/run.sh"
mkdir -p "$LOCAL_BIN"
ln -sf "$PROJECT_DIR/run.sh" "$LOCAL_BIN/run"

# Ensure ~/.local/bin is in PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "export PATH=\$HOME/.local/bin:\$PATH" >> ~/.bashrc
    source ~/.bashrc
fi

echo ""
echo "=== Installation Complete ==="
echo "Activate the virtual environment with:"
echo "  source .venv/bin/activate"
echo ""
echo "Run the project with:"
echo "  run"
echo ""
