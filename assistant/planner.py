"""Task planner that converts intents into executable plan steps."""

from __future__ import annotations

from assistant.contracts import Intent, PlanStep


class Planner:
    """Simple deterministic planner with room for DAG extension."""

    _COMPOSITE_MAP: dict[str, list[tuple[str, str, str, int]]] = {
        "clean_and_update": [
            ("clear_cache", "system", "clear_cache", 0),
            ("remove_temp", "files", "remove_temp", 0),
            ("update_system", "system", "update_system", 1),
        ],
        "prepare_dev_environment": [
            ("open_terminal", "apps", "launch_app", 0),
            ("goto_project", "files", "change_directory", 0),
            ("open_vscode", "apps", "launch_app", 0),
        ]
    }

    def build(self, intents: list[Intent]) -> list[PlanStep]:
        steps: list[PlanStep] = []

        for intent in intents:
            if intent.id in self._COMPOSITE_MAP:
                previous_step_id = ""
                for idx, (step_id, plugin, action, retries) in enumerate(self._COMPOSITE_MAP[intent.id], start=1):
                    current_id = f"{intent.id}_{idx}_{step_id}"
                    steps.append(
                        PlanStep(
                            id=current_id,
                            action=action,
                            plugin=plugin,
                            args=dict(intent.args),
                            dangerous=intent.dangerous,
                            intent_id=intent.id,
                            depends_on=[previous_step_id] if previous_step_id else [],
                            max_retries=retries,
                        )
                    )
                    previous_step_id = current_id
                continue

            steps.append(
                PlanStep(
                    id=f"{intent.id}_1",
                    action=intent.action,
                    plugin=self._plugin_for_intent(intent),
                    args=dict(intent.args),
                    dangerous=intent.dangerous,
                    intent_id=intent.id,
                    depends_on=[],
                    max_retries=0,
                )
            )

        return steps

    @staticmethod
    def _plugin_for_intent(intent: Intent) -> str:
        if intent.action in {"search_web", "open_search_result"}:
            return "browser"

        if intent.action in {"set_reminder", "check_reminders", "suggest_next_action"}:
            return "proactive"

        category_map = {
            "application": "apps",
            "file_operation": "files",
            "navigation": "files",
            "system_monitor": "system",
            "system_control": "system",
            "utility": "system",
            "automation": "automation",
            "browser": "browser",
        }
        return category_map.get(intent.category, "system")
