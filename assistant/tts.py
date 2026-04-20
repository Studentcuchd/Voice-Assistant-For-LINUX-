"""Optional TTS helpers for conversational voice feedback."""

from __future__ import annotations

import shutil
import subprocess


def speak(text: str) -> None:
    value = text.strip()
    if not value:
        return

    # Prefer spd-say for Linux desktops, fall back to espeak.
    if shutil.which("spd-say"):
        subprocess.Popen(["spd-say", value], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if shutil.which("espeak"):
        subprocess.Popen(["espeak", value], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
