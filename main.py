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
import re
import sys
import time
from datetime import datetime

# ── Make sure the project root is on sys.path when run directly ───────────────
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.executor import Executor
from engine.interpreter import Command, Interpreter
from utils.logger import get_logger
from voice.speech import SpeechCapture, get_input

try:
    from assistant.tts import speak as _speak
except Exception:  # noqa: BLE001
    _speak = None

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
║    search web for python lists                             ║
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


def _normalize_text(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _strip_for_tts(value: str) -> str:
    # Keep TTS output short and avoid speaking symbols/emojis verbatim.
    cleaned = re.sub(r"[^\w\s.,:;!?\-]", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:220]


def _small_talk_reply(raw: str) -> str | None:
    text = _normalize_text(raw)
    if text in {"hi", "hello", "hey", "hello assistant", "hey assistant"}:
        return "Hi. I am listening."
    if text in {"how are you", "how are you doing"}:
        return "I am doing great and ready to help."
    if text in {"who are you", "what are you", "what is your name"}:
        return "I am your Linux voice assistant."
    if text in {"thanks", "thank you", "thank you assistant"}:
        return "You're welcome."
    if text in {"what time is it", "time now", "tell me the time"}:
        return f"It is {datetime.now():%H:%M}."
    return None

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

    def __init__(self, force_text: bool = False, *, enable_tts: bool = False, wake_word: str = "") -> None:
        self.force_text   = force_text
        self.capture      = SpeechCapture()
        self.interpreter  = Interpreter()
        self.executor     = Executor()
        self._session_cmds = 0    # stats
        self.enable_tts = enable_tts
        self.wake_word = _normalize_text(wake_word)

    def _say(self, text: str) -> None:
        if not self.enable_tts or _speak is None:
            return
        msg = _strip_for_tts(text)
        if msg:
            _speak(msg)

    def _handle_wake_word(self, text: str) -> str | None:
        if self.force_text or not self.wake_word:
            return text

        normalized = _normalize_text(text)
        if normalized == self.wake_word:
            print("\n  🎧  I'm listening...\n")
            self._say("I'm listening.")
            return None

        if normalized.startswith(self.wake_word + " "):
            rest = normalized[len(self.wake_word):].strip(" ,.!?\t")
            return rest or None
        return None

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

        wake_handled = self._handle_wake_word(raw)
        if wake_handled is None:
            return
        raw = wake_handled

        reply = _small_talk_reply(raw)
        if reply:
            print(f"\n  🤖  {reply}\n")
            self._say(reply)
            return

        # ── Built-in meta-commands ─────────────────────────────────────────
        if raw in EXIT_TRIGGERS:
            raise KeyboardInterrupt

        if raw in HELP_TRIGGERS:
            print(HELP_TEXT)
            self._say("Here are some things I can do. Check the command list on screen.")
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
                self._say(f"I didn't catch that. Maybe try: {suggestions[0]}.")
            else:
                self._say("I did not understand that command.")
            print()
            return

        # ── Preview & execute ─────────────────────────────────────────────
        _print_command_plan(commands)

        for cmd in commands:
            result = self.executor.run(cmd)
            _print_result(result)
            self._say(result)
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
    parser.add_argument(
        "--tts",
        action="store_true",
        help="Enable spoken feedback (Siri-like responses)",
    )
    parser.add_argument(
        "--wake-word",
        default="",
        help="Optional wake word for voice mode, e.g. 'hey siri'",
    )
    return parser.parse_args()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    assistant = VoiceAssistant(force_text=args.text, enable_tts=args.tts, wake_word=args.wake_word)
    assistant.run()
