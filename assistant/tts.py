"""Optional TTS helpers for conversational voice feedback."""

from __future__ import annotations

import os
import shutil
import subprocess


def speak(text: str) -> None:
    value = text.strip()
    if not value:
        return

    # Try platform-specific TTS options
    if os.name == "nt":  # Windows
        _speak_windows(value)
    else:  # Unix/Linux
        _speak_unix(value)


def _speak_windows(text: str) -> None:
    """Use Windows PowerShell Add-Type for speech synthesis."""
    try:
        ps_cmd = (
            f'Add-Type -AssemblyName System.Speech; '
            f'$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            f'$speak.Speak("{text.replace(chr(34), chr(34)*2)}")'
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS,
        )
    except Exception:
        pass  # Fail silently if PowerShell unavailable


def _speak_unix(text: str) -> None:
    """Use Linux TTS tools (spd-say or espeak)."""
    # Prefer spd-say for Linux desktops, fall back to espeak.
    if shutil.which("spd-say"):
        subprocess.Popen(["spd-say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    if shutil.which("espeak"):
        subprocess.Popen(["espeak", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
