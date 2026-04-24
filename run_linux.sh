#!/usr/bin/env bash
set -euo pipefail

# One-command Linux runner for the voice assistant.
# Usage examples:
#   ./run_linux.sh
#   ./run_linux.sh --voice --continuous --wake-word "hey linux"
#   ./run_linux.sh --mvp --text
#   ./run_linux.sh --skip-system-deps

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

USE_MVP=0
FORCE_TEXT=1
CONTINUOUS=0
ENABLE_TTS=0
ENABLE_OLLAMA=0
SKIP_SYSTEM_DEPS=0
NO_VENV=0
WAKE_WORD="hey linux"
OLLAMA_MODEL="llama3.2:3b"
OLLAMA_ENDPOINT="http://127.0.0.1:11434/api/generate"

log() {
  printf "\n[voiceassistant] %s\n" "$*"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_system_deps() {
  if [[ "$SKIP_SYSTEM_DEPS" -eq 1 ]]; then
    log "Skipping system package installation (--skip-system-deps)."
    return 0
  fi

  if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=""
  elif have_cmd sudo; then
    SUDO="sudo"
  else
    log "sudo not found and not root; skipping system package install."
    return 0
  fi

  if have_cmd apt-get; then
    log "Installing system packages using apt..."
    $SUDO apt-get update
    $SUDO apt-get install -y python3 python3-venv python3-pip portaudio19-dev python3-pyaudio xdotool espeak-ng speech-dispatcher
    return 0
  fi

  if have_cmd dnf; then
    log "Installing system packages using dnf..."
    $SUDO dnf install -y python3 python3-pip python3-virtualenv portaudio-devel python3-pyaudio xdotool espeak-ng speech-dispatcher
    return 0
  fi

  if have_cmd pacman; then
    log "Installing system packages using pacman..."
    $SUDO pacman -Sy --noconfirm python python-pip python-virtualenv portaudio python-pyaudio xdotool espeak-ng speech-dispatcher
    return 0
  fi

  log "No supported package manager found (apt/dnf/pacman). Continuing without system package install."
}

setup_python() {
  if [[ "$NO_VENV" -eq 1 ]]; then
    if have_cmd python3; then
      PYTHON_BIN="python3"
    elif have_cmd python; then
      PYTHON_BIN="python"
    else
      echo "Python is not installed. Install Python 3.10+ and retry."
      exit 1
    fi
    return 0
  fi

  if ! have_cmd python3; then
    echo "python3 was not found. Install Python 3.10+ and retry."
    exit 1
  fi

  if [[ ! -d ".venv" ]]; then
    log "Creating virtual environment (.venv)..."
    python3 -m venv .venv
  fi

  # shellcheck disable=SC1091
  source .venv/bin/activate
  PYTHON_BIN="python"

  log "Installing Python dependencies..."
  "$PYTHON_BIN" -m pip install --upgrade pip wheel
  "$PYTHON_BIN" -m pip install -r requirements.txt
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mvp)
        USE_MVP=1
        shift
        ;;
      --text)
        FORCE_TEXT=1
        shift
        ;;
      --voice)
        FORCE_TEXT=0
        shift
        ;;
      --continuous)
        CONTINUOUS=1
        shift
        ;;
      --tts)
        ENABLE_TTS=1
        shift
        ;;
      --ollama)
        ENABLE_OLLAMA=1
        shift
        ;;
      --ollama-model)
        OLLAMA_MODEL="${2:-$OLLAMA_MODEL}"
        shift 2
        ;;
      --ollama-endpoint)
        OLLAMA_ENDPOINT="${2:-$OLLAMA_ENDPOINT}"
        shift 2
        ;;
      --wake-word)
        WAKE_WORD="${2:-$WAKE_WORD}"
        shift 2
        ;;
      --skip-system-deps)
        SKIP_SYSTEM_DEPS=1
        shift
        ;;
      --no-venv)
        NO_VENV=1
        shift
        ;;
      -h|--help)
        cat <<'EOF'
Usage: ./run_linux.sh [options]

Options:
  --mvp                 Run root main.py instead of app/main.py
  --text                Force text mode (default)
  --voice               Enable microphone mode
  --continuous          Continuous listening mode (modular runner)
  --wake-word WORD      Wake word for modular runner (default: hey linux)
  --tts                 Enable text-to-speech responses
  --ollama              Enable Ollama fallback parser
  --ollama-model NAME   Ollama model (default: llama3.2:3b)
  --ollama-endpoint URL Ollama endpoint (default: http://127.0.0.1:11434/api/generate)
  --skip-system-deps    Do not install apt/dnf/pacman packages
  --no-venv             Use system Python directly
  -h, --help            Show this help
EOF
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        echo "Use --help to see available options."
        exit 1
        ;;
    esac
  done
}

main() {
  parse_args "$@"
  install_system_deps
  setup_python

  if [[ "$USE_MVP" -eq 1 ]]; then
    CMD=("$PYTHON_BIN" "main.py")
    [[ "$FORCE_TEXT" -eq 1 ]] && CMD+=("--text")
    [[ "$ENABLE_TTS" -eq 1 ]] && CMD+=("--tts")
    if [[ "$FORCE_TEXT" -eq 0 ]]; then
      CMD+=("--wake-word" "$WAKE_WORD")
    fi
  else
    CMD=("$PYTHON_BIN" "app/main.py")
    [[ "$FORCE_TEXT" -eq 1 ]] && CMD+=("--text")
    [[ "$CONTINUOUS" -eq 1 ]] && CMD+=("--continuous")
    [[ "$FORCE_TEXT" -eq 0 ]] && CMD+=("--wake-word" "$WAKE_WORD")
    [[ "$ENABLE_TTS" -eq 1 ]] && CMD+=("--tts")
    if [[ "$ENABLE_OLLAMA" -eq 1 ]]; then
      CMD+=("--ollama" "--ollama-model" "$OLLAMA_MODEL" "--ollama-endpoint" "$OLLAMA_ENDPOINT")
    fi
  fi

  log "Starting assistant..."
  printf "[voiceassistant] Command:"
  for part in "${CMD[@]}"; do
    printf " %q" "$part"
  done
  printf "\n\n"

  exec "${CMD[@]}"
}

main "$@"
