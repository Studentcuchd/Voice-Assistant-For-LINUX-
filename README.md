# Voice-Controlled Linux Assistant

This project converts natural-language voice or text into executable Linux commands. It includes multi-command splitting, fuzzy matching, safety confirmation for destructive actions, and a JSON-driven command catalog.

## Latest Updates

- Added production modular architecture with orchestrator, planner, policy engine, memory, and dynamic plugins.
- Introduced hybrid intent handling: rule-based parser first, deterministic fallback parser second.
- Added persistent long-term memory with SQLite (`data/assistant.db`) and session memory for short-term context.
- Added wake-word-aware input pipeline with tolerant matching for speech variation (`hey linux`, `hey linus`, etc.).
- Added Linux desktop automation plugin support using `xdotool`.
- Preserved backward compatibility: original MVP entrypoint remains `main.py`.

## Project Structure

```text
voiceassistant/
├── main.py
├── requirements.txt
├── README.md
├── engine/
│   ├── __init__.py
│   ├── interpreter.py
│   ├── executor.py
│   └── data/
│       └── commands.json
├── voice/
│   ├── __init__.py
│   └── speech.py
└── utils/
    ├── __init__.py
    └── logger.py
```

## Setup

The project is designed for Linux.

One-step setup (recommended):

```bash
bash setup_linux.sh
```

This script installs required Linux packages and Python dependencies.

```bash
sudo apt install portaudio19-dev python3-pyaudio
pip install -r requirements.txt
```

## Usage

```bash
python main.py
python main.py --text
python app/main.py
python app/main.py --text
python app/main.py --continuous --wake-word "hey linux"
python app/main.py --continuous --wake-word "hey linux" --wake-threshold 0.72
```

Voice mode calibrates the microphone when available. Text mode bypasses the microphone entirely.

`main.py` is the backward-compatible MVP runner.
`app/main.py` is the new production modular runner.

The modular runner includes tolerant wake-word detection for speech variations
like `hey linux`, `hey linus`, and similar ASR outputs.

Try phrases like:

```text
search web for python lists
look up best vscode extensions
search on browser weather in london
```

## Command Model

Command definitions live in [engine/data/commands.json](engine/data/commands.json). Each entry declares keywords, an action name, whether it is dangerous, and optional app candidates or required arguments.

The runtime flow is:

```text
input -> voice/speech.py -> engine/interpreter.py -> engine/executor.py -> terminal output
```

## Production Modular Architecture

The new architecture adds production-grade layers without breaking the original flow:

- `assistant/orchestrator.py`: parse -> plan -> policy -> plugin execution pipeline
- `assistant/intent.py`: hybrid intent system (rules first, deterministic fallback second)
- `assistant/memory.py`: session memory + persistent SQLite long-term memory
- `assistant/planner.py`: multi-step planning for composite tasks
- `assistant/policy.py`: risk classification and permission checks
- `assistant/executor.py`: dynamic plugin loader and router
- `assistant/plugins/*.py`: apps/files/system/browser/automation feature plugins
- `config/permissions.json`: allow/deny and confirmation policy

Persistent memory database is stored at `data/assistant.db`.

Optional Linux desktop automation plugin uses `xdotool`.

## Extending the Assistant

Add a new JSON entry for a command. If the action name is new, add a matching handler in [engine/executor.py](engine/executor.py).

## Notes

The implementation lives under `engine/`, `voice/`, and `utils/`.
