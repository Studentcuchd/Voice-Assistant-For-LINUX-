"""Top-level assistant orchestrator with memory, planning, policy, and plugins."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable, Optional

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
        confirm_callback: Optional[Callable[[str, str, dict], bool]] = None,
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
            metadata={"db_path": str(db_path)},
        )

    def process(self, utterance: str) -> list[ExecutionResult]:
        intent_context = self._session.context_payload()
        intents = self._intent.parse(utterance, context=intent_context)
        if not intents:
            suggestions = self._intent.suggest(utterance)
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            result = ExecutionResult(ok=False, message=f"I could not understand that.{hint}")
            self._session.record_turn(utterance, [], [result])
            return [result]

        steps = self._planner.build(intents)
        results: list[ExecutionResult] = []
        execution_status: dict[str, bool] = {}

        for step in steps:
            if step.depends_on and not all(execution_status.get(dep, False) for dep in step.depends_on):
                skipped = ExecutionResult(
                    ok=False,
                    message=f"Skipped '{step.action}' because dependencies failed.",
                    step_id=step.id,
                    plugin="planner",
                )
                results.append(skipped)
                execution_status[step.id] = False
                continue

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
                execution_status[step.id] = False
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
                    execution_status[step.id] = False
                    continue

            result = self._execute_with_retry(step)
            results.append(result)
            execution_status[step.id] = result.ok

            source_intent = self._find_intent_for_step(step.intent_id, intents)
            if source_intent is not None:
                self._longterm.record_action(source_intent, result)

        self._session.record_turn(utterance, intents, results)
        return results

    def poll_background(self) -> list[ExecutionResult]:
        """Run lightweight proactive checks between turns."""
        from assistant.contracts import PlanStep

        check_step = PlanStep(
            id="background_check_reminders",
            action="check_reminders",
            plugin="proactive",
            args={},
            dangerous=False,
            intent_id="background",
        )
        result = self._plugins.execute(check_step, self._context)
        if result.ok and result.message:
            return [result]
        return []

    def _execute_with_retry(self, step) -> ExecutionResult:
        attempts = max(1, step.max_retries + 1)
        last_result = ExecutionResult(
            ok=False,
            message=f"Execution failed for '{step.action}'.",
            step_id=step.id,
            plugin="executor",
        )

        for attempt in range(1, attempts + 1):
            result = self._plugins.execute(step, self._context)
            if result.ok:
                if attempt > 1:
                    result.message = f"{result.message} (recovered on retry {attempt}/{attempts})"
                return result
            last_result = result

        return last_result

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
