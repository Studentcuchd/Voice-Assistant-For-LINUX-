"""File and navigation plugin."""

from __future__ import annotations

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep
from assistant.plugins._legacy import LegacyExecutorAdapter


_FILE_ACTIONS = {
    "create_directory",
    "delete_file",
    "delete_directory",
    "list_files",
    "change_directory",
    "go_home",
    "create_file",
    "print_working_dir",
}


class FilesPlugin:
    name = "files"

    def __init__(self) -> None:
        self._legacy = LegacyExecutorAdapter()

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action in _FILE_ACTIONS

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        action = str(args.get("action", "")).strip() or _infer_action(intent)
        message = self._legacy.run(
            intent_id=intent,
            action=action,
            description="File operation",
            dangerous=action in {"delete_file", "delete_directory"},
            args=args,
        )
        return ExecutionResult(ok=not message.startswith("❌"), message=message, plugin=self.name)


def _infer_action(intent: str) -> str:
    map_by_intent = {
        "create_folder": "create_directory",
        "delete_file": "delete_file",
        "delete_folder": "delete_directory",
        "list_files": "list_files",
        "change_directory": "change_directory",
        "go_home": "go_home",
        "create_file": "create_file",
        "current_directory": "print_working_dir",
    }
    return map_by_intent.get(intent, intent)


def register() -> FilesPlugin:
    return FilesPlugin()
