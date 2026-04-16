"""
main.py
-------
Voice-Controlled Linux Assistant — Entry Point

Runs an interactive loop that:
  1.  Captures a command (voice or text fallback)
  2.  Interprets it into structured Command objects
  3.  Executes each command and prints the result
  4.  Repeats until the user says "exit" / "quit" / Ctrl-C

Usage
-----
    python main.py              # voice mode (falls back to text automatically)
    python main.py --text       # force text mode
    python main.py --help       # show CLI help
"""

from __future__ import annotations

import argparse
import sys
import time

# ── Make sure the project root is on sys.path when run directly ───────────────
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.executor import Executor
from engine.interpreter import Command, Interpreter
from utils.logger import get_logger
from voice.speech import SpeechCapture, get_input

log = get_logger(__name__)

# ── UI helpers ────────────────────────────────────────────────────────────────

BANNER = r"""
 ██╗   ██╗ ██████╗ ██╗ ██████╗███████╗      █████╗ ██╗
 ██║   ██║██╔═══██╗██║██╔════╝██╔════╝     ██╔══██╗██║
 ██║   ██║██║   ██║██║██║     █████╗       ███████║██║
 ╚██╗ ██╔╝██║   ██║██║██║     ██╔══╝       ██╔══██║██║
  ╚████╔╝ ╚██████╔╝██║╚██████╗███████╗     ██║  ██║██║
   ╚═══╝   ╚═════╝ ╚═╝ ╚═════╝╚══════╝     ╚═╝  ╚═╝╚═╝

  Voice-Controlled Linux Assistant  |  speak or type commands
  Type 'help' for examples  |  'exit' or Ctrl-C to quit
"""

EXIT_TRIGGERS  = {"exit", "quit", "bye", "stop", "goodbye", "close"}
HELP_TRIGGERS  = {"help", "commands", "what can you do", "list commands"}

HELP_TEXT = """
╔════════════════════════════════════════════════════════════╗
║  EXAMPLE COMMANDS                                          ║
╠════════════════════════════════════════════════════════════╣
║  Applications                                              ║
║    open browser / launch firefox / start chrome           ║
║    open terminal / open vscode / open file manager        ║
║                                                            ║
║  File Operations                                           ║
║    create folder my_project                                ║
║    create file notes.txt                                   ║
║    delete file old_notes.txt                               ║
║    list files                                              ║
║                                                            ║
║  Navigation                                                ║
║    where am I / current directory                          ║
║    go to Documents / change directory projects             ║
║    go home                                                  ║
║                                                            ║
║  System Info                                               ║
║    cpu usage / memory usage / disk space                   ║
║    show processes / system info / uptime / date / ip       ║
║                                                            ║
║  Multi-command (AND / THEN)                                ║
║    open browser and create folder downloads2               ║
║    show disk then list files                               ║
║                                                            ║
║  System Control (⚠️ requires confirmation)                 ║
║    shutdown / reboot                                       ║
╚════════════════════════════════════════════════════════════╝
"""

def _print_separator() -> None:
    print("\n" + "─" * 62 + "\n")

def _print_result(result: str) -> None:
    print(f"\n  {result}\n")

def _print_command_plan(commands: list[Command]) -> None:
    """Show the user what the assistant understood before executing."""
    if len(commands) == 1:
        print(f"  🔍  Understood: {commands[0].description}")
        if commands[0].argument:
            print(f"       Argument : '{commands[0].argument}'")
    else:
        print(f"  🔍  Understood {len(commands)} commands:")
        for i, c in enumerate(commands, 1):
            arg_str = f" → '{c.argument}'" if c.argument else ""
            print(f"       {i}. {c.description}{arg_str}")
    print()


# ── Core assistant loop ───────────────────────────────────────────────────────

class VoiceAssistant:
    """Orchestrates the listen → interpret → execute pipeline."""

    def __init__(self, force_text: bool = False) -> None:
        self.force_text   = force_text
        self.capture      = SpeechCapture()
        self.interpreter  = Interpreter()
        self.executor     = Executor()
        self._session_cmds = 0    # stats

    def run(self) -> None:
        """Main interactive loop."""
        print(BANNER)

        if not self.force_text and self.capture.mic_available:
            self.capture.calibrate(duration=1.0)
            mode = "🎙  Voice mode active  (speak your command)"
        else:
            mode = "⌨️   Text mode active  (type your command)"

        print(f"  {mode}\n")
        _print_separator()

        try:
            while True:
                self._tick()
        except KeyboardInterrupt:
            print("\n\n  👋  Goodbye! (session commands: %d)" % self._session_cmds)
            log.info("Session ended by user. Commands executed: %d", self._session_cmds)

    def _tick(self) -> None:
        """Single iteration: get input → interpret → execute → report."""
        raw = get_input(self.capture, force_text=self.force_text)

        if raw is None:
            # Empty input or EOF — just loop
            return

        # ── Built-in meta-commands ─────────────────────────────────────────
        if raw in EXIT_TRIGGERS:
            raise KeyboardInterrupt

        if raw in HELP_TRIGGERS:
            print(HELP_TEXT)
            return

        # ── Interpret ─────────────────────────────────────────────────────
        commands = self.interpreter.parse(raw)

        if not commands:
            print(f"\n  ❓  Sorry, I didn't understand: \"{raw}\"")
            suggestions = self.interpreter.suggest(raw)
            if suggestions:
                print("  💡  Did you mean one of:")
                for s in suggestions:
                    print(f"       • {s}")
            print()
            return

        # ── Preview & execute ─────────────────────────────────────────────
        _print_command_plan(commands)

        for cmd in commands:
            result = self.executor.run(cmd)
            _print_result(result)
            self._session_cmds += 1
            if len(commands) > 1:
                time.sleep(0.3)   # brief pause between chained commands

        _print_separator()


# ── CLI argument parsing ──────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="voice_assistant",
        description="Voice-Controlled Linux Assistant — speak or type Linux commands.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py               # voice mode
  python main.py --text        # text-only mode
        """,
    )
    parser.add_argument(
        "--text", "-t",
        action="store_true",
        help="Force text input mode (skip microphone)",
    )
    return parser.parse_args()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    assistant = VoiceAssistant(force_text=args.text)
    assistant.run()
