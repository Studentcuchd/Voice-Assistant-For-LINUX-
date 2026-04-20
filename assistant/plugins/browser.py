"""Browser plugin."""

from __future__ import annotations

import webbrowser
from urllib.parse import quote_plus

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep
from assistant.plugins._legacy import LegacyExecutorAdapter


class BrowserPlugin:
    name = "browser"

    def __init__(self) -> None:
        self._legacy = LegacyExecutorAdapter()

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action in {"search_web", "open_search_result"}

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        if intent == "open_search_result":
            query = str(args.get("query", args.get("target", ""))).strip()
            if query:
                context.state.entities["last_query"] = query
            try:
                context.state.entities["last_result_index"] = int(args.get("index", 1))
            except (TypeError, ValueError):
                context.state.entities["last_result_index"] = 1
            return self._open_search_result(args)

        action = "search_web" if intent == "search_web" or args.get("query") else "launch_app"
        normalized = dict(args)
        if "query" in normalized and "target" not in normalized:
            normalized["target"] = normalized["query"]
        if "target" in normalized and str(normalized["target"]).strip():
            context.state.entities["last_query"] = str(normalized["target"]).strip()

        message = self._legacy.run(
            intent_id=intent,
            action=action,
            description="Browser action",
            dangerous=False,
            args=normalized,
        )
        return ExecutionResult(ok=not message.startswith("❌"), message=message, plugin=self.name)

    def _open_search_result(self, args: dict) -> ExecutionResult:
        query = str(args.get("query", args.get("target", ""))).strip()
        if not query:
            return ExecutionResult(ok=False, message="No prior search query available.", plugin=self.name)

        try:
            index = int(args.get("index", 1))
        except (TypeError, ValueError):
            index = 1

        if index <= 1:
            url = f"https://www.google.com/search?btnI=1&q={quote_plus(query)}"
            opened = webbrowser.open_new_tab(url)
            if opened:
                return ExecutionResult(ok=True, message=f"Opened the first result for '{query}'.", plugin=self.name)
            return ExecutionResult(ok=False, message="Could not open browser tab for first result.", plugin=self.name)

        offset = max(0, (index - 1) * 10)
        url = f"https://www.google.com/search?q={quote_plus(query)}&start={offset}"
        opened = webbrowser.open_new_tab(url)
        if opened:
            return ExecutionResult(
                ok=True,
                message=f"Opened search page near result {index} for '{query}'.",
                plugin=self.name,
            )
        return ExecutionResult(ok=False, message="Could not open browser tab for follow-up result.", plugin=self.name)


def register() -> BrowserPlugin:
    return BrowserPlugin()
