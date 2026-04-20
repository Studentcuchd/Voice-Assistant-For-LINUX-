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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    project_root = Path(__file__).resolve().parents[1]
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
        print(render_results(results))

        if not args.continuous and not args.text:
            print("Awaiting wake-word...")


if __name__ == "__main__":
    main()
