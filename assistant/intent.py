"""Hybrid intent engine: rule-based first, LLM-like fallback second."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from assistant.contracts import Intent
from engine.interpreter import Command, Interpreter


class LLMIntentProvider(Protocol):
    """Provider contract for optional LLM fallback parsers."""

    def parse(self, text: str) -> list[dict[str, Any]]:
        """Return a list of normalized intent dictionaries."""


@dataclass
class DeterministicFallbackProvider:
    """Lightweight parser used when no external LLM is configured.

    This keeps behavior deterministic and safe while preserving the
    hybrid architecture contract.
    """

    def parse(self, text: str) -> list[dict[str, Any]]:
        value = text.strip().lower()
        if not value:
            return []

        if "clean system and update" in value:
            return [
                {
                    "id": "clean_and_update",
                    "action": "clean_and_update",
                    "category": "system_control",
                    "description": "Clean system and update packages",
                    "args": {},
                    "dangerous": False,
                    "confidence": 0.65,
                    "source": "llm-fallback",
                }
            ]

        if value.startswith("type "):
            text_to_type = text.strip()[5:].strip()
            if text_to_type:
                return [
                    {
                        "id": "automation_type",
                        "action": "automation_type",
                        "category": "automation",
                        "description": "Type text using desktop automation",
                        "args": {"text": text_to_type},
                        "dangerous": False,
                        "confidence": 0.63,
                        "source": "llm-fallback",
                    }
                ]

        hotkey = re.match(r"press\s+(.+)", value)
        if hotkey:
            return [
                {
                    "id": "automation_hotkey",
                    "action": "automation_hotkey",
                    "category": "automation",
                    "description": "Press keyboard shortcut",
                    "args": {"keys": hotkey.group(1).strip()},
                    "dangerous": False,
                    "confidence": 0.62,
                    "source": "llm-fallback",
                }
            ]

        return []


class HybridIntentEngine:
    """Rule-first parser with fallback provider for unknown requests."""

    def __init__(self, interpreter: Optional[Interpreter] = None, fallback_provider: Optional[LLMIntentProvider] = None) -> None:
        self._interpreter = interpreter or Interpreter()
        self._fallback_provider = fallback_provider or DeterministicFallbackProvider()

    def parse(self, text: str) -> list[Intent]:
        rule_commands = self._interpreter.parse(text)
        if rule_commands:
            return [self._command_to_intent(command) for command in rule_commands]

        fallback_intents = self._parse_with_fallback(text)
        if fallback_intents:
            return fallback_intents

        return []

    def suggest(self, text: str, top_n: int = 3) -> list[str]:
        return self._interpreter.suggest(text, top_n=top_n)

    def _parse_with_fallback(self, text: str) -> list[Intent]:
        raw = self._fallback_provider.parse(text)
        intents: list[Intent] = []
        for item in raw:
            normalized = self._validate_intent(item)
            if normalized is not None:
                intents.append(normalized)
        return intents

    def _validate_intent(self, payload: dict[str, Any]) -> Optional[Intent]:
        required = {"id", "action", "category", "description", "args"}
        if not required.issubset(set(payload.keys())):
            return None

        if not isinstance(payload.get("args"), dict):
            return None

        return Intent(
            id=str(payload["id"]),
            action=str(payload["action"]),
            category=str(payload["category"]),
            description=str(payload["description"]),
            args=dict(payload.get("args", {})),
            confidence=float(payload.get("confidence", 0.55)),
            dangerous=bool(payload.get("dangerous", False)),
            source=str(payload.get("source", "llm-fallback")),
        )

    @staticmethod
    def _command_to_intent(command: Command) -> Intent:
        args: dict[str, Any] = {}
        if command.argument:
            args["target"] = command.argument

        return Intent(
            id=command.id,
            action=command.action,
            category=command.category or "utility",
            description=command.description,
            args=args,
            confidence=command.confidence,
            dangerous=command.dangerous,
            source="rules",
        )
