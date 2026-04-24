"""Hybrid intent engine: rule-based first, LLM-like fallback second."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from assistant.contracts import Intent
from engine.interpreter import Command, Interpreter


class LLMIntentProvider(Protocol):
    """Provider contract for optional LLM fallback parsers."""

    def parse(self, text: str, context: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        """Return a list of normalized intent dictionaries."""


@dataclass
class DeterministicFallbackProvider:
    """Lightweight parser used when no external LLM is configured.

    This keeps behavior deterministic and safe while preserving the
    hybrid architecture contract.
    """

    def parse(self, text: str, context: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        value = text.strip().lower()
        context = context or {}
        entities = context.get("entities", {}) if isinstance(context, dict) else {}
        if not value:
            return []

        if "prepare my dev environment" in value or "prepare dev environment" in value:
            return [
                {
                    "id": "prepare_dev_environment",
                    "action": "prepare_dev_environment",
                    "category": "system_control",
                    "description": "Prepare development environment",
                    "args": {},
                    "dangerous": False,
                    "confidence": 0.66,
                    "source": "deterministic-fallback",
                }
            ]

        reminder = re.match(
            r"^remind\s+me\s+in\s+(\d+)\s*(minute|minutes|min|mins|hour|hours)\s+(?:to\s+)?(.+)$",
            value,
        )
        if reminder:
            amount = int(reminder.group(1))
            unit = reminder.group(2)
            message = reminder.group(3).strip()
            minutes = amount * 60 if unit.startswith("hour") else amount
            return [
                {
                    "id": "set_reminder",
                    "action": "set_reminder",
                    "category": "utility",
                    "description": "Set a reminder",
                    "args": {"minutes": minutes, "message": message},
                    "dangerous": False,
                    "confidence": 0.86,
                    "source": "deterministic-fallback",
                }
            ]

        if value in {"what should i do now", "suggest next action", "any suggestion"}:
            return [
                {
                    "id": "suggest_next_action",
                    "action": "suggest_next_action",
                    "category": "utility",
                    "description": "Suggest likely next action",
                    "args": {},
                    "dangerous": False,
                    "confidence": 0.7,
                    "source": "context-fallback",
                }
            ]

        if value in {"not that one", "open next result", "open the next result"}:
            last_query = str(entities.get("last_query", "")).strip()
            last_idx = int(entities.get("last_result_index", 1) or 1)
            if last_query:
                return [
                    {
                        "id": "open_search_result",
                        "action": "open_search_result",
                        "category": "browser",
                        "description": "Open next search result page",
                        "args": {"query": last_query, "index": last_idx + 1},
                        "dangerous": False,
                        "confidence": 0.82,
                        "source": "context-fallback",
                    }
                ]

        click = re.match(r"^click\s+(?:at\s+)?(\d+)\s+(\d+)$", value)
        if click:
            return [
                {
                    "id": "automation_click",
                    "action": "automation_click",
                    "category": "automation",
                    "description": "Click at screen coordinates",
                    "args": {"x": int(click.group(1)), "y": int(click.group(2))},
                    "dangerous": False,
                    "confidence": 0.76,
                    "source": "deterministic-fallback",
                }
            ]

        move = re.match(r"^move\s+(?:mouse\s+)?to\s+(\d+)\s+(\d+)$", value)
        if move:
            return [
                {
                    "id": "automation_move",
                    "action": "automation_move",
                    "category": "automation",
                    "description": "Move mouse to screen coordinates",
                    "args": {"x": int(move.group(1)), "y": int(move.group(2))},
                    "dangerous": False,
                    "confidence": 0.76,
                    "source": "deterministic-fallback",
                }
            ]

        # Follow-up resolution for conversational references.
        if value in {"open first result", "open the first result"}:
            last_query = str(entities.get("last_query", "")).strip()
            if last_query:
                return [
                    {
                        "id": "open_search_result",
                        "action": "open_search_result",
                        "category": "browser",
                        "description": "Open first search result",
                        "args": {"query": last_query, "index": 1},
                        "dangerous": False,
                        "confidence": 0.8,
                        "source": "context-fallback",
                    }
                ]

        if value in {"open second result", "open the second result"}:
            last_query = str(entities.get("last_query", "")).strip()
            if last_query:
                return [
                    {
                        "id": "open_search_result",
                        "action": "open_search_result",
                        "category": "browser",
                        "description": "Open second search result page",
                        "args": {"query": last_query, "index": 2},
                        "dangerous": False,
                        "confidence": 0.78,
                        "source": "context-fallback",
                    }
                ]

        query_only = re.match(r"^search\s+(.+)$", value)
        if query_only:
            return [
                {
                    "id": "search_web",
                    "action": "search_web",
                    "category": "application",
                    "description": "Search the web in the browser",
                    "args": {"query": query_only.group(1).strip()},
                    "dangerous": False,
                    "confidence": 0.7,
                    "source": "deterministic-fallback",
                }
            ]

        open_app = re.match(
            r"^(?:open|launch|start|run)\s+(?:the\s+)?(?:app(?:lication)?\s+)?(.+)$",
            value,
        )
        if open_app:
            app_name = open_app.group(1).strip().strip('"\'')
            if app_name and app_name not in {"browser", "terminal", "vscode", "file manager"}:
                return [
                    {
                        "id": "open_application",
                        "action": "launch_app",
                        "category": "application",
                        "description": "Open application by name",
                        "args": {"target": app_name, "app_candidates": [app_name]},
                        "dangerous": False,
                        "confidence": 0.7,
                        "source": "deterministic-fallback",
                    }
                ]

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


@dataclass
class OllamaIntentProvider:
    """Local LLM fallback using Ollama with strict JSON parsing only."""

    model: str = "llama3.2:3b"
    endpoint: str = "http://127.0.0.1:11434/api/generate"

    _ALLOWED_ACTIONS: set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._ALLOWED_ACTIONS is None:
            self._ALLOWED_ACTIONS = {
                "launch_app",
                "search_web",
                "create_directory",
                "delete_file",
                "delete_directory",
                "list_files",
                "print_working_dir",
                "change_directory",
                "go_home",
                "show_cpu",
                "show_memory",
                "show_disk",
                "show_system_info",
                "show_processes",
                "shutdown",
                "reboot",
                "update_system",
                "clear_screen",
                "show_date",
                "show_ip",
                "show_uptime",
                "create_file",
                "automation_type",
                "automation_hotkey",
                "automation_click",
                "automation_move",
                "open_search_result",
                "clean_and_update",
                "prepare_dev_environment",
                "set_reminder",
                "check_reminders",
                "suggest_next_action",
            }

    def parse(self, text: str, context: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        prompt = self._build_prompt(text=text, context=context or {})
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "top_p": 0.1},
        }

        req = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=7) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError, OSError):
            return []

        raw_text = str(body.get("response", "")).strip()
        if not raw_text:
            return []

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            return []

        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            return []

        normalized: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "")).strip()
            if action not in self._ALLOWED_ACTIONS:
                continue
            normalized.append(item)
        return normalized

    @staticmethod
    def _build_prompt(text: str, context: dict[str, Any]) -> str:
        return (
            "You are an intent parser for a Linux assistant. "
            "Output only strict JSON. Never output shell commands. "
            "Return a JSON array of intents with keys: "
            "id, action, category, description, args, dangerous, confidence, source. "
            f"Conversation context: {json.dumps(context, ensure_ascii=True)}. "
            f"User input: {text}"
        )


class HybridIntentEngine:
    """Rule-first parser with fallback provider for unknown requests."""

    def __init__(self, interpreter: Optional[Interpreter] = None, fallback_provider: Optional[LLMIntentProvider] = None) -> None:
        self._interpreter = interpreter or Interpreter()
        self._fallback_provider = fallback_provider or self._build_default_fallback()

    @staticmethod
    def _build_default_fallback() -> LLMIntentProvider:
        if os.getenv("ASSISTANT_USE_OLLAMA", "0").strip().lower() in {"1", "true", "yes"}:
            model = os.getenv("ASSISTANT_OLLAMA_MODEL", "llama3.2:3b")
            endpoint = os.getenv("ASSISTANT_OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/generate")
            return OllamaIntentProvider(model=model, endpoint=endpoint)
        return DeterministicFallbackProvider()

    def parse(self, text: str, context: Optional[dict[str, Any]] = None) -> list[Intent]:
        rule_commands = self._interpreter.parse(text)
        if rule_commands:
            return [self._command_to_intent(command) for command in rule_commands]

        fallback_intents = self._parse_with_fallback(text, context=context)
        if fallback_intents:
            return fallback_intents

        return []

    def suggest(self, text: str, top_n: int = 3) -> list[str]:
        return self._interpreter.suggest(text, top_n=top_n)

    def _parse_with_fallback(self, text: str, context: Optional[dict[str, Any]] = None) -> list[Intent]:
        raw = self._fallback_provider.parse(text, context=context)
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

        allowed_categories = {
            "application",
            "file_operation",
            "navigation",
            "system_monitor",
            "system_control",
            "utility",
            "automation",
            "browser",
        }

        allowed_actions = {
            "launch_app",
            "search_web",
            "create_directory",
            "delete_file",
            "delete_directory",
            "list_files",
            "print_working_dir",
            "change_directory",
            "go_home",
            "show_cpu",
            "show_memory",
            "show_disk",
            "show_system_info",
            "show_processes",
            "shutdown",
            "reboot",
            "update_system",
            "clear_screen",
            "show_date",
            "show_ip",
            "show_uptime",
            "create_file",
            "automation_type",
            "automation_hotkey",
            "automation_click",
            "automation_move",
            "open_search_result",
            "clean_and_update",
            "prepare_dev_environment",
            "set_reminder",
            "check_reminders",
            "suggest_next_action",
        }

        category = str(payload["category"]).strip()
        if category not in allowed_categories:
            return None

        action = str(payload["action"]).strip()
        if action not in allowed_actions:
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
        if command.action == "launch_app" and command.app_candidates:
            args["app_candidates"] = list(command.app_candidates)

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
