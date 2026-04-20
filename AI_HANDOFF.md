# AI Handoff Document

## 1) Project Snapshot

Project name: Voice-Controlled Linux Assistant
Current branch: main
Latest feature commit: 0999f55 (Complete Step 3 Siri-like integration features)
Status: Siri-like integration pass completed in modular runtime with proactive and conversational upgrades.

Primary goal achieved so far:
- Upgraded from MVP command assistant to layered system with orchestrator, memory, planner, policy, and plugin runtime.
- Added wake-word-aware voice flow with tolerant matching.
- Added one-step Linux setup script.
- Added Ollama parser integration option with strict JSON intent safety.
- Added proactive reminders/suggestions and background reminder polling.
- Added optional TTS output and richer desktop automation fallback.

## 2) What Is Implemented

### MVP (still available)
- Entry point: main.py
- Flow: voice/text input -> interpreter -> executor
- Rule-based intent mapping via JSON command catalog
- Multi-command splitting
- Dangerous command confirmation

### Modular production layer (new)
- Entry point: app/main.py
- Layers implemented:
  - Input controller with wake word and interruption handling
  - Hybrid intent engine (rules first, deterministic fallback second)
  - Planner for single-step and composite multi-step tasks
  - Policy/risk engine with confirmation gates
  - Dynamic plugin discovery and execution
  - Session + long-term memory
  - Structured feedback rendering

## 3) Architecture and Key Files

### Entrypoints
- main.py
  - Old MVP runtime (kept for backward compatibility)
- app/main.py
  - New modular runtime
  - Supports: --text, --continuous, --wake-word, --wake-threshold, --ollama, --ollama-model, --ollama-endpoint, --tts

### Core modular package
- assistant/orchestrator.py
  - Main pipeline: parse -> plan -> policy -> execute -> memory
- assistant/contracts.py
  - Shared dataclasses (Intent, PlanStep, ExecutionResult, context/state)
- assistant/intent.py
  - Hybrid intent engine
  - Uses engine/interpreter.py first, fallback parser second
- assistant/planner.py
  - Maps intents to plugin steps
  - Includes composite example: clean_and_update
- assistant/policy.py
  - Risk and permission decisions (allow/deny/confirm)
- assistant/executor.py
  - Dynamic plugin loading from assistant/plugins
- assistant/memory.py
  - Session memory + SQLite long-term memory
- assistant/input.py
  - Wake-word tolerant parsing and interrupt marker
- assistant/feedback.py
  - CLI output renderer

### Plugin system
- assistant/plugins/apps.py
- assistant/plugins/browser.py
- assistant/plugins/files.py
- assistant/plugins/system.py
- assistant/plugins/automation.py
- assistant/plugins/proactive.py
- assistant/plugins/_legacy.py
  - Compatibility adapter reusing existing engine/executor logic

### Legacy engine retained
- engine/interpreter.py
- engine/executor.py
- engine/data/commands.json
- voice/speech.py
- utils/logger.py

### Config
- config/permissions.json
  - Current policy defaults:
    - High risk: delete_file, delete_directory, shutdown, reboot
    - Medium risk: update_system, change_directory

### Setup and dependency files
- requirements.txt
- setup_linux.sh

### Optional runtime helpers
- assistant/tts.py

## 4) Features Included

### Input and conversation
- Voice input via SpeechRecognition + PyAudio
- Text mode fallback
- Wake-word mode in modular runtime
- Tolerant wake matching for variants like hey linux / hey linus
- Continuous mode option and interruption phrase handling
- Follow-up references: open first/second result, open next result, not that one

### Intent and planning
- Rule-based command interpretation from commands.json
- Hybrid fallback parser for unsupported phrases (deterministic + optional Ollama)
- Multi-step planning support via planner
- Dependency-aware sequencing and step retry support

### Execution
- Dynamic plugin loading
- Category-driven plugin routing
- Reuse of stable legacy executor behavior through adapter

### Safety
- Policy allow/deny support
- Low/medium/high risk classification
- Confirmation before high-risk actions

### Memory
- Short-term session memory in process
- Long-term memory in SQLite database at data/assistant.db
- Action history persistence

### Automation
- Linux desktop automation plugin via xdotool
- pyautogui fallback support when xdotool is unavailable
- Actions wired: type text, press keys, click coordinates, move pointer

### Proactive intelligence
- Reminder creation from natural language
- Background due-reminder polling between turns
- Suggest-next-action using long-term command usage patterns

### Voice response
- Optional TTS via spd-say/espeak in modular runtime

## 5) Installation (Everything Needed)

### Recommended one-shot install (Linux)
1. Run:
   bash setup_linux.sh

What this script does:
- Installs Linux packages (apt or dnf path)
- Installs Python packages from requirements.txt

### Manual install if needed
Debian/Ubuntu:
- sudo apt update
- sudo apt install -y portaudio19-dev python3-pyaudio xdotool
- pip install -r requirements.txt

Fedora:
- sudo dnf install -y portaudio-devel python3-pyaudio xdotool
- pip install -r requirements.txt

Python dependencies currently required:
- SpeechRecognition>=3.10.0,<4.0.0
- PyAudio>=0.2.13,<1.0.0
- PyAutoGUI>=0.9.54,<1.0.0

Notes:
- SQLite is built into Python, no separate pip package required.

## 6) How To Run

### MVP mode (legacy)
- python main.py
- python main.py --text

### Modular production mode
- python app/main.py
- python app/main.py --text
- python app/main.py --continuous --wake-word "hey linux"
- python app/main.py --continuous --wake-word "hey linux" --wake-threshold 0.72
- python app/main.py --text --ollama --ollama-model "llama3.2:3b"
- python app/main.py --continuous --tts --ollama --ollama-model "llama3.2:3b"

## 7) Current Completion Level

Implemented and usable now:
- Modular architecture scaffold and runtime flow
- Plugin loading and routing
- Policy gating
- Memory persistence
- Wake-word tolerant input
- Setup script and dependency docs
- Conversational follow-up handling for search results and corrections
- Proactive reminder and suggestion workflows
- Optional local Ollama fallback parsing with action/category allowlists
- Optional TTS output and expanded desktop automation

Partially implemented / placeholder behavior:
- Ollama fallback is integrated but still parser-only and prompt/template can be improved.
- Planner supports dependencies/retries but not full rollback DAG yet.
- Some composite step actions are acknowledged placeholders (for example clear_cache/remove_temp)

Not yet fully productionized:
- Automated test suite (unit/integration) across modules
- Additional schema hardening for arbitrary LLM malformed outputs
- More robust observability (metrics/tracing dashboard)
- Rich semantic UI automation workflows (vision/element targeting)

## 8) Important Behavioral Notes

- main.py remains fully available and separate from app/main.py.
- app/main.py is the primary target for future enhancements.
- Unknown commands in modular mode return suggestions from rule engine when possible.
- High-risk commands require confirmation based on config/permissions.json.

## 9) Suggested Next Engineering Steps

1. Add real LLM provider in assistant/intent.py behind LLMIntentProvider interface.
2. Add strict JSON schema validator for fallback outputs before intent acceptance.
3. Expand planner into dependency-aware task graph with rollback strategies.
4. Add unit tests for orchestrator, planner, policy, and plugin manager.
5. Add integration tests for end-to-end command execution in text mode.
6. Add plugin health checks and graceful dependency warnings (for missing xdotool, etc.).
7. Add user preference learning loop using memory tables.

## 10) Quick Prompt To Give Another AI

Use this project as-is and continue from modular runtime in app/main.py.
Do not remove legacy compatibility.
Prioritize: real LLM fallback provider, tests, planner expansion, and production observability.
Respect Linux-first behavior and policy confirmations for risky actions.
