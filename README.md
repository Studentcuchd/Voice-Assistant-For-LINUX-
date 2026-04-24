# Voice-Controlled Linux Assistant

Complete voice and text assistant for Linux with:

- Rule-based + fallback intent parsing
- Command execution with safety checks
- Browser search integration
- Modular plugin runtime
- Session + long-term memory (SQLite)
- Optional wake-word flow, automation, and TTS

This repository is now intentionally clean:

- One installation file: `requirements.txt`
- One documentation file: `README.md`

## Project Layout

```text
voiceassistant/
├── README.md
├── requirements.txt
├── main.py                     # MVP runner
├── app/
│   └── main.py                 # production modular runner
├── assistant/
│   ├── contracts.py
│   ├── executor.py
│   ├── feedback.py
│   ├── input.py
│   ├── intent.py
│   ├── memory.py
│   ├── orchestrator.py
│   ├── planner.py
│   ├── policy.py
│   ├── tts.py
│   └── plugins/
├── engine/
│   ├── interpreter.py
│   ├── executor.py
│   └── data/commands.json
├── voice/
│   └── speech.py
├── utils/
│   └── logger.py
├── config/
│   └── permissions.json
└── data/
    └── assistant.db            # runtime-generated
```

## Installation

All installation instructions are intentionally centralized in one file only:

- `requirements.txt`

That file contains:

- Python package dependencies
- Linux system package prerequisites for Debian/Ubuntu, Fedora, and Arch
- Notes for optional features (audio, automation, TTS)

If microphone input is unavailable, the app automatically falls back to text mode.

## Step-by-Step Linux Run Guide

Follow these steps on your Linux machine from project root:

1. Clone and enter the project folder.

2. Make the Linux runner executable.

    chmod +x run_linux.sh

3. Start in text mode (recommended first run).

    ./run_linux.sh

4. Start in voice mode with wake word.

    ./run_linux.sh --voice --continuous --wake-word "hey linux"

5. Run MVP mode if you want the legacy pipeline.

    ./run_linux.sh --mvp --text

6. See all runtime options.

    ./run_linux.sh --help

Notes:

- The script installs Linux system dependencies (apt, dnf, or pacman), creates .venv, installs requirements.txt, then runs the assistant.
- Use --skip-system-deps if you already installed OS packages.
- Use --no-venv if you intentionally want system Python.

## Ollama Installation and Usage

If you want LLM fallback parsing, install and run Ollama.

### Install Ollama on Linux

Option A (official install script):

curl -fsSL https://ollama.com/install.sh | sh

Option B (manual package flow):

- Follow the latest Linux instructions on Ollama docs if your distro needs a custom method.

### Start Ollama service

ollama serve

Keep this running in a separate terminal.

### Pull a model

ollama pull llama3.2:3b

You can replace the model name with any model installed in your environment.

### Run assistant with Ollama enabled

./run_linux.sh --text --ollama --ollama-model "llama3.2:3b"

With custom endpoint:

./run_linux.sh --text --ollama --ollama-model "llama3.2:3b" --ollama-endpoint "http://127.0.0.1:11434/api/generate"

Quick check:

Ask an uncommon command. If rule-based parsing does not match, fallback parsing will use Ollama.

## Quick Start

### MVP runner

```bash
python main.py
python main.py --text
```

### Production modular runner

```bash
python app/main.py --text
python app/main.py --continuous --wake-word "hey linux"
python app/main.py --continuous --wake-word "hey linux" --wake-threshold 0.72
python app/main.py --continuous --tts
python app/main.py --text --ollama --ollama-model "llama3.2:3b"
```

## What It Can Do

### Core commands

- Open apps (browser, terminal, file manager, editor)
- File operations (create/list/delete)
- Navigation (current path, change directory, go home)
- System information (cpu/memory/disk/processes/date/ip/uptime)
- Controlled dangerous actions (shutdown/reboot with confirmation)

### Browser behavior

- `open browser` opens default browser
- `search web for python lists` performs a search
- `open https://github.com` opens URL directly
- `open studentcuchd.github.io` resolves and opens as URL
- Unknown phrases can fall back to browser search

### Conversational features (modular runtime)

- Context follow-ups: `open first result`, `open second result`, `not that one`
- Reminder flow: `remind me in 10 minutes to check logs`
- Next-step suggestions: `what should i do now`

## Architecture Summary

### MVP pipeline

```text
input -> voice/speech.py -> engine/interpreter.py -> engine/executor.py -> output
```

### Modular pipeline

```text
input -> assistant/intent.py -> assistant/planner.py -> assistant/policy.py
      -> assistant/executor.py (plugins) -> assistant/feedback.py
```

Key modules:

- `assistant/orchestrator.py`: end-to-end controller
- `assistant/intent.py`: hybrid intent engine
- `assistant/memory.py`: session + SQLite long-term memory
- `assistant/executor.py`: plugin manager
- `assistant/plugins/*`: apps/files/browser/system/automation/proactive plugins

## Configuration

- Command catalog: `engine/data/commands.json`
- Policy config: `config/permissions.json`
- Persistent memory DB: `data/assistant.db`

## Troubleshooting

### PyAudio install errors

Follow the Linux package prerequisites listed in `requirements.txt`, then reinstall from the same file.

### No microphone detected

Use text mode:

```bash
python main.py --text
```

### Automation actions not working

- Verify `xdotool` is present as listed in `requirements.txt`
- Ensure desktop session allows simulated input
- PyAutoGUI is used as fallback when available

## Extending the Assistant

1. Add/modify intents in `engine/data/commands.json`
2. Add execution logic in `engine/executor.py` or a plugin under `assistant/plugins/`
3. Update this README when behavior changes
