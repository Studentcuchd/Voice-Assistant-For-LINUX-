"""Desktop automation plugin (Linux-first)."""

from __future__ import annotations

import subprocess

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep


class AutomationPlugin:
    name = "automation"

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action.startswith("automation_")

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        action = intent

        if action == "automation_type":
            return self._type_text(args)
        if action == "automation_hotkey":
            return self._press_keys(args)

        return ExecutionResult(ok=False, message=f"Unsupported automation action: {action}", plugin=self.name)

    def _type_text(self, args: dict) -> ExecutionResult:
        text = str(args.get("text", "")).strip()
        if not text:
            return ExecutionResult(ok=False, message="No text provided for typing.", plugin=self.name)

        rc = subprocess.call(["xdotool", "type", "--delay", "1", text])
        if rc != 0:
            return ExecutionResult(ok=False, message="xdotool typing failed. Is xdotool installed?", plugin=self.name)
        return ExecutionResult(ok=True, message=f"Typed text: {text}", plugin=self.name)

    def _press_keys(self, args: dict) -> ExecutionResult:
        keys = str(args.get("keys", "")).strip()
        if not keys:
            return ExecutionResult(ok=False, message="No keys provided for hotkey action.", plugin=self.name)

        rc = subprocess.call(["xdotool", "key", keys])
        if rc != 0:
            return ExecutionResult(ok=False, message="xdotool key press failed. Is xdotool installed?", plugin=self.name)
        return ExecutionResult(ok=True, message=f"Pressed keys: {keys}", plugin=self.name)


def register() -> AutomationPlugin:
    return AutomationPlugin()
