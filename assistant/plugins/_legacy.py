"""Compatibility helpers for reusing the MVP executor safely."""

from __future__ import annotations

from engine.executor import Executor
from engine.interpreter import Command


class LegacyExecutorAdapter:
    """Adapts new plan steps to the existing executor command model."""

    def __init__(self) -> None:
        self._executor = Executor()

    def run(self, *, intent_id: str, action: str, description: str, dangerous: bool, args: dict) -> str:
        app_candidates = args.get("app_candidates", [])
        if not isinstance(app_candidates, list):
            app_candidates = []

        command = Command(
            id=intent_id,
            action=action,
            description=description,
            dangerous=dangerous,
            argument=str(args.get("target", "")).strip() or None,
            app_candidates=[str(item).strip() for item in app_candidates if str(item).strip()],
            category=str(args.get("category", "")),
        )
        return self._executor.run(command)
