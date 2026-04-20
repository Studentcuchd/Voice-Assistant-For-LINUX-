"""Permission and risk controls for executable steps."""

from __future__ import annotations

import json
from pathlib import Path

from assistant.contracts import PlanStep, PolicyDecision


class PolicyEngine:
    """Evaluates allow/deny, risk level, and confirmation requirements."""

    def __init__(self, policy_file: Path) -> None:
        self._policy_file = policy_file
        self._data = self._load_policy()

    def _load_policy(self) -> dict:
        if not self._policy_file.exists():
            return {
                "deny_actions": [],
                "high_risk_actions": ["delete_file", "delete_directory", "shutdown", "reboot"],
                "medium_risk_actions": ["update_system"],
                "confirm_high": True,
                "confirm_medium": False,
            }

        with self._policy_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def evaluate(self, step: PlanStep) -> PolicyDecision:
        if step.action in set(self._data.get("deny_actions", [])):
            return PolicyDecision(
                allow=False,
                risk="high",
                requires_confirmation=False,
                reason=f"Action denied by policy: {step.action}",
                step=step,
            )

        high = set(self._data.get("high_risk_actions", []))
        medium = set(self._data.get("medium_risk_actions", []))

        if step.action in high or step.dangerous:
            return PolicyDecision(
                allow=True,
                risk="high",
                requires_confirmation=bool(self._data.get("confirm_high", True)),
                reason="High-risk action",
                step=step,
            )

        if step.action in medium:
            return PolicyDecision(
                allow=True,
                risk="medium",
                requires_confirmation=bool(self._data.get("confirm_medium", False)),
                reason="Medium-risk action",
                step=step,
            )

        return PolicyDecision(
            allow=True,
            risk="low",
            requires_confirmation=False,
            reason="Low-risk action",
            step=step,
        )
