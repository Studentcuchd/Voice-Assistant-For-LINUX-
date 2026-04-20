"""Input adapters for text, voice, wake-word, and continuous mode."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from voice.speech import SpeechCapture, get_input


@dataclass
class InputController:
    """Coordinates wake-word gating and continuous input collection."""

    force_text: bool = False
    wake_word: str = "hey linux"
    continuous: bool = False
    wake_threshold: float = 0.78

    def __post_init__(self) -> None:
        self.capture = SpeechCapture()
        normalized_wake = self._normalize_phrase(self.wake_word)
        self._wake_aliases = {
            normalized_wake,
            "hey linus",
            "hey linux assistant",
            "hi linux",
            "ok linux",
        }

    def read_once(self) -> Optional[str]:
        text = get_input(self.capture, force_text=self.force_text)
        if text is None:
            return None

        value = text.strip().lower()
        if not value:
            return None

        if self.force_text:
            return value

        if self.wake_word:
            stripped = self._strip_wake_word(value)
            if stripped is not None:
                return stripped

        if self.continuous and value in {"stop listening", "pause listening"}:
            return "__INTERRUPT__"

        if self.wake_word:
            return None

        return value

    @staticmethod
    def _normalize_phrase(value: str) -> str:
        return " ".join(value.strip().lower().split())

    def _strip_wake_word(self, value: str) -> Optional[str]:
        normalized = self._normalize_phrase(value)
        if not normalized:
            return None

        # Fast path for exact prefix alias match.
        for alias in sorted(self._wake_aliases, key=len, reverse=True):
            if normalized.startswith(alias):
                rest = normalized[len(alias) :].strip(" ,.!?")
                return rest or ""

        # Fuzzy path for ASR misspelling/noise in first 2-3 tokens.
        tokens = normalized.split()
        max_window = min(3, len(tokens))
        for window in range(1, max_window + 1):
            prefix = " ".join(tokens[:window])
            for alias in self._wake_aliases:
                score = SequenceMatcher(None, prefix, alias).ratio()
                if score >= self.wake_threshold:
                    rest = " ".join(tokens[window:]).strip(" ,.!?")
                    return rest or ""

        return None
