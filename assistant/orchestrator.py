"""Top-level assistant orchestrator with memory, planning, policy, and plugins."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from assistant.contracts import AssistantContext, ExecutionResult, Intent
from assistant.executor import PluginManager
from assistant.intent import HybridIntentEngine
from assistant.memory import SQLiteLongTermMemory, SessionMemoryStore
from assistant.planner import Planner
from assistant.policy import PolicyEngine


class AssistantOrchestrator:
    """Coordinates parse -> plan -> policy -> execute -> feedback flow."""

    def __init__(
        self,
        *,
        policy_file: Path,
        db_path: Path,
        confirm_callback: Optional[callable] = None,
    ) -> None:
        self._intent = HybridIntentEngine()
        self._planner = Planner()
        self._policy = PolicyEngine(policy_file=policy_file)
        self._plugins = PluginManager()
        self._session = SessionMemoryStore()
        self._longterm = SQLiteLongTermMemory(db_path=db_path)
        self._confirm_callback = confirm_callback or self._default_confirm

        self._context = AssistantContext(
            cwd=str(Path.cwd()),
            session_id=uuid.uuid4().hex,
            state=self._session.state,
            metadata={},
        )

    def process(self, utterance: str) -> list[ExecutionResult]:
        intents = self._intent.parse(utterance)
        if not intents:
            suggestions = self._intent.suggest(utterance)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            result = ExecutionResult(ok=False, message=f"I could not understand that.{hint}")
            self._session.record_turn(utterance, [], [result])
            return [result]

        steps = self._planner.build(intents)
        results: list[ExecutionResult] = []

        for step in steps:
            decision = self._policy.evaluate(step)
            if not decision.allow:
                results.append(
                    ExecutionResult(
                        ok=False,
                        message=f"Blocked by policy: {decision.reason}",
                        step_id=step.id,
                        plugin="policy",
                    )
                )
                continue

            if decision.requires_confirmation:
                approved = self._confirm_callback(step.action, decision.risk, step.args)
                if not approved:
                    results.append(
                        ExecutionResult(
                            ok=False,
                            message=f"Cancelled by user for risky action '{step.action}'.",
                            step_id=step.id,
                            plugin="policy",
                            details={"risk": decision.risk},
                        )
                    )
                    continue

            result = self._plugins.execute(step, self._context)
            results.append(result)

            source_intent = self._find_intent_for_step(step.intent_id, intents)
            if source_intent is not None:
                self._longterm.record_action(source_intent, result)

        self._session.record_turn(utterance, intents, results)
        return results

    @staticmethod
    def _find_intent_for_step(intent_id: str, intents: list[Intent]) -> Optional[Intent]:
        for intent in intents:
            if intent.id == intent_id:
                return intent
        return None

    @staticmethod
    def _default_confirm(action: str, risk: str, args: dict) -> bool:
        print(f"\\nSafety confirmation required [{risk}] for action: {action}")
        if args:
            print(f"Arguments: {args}")
        try:
            answer = input("Proceed? (yes/no): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return False
        return answer in {"yes", "y"}
