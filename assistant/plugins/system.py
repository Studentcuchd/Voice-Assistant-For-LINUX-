"""System information and control plugin."""

from __future__ import annotations

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep
from assistant.plugins._legacy import LegacyExecutorAdapter


_SYSTEM_ACTIONS = {
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
}


class SystemPlugin:
    name = "system"

    def __init__(self) -> None:
        self._legacy = LegacyExecutorAdapter()

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action in _SYSTEM_ACTIONS

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        action = str(args.get("action", "")).strip() or _infer_action(intent)

        if action in {"clear_cache", "remove_temp"}:
            return ExecutionResult(
                ok=True,
                message=f"Planned step '{action}' acknowledged (implementation pending).",
                plugin=self.name,
            )

        message = self._legacy.run(
            intent_id=intent,
            action=action,
            description="System action",
            dangerous=action in {"shutdown", "reboot"},
            args=args,
        )
        return ExecutionResult(ok=not message.startswith("❌"), message=message, plugin=self.name)


def _infer_action(intent: str) -> str:
    map_by_intent = {
        "cpu_usage": "show_cpu",
        "memory_usage": "show_memory",
        "disk_usage": "show_disk",
        "system_info": "show_system_info",
        "running_processes": "show_processes",
        "shutdown": "shutdown",
        "reboot": "reboot",
        "update_system": "update_system",
        "clear_screen": "clear_screen",
        "show_date": "show_date",
        "show_ip": "show_ip",
        "show_uptime": "show_uptime",
    }
    return map_by_intent.get(intent, intent)


def register() -> SystemPlugin:
    return SystemPlugin()
