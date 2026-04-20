"""Production entrypoint for the modular Linux voice assistant."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow `python app/main.py` execution from project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from assistant.feedback import render_results
from assistant.input import InputController
from assistant.orchestrator import AssistantOrchestrator
from assistant.tts import speak

EXIT_WORDS = {"exit", "quit", "bye", "stop"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production modular voice assistant")
    parser.add_argument("--text", action="store_true", help="Use text mode only")
    parser.add_argument("--continuous", action="store_true", help="Keep listening continuously")
    parser.add_argument("--wake-word", default="hey linux", help="Wake-word prefix for voice mode")
    parser.add_argument(
        "--wake-threshold",
        type=float,
        default=0.78,
        help="Wake-word fuzzy threshold between 0 and 1 (lower = more sensitive)",
    )
    parser.add_argument("--ollama", action="store_true", help="Enable Ollama LLM fallback for unknown intents")
    parser.add_argument("--ollama-model", default="llama3.2:3b", help="Ollama model to use for intent parsing")
    parser.add_argument(
        "--ollama-endpoint",
        default="http://127.0.0.1:11434/api/generate",
        help="Ollama generate API endpoint",
    )
    parser.add_argument("--tts", action="store_true", help="Enable text-to-speech responses")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.ollama:
        os.environ["ASSISTANT_USE_OLLAMA"] = "1"
        os.environ["ASSISTANT_OLLAMA_MODEL"] = args.ollama_model
        os.environ["ASSISTANT_OLLAMA_ENDPOINT"] = args.ollama_endpoint

    project_root = Path(__file__).resolve().parents[1]
    os.environ["ASSISTANT_DB_PATH"] = str(project_root / "data" / "assistant.db")
    orchestrator = AssistantOrchestrator(
        policy_file=project_root / "config" / "permissions.json",
        db_path=project_root / "data" / "assistant.db",
    )

    input_controller = InputController(
        force_text=args.text,
        wake_word=args.wake_word,
        continuous=args.continuous,
        wake_threshold=max(0.5, min(0.95, args.wake_threshold)),
    )

    print("Modular Linux Assistant ready. Type 'exit' to quit.")
    if not args.text:
        print(f"Wake-word mode: say '{args.wake_word}' before commands.")

    while True:
        utterance = input_controller.read_once()

        if utterance is None:
            continue

        if utterance == "__INTERRUPT__":
            print("Listening interrupted. Say wake-word again.")
            continue

        if utterance in EXIT_WORDS:
            print("Goodbye.")
            break

        results = orchestrator.process(utterance)
        output = render_results(results)
        print(output)

        background = orchestrator.poll_background()
        if background:
            bg_output = render_results(background)
            print(bg_output)
            if args.tts:
                speak(bg_output)

        if args.tts:
            speak(output)

        if not args.continuous and not args.text:
            print("Awaiting wake-word...")


if __name__ == "__main__":
    main()
