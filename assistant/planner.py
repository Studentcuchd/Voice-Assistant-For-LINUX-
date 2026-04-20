"""Task planner that converts intents into executable plan steps."""

from __future__ import annotations

from assistant.contracts import Intent, PlanStep


class Planner:
    """Simple deterministic planner with room for DAG extension."""

    _COMPOSITE_MAP: dict[str, list[tuple[str, str, str]]] = {
        "clean_and_update": [
            ("clear_cache", "system", "clear_cache"),
            ("remove_temp", "files", "remove_temp"),
            ("update_system", "system", "update_system"),
        ]
    }

    def build(self, intents: list[Intent]) -> list[PlanStep]:
        steps: list[PlanStep] = []

        for intent in intents:
            if intent.id in self._COMPOSITE_MAP:
                for idx, (step_id, plugin, action) in enumerate(self._COMPOSITE_MAP[intent.id], start=1):
                    steps.append(
                        PlanStep(
                            id=f"{intent.id}_{idx}_{step_id}",
                            action=action,
                            plugin=plugin,
                            args=dict(intent.args),
                            dangerous=intent.dangerous,
                            intent_id=intent.id,
                        )
                    )
                continue

            steps.append(
                PlanStep(
                    id=f"{intent.id}_1",
                    action=intent.action,
                    plugin=self._plugin_for_intent(intent),
                    args=dict(intent.args),
                    dangerous=intent.dangerous,
                    intent_id=intent.id,
                )
            )

        return steps

    @staticmethod
    def _plugin_for_intent(intent: Intent) -> str:
        if intent.action == "search_web":
            return "browser"

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
