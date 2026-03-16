#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.thema-api-explorer"
REPO="https://github.com/Thema-AI/thema-api-explorer.git"

# Clone or pull latest
if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull -q 2>/dev/null || true
else
    echo "Installing thema-api-explorer..."
    rm -rf "$INSTALL_DIR"
    git clone -q "$REPO" "$INSTALL_DIR"
fi

# Create venv if needed
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    python3 -m venv "$INSTALL_DIR/.venv"
fi

source "$INSTALL_DIR/.venv/bin/activate"
pip install -q -e "$INSTALL_DIR"

exec thema-api-explorer "$@"
