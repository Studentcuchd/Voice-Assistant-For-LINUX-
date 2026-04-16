# Voice-Controlled Linux Assistant

This project converts natural-language voice or text into executable Linux commands. It includes multi-command splitting, fuzzy matching, safety confirmation for destructive actions, and a JSON-driven command catalog.

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

```bash
sudo apt install portaudio19-dev python3-pyaudio
pip install -r requirements.txt
```

## Usage

```bash
python main.py
python main.py --text
```

Voice mode calibrates the microphone when available. Text mode bypasses the microphone entirely.

## Command Model

Command definitions live in [engine/data/commands.json](engine/data/commands.json). Each entry declares keywords, an action name, whether it is dangerous, and optional app candidates or required arguments.

The runtime flow is:

```text
input -> voice/speech.py -> engine/interpreter.py -> engine/executor.py -> terminal output
```

## Extending the Assistant

Add a new JSON entry for a command. If the action name is new, add a matching handler in [engine/executor.py](engine/executor.py).

## Notes

The implementation lives under `engine/`, `voice/`, and `utils/`.
