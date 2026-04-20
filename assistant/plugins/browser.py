"""Browser plugin."""

from __future__ import annotations

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep
from assistant.plugins._legacy import LegacyExecutorAdapter


class BrowserPlugin:
    name = "browser"

    def __init__(self) -> None:
        self._legacy = LegacyExecutorAdapter()

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action in {"search_web"}

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        action = "search_web" if intent == "search_web" or args.get("query") else "launch_app"
        normalized = dict(args)
        if "query" in normalized and "target" not in normalized:
            normalized["target"] = normalized["query"]

        message = self._legacy.run(
            intent_id=intent,
            action=action,
            description="Browser action",
            dangerous=False,
            args=normalized,
        )
        return ExecutionResult(ok=not message.startswith("❌"), message=message, plugin=self.name)


def register() -> BrowserPlugin:
    return BrowserPlugin()
