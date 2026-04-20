# Project Summary (So Far)

This is a voice-controlled Linux assistant built in Python that converts natural language (voice or text) into executable system commands.

## Current Status

- Core pipeline is implemented end-to-end: input -> interpret -> execute.
- Supports both voice mode (SpeechRecognition + PyAudio) and text fallback mode.
- Uses a JSON command catalog (`engine/data/commands.json`) for easy extension.
- Handles multi-command input (e.g., "and", "then") in a single user request.
- Includes safety confirmation for dangerous actions (delete, shutdown, reboot).
- Provides friendly CLI UX with command preview, help menu, and formatted outputs.

## Main Components

- `main.py`: CLI entry point and assistant loop.
- `voice/speech.py`: microphone capture, speech-to-text, and text fallback handling.
- `engine/interpreter.py`: intent parsing, fuzzy matching, alias normalization, argument extraction.
- `engine/executor.py`: action dispatch and OS command/app execution.
- `engine/data/commands.json`: command definitions (keywords, action, safety, arguments).
- `utils/logger.py`: colored console logging + rotating file logs.

## Features Implemented

- Open apps (browser, terminal, VS Code, file manager, text editor)
- Web search from spoken/text queries
- File and folder create/delete/list
- Directory navigation (pwd, cd, home)
- System info (CPU, memory, disk, processes, uptime, date, IP)
- System control actions (shutdown/reboot/update)

## Dependencies

- Python packages: `SpeechRecognition`, `pyaudio`
- System requirement for voice input: PortAudio (Linux package)

## Short Conclusion

The project is in a strong working MVP stage: modular architecture, extensible command model, multi-input support, and safety checks are already in place.