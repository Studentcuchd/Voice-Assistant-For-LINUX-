"""Application plugin."""

from __future__ import annotations

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep
from assistant.plugins._legacy import LegacyExecutorAdapter


class AppsPlugin:
    name = "apps"

    def __init__(self) -> None:
        self._legacy = LegacyExecutorAdapter()

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action == "launch_app"

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        message = self._legacy.run(
            intent_id=intent,
            action="launch_app",
            description="Open application",
            dangerous=False,
            args=args,
        )
        return ExecutionResult(ok=not message.startswith("❌"), message=message, plugin=self.name)


def register() -> AppsPlugin:
    return AppsPlugin()
