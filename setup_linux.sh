#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for Linux system and Python dependencies.
# Usage:
#   bash setup_linux.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 is not installed. Install Python 3.10+ and retry."
  exit 1
fi

if ! command -v pip3 >/dev/null 2>&1; then
  echo "[ERROR] pip3 is not installed. Install python3-pip and retry."
  exit 1
fi

install_with_apt() {
  echo "[INFO] Detected Debian/Ubuntu. Installing system packages..."
  sudo apt update
  sudo apt install -y portaudio19-dev python3-pyaudio xdotool
}

install_with_dnf() {
  echo "[INFO] Detected Fedora/RHEL family. Installing system packages..."
  sudo dnf install -y portaudio-devel python3-pyaudio xdotool
}

if command -v apt >/dev/null 2>&1; then
  install_with_apt
elif command -v dnf >/dev/null 2>&1; then
  install_with_dnf
else
  echo "[WARN] Unsupported package manager. Install manually:"
  echo "       - PortAudio dev package"
  echo "       - python3-pyaudio"
  echo "       - xdotool"
fi

echo "[INFO] Installing Python dependencies from requirements.txt..."
pip3 install -r "${PROJECT_DIR}/requirements.txt"

echo "[OK] Setup completed."
echo "[INFO] Run the assistant with:"
echo "       python3 app/main.py --text"
echo "       python3 app/main.py --continuous --wake-word 'hey linux'"
