"""Plugin execution runtime and dynamic plugin loader."""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass
from typing import Protocol

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep


class Plugin(Protocol):
    """Runtime plugin contract."""

    name: str

    def can_handle(self, step: PlanStep) -> bool:
        """Return True when this plugin supports the step."""

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        """Run a plan step and return structured result."""


@dataclass
class PluginManager:
    """Dynamic plugin discovery and step routing."""

    package: str = "assistant.plugins"

    def __post_init__(self) -> None:
        self._plugins: list[Plugin] = []
        self.load_all()

    def load_all(self) -> None:
        self._plugins.clear()
        package_module = importlib.import_module(self.package)

        for module_info in pkgutil.iter_modules(package_module.__path__):
            if module_info.name.startswith("_"):
                continue
            module = importlib.import_module(f"{self.package}.{module_info.name}")
            register = getattr(module, "register", None)
            if callable(register):
                plugin = register()
                self._plugins.append(plugin)

    def execute(self, step: PlanStep, context: AssistantContext) -> ExecutionResult:
        for plugin in self._plugins:
            if plugin.can_handle(step):
                result = plugin.execute(step.action, dict(step.args), context)
                result.step_id = step.id
                if not result.plugin:
                    result.plugin = plugin.name
                return result

        return ExecutionResult(
            ok=False,
            message=f"No plugin found for step action '{step.action}'",
            step_id=step.id,
            plugin="plugin-manager",
        )
