"""Desktop automation plugin (Linux-first)."""

from __future__ import annotations

import subprocess

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep

try:
    import pyautogui  # type: ignore[import-not-found]
except ImportError:
    pyautogui = None


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
        if action == "automation_click":
            return self._click(args)
        if action == "automation_move":
            return self._move(args)

        return ExecutionResult(ok=False, message=f"Unsupported automation action: {action}", plugin=self.name)

    def _type_text(self, args: dict) -> ExecutionResult:
        text = str(args.get("text", "")).strip()
        if not text:
            return ExecutionResult(ok=False, message="No text provided for typing.", plugin=self.name)

        try:
            rc = subprocess.call(["xdotool", "type", "--delay", "1", text])
            if rc == 0:
                return ExecutionResult(ok=True, message=f"Typed text: {text}", plugin=self.name)
        except FileNotFoundError:
            pass

        if pyautogui is not None:
            pyautogui.write(text, interval=0.01)
            return ExecutionResult(ok=True, message=f"Typed text using pyautogui: {text}", plugin=self.name)

        return ExecutionResult(ok=False, message="Typing failed. Install xdotool or pyautogui.", plugin=self.name)

    def _press_keys(self, args: dict) -> ExecutionResult:
        keys = str(args.get("keys", "")).strip()
        if not keys:
            return ExecutionResult(ok=False, message="No keys provided for hotkey action.", plugin=self.name)

        try:
            rc = subprocess.call(["xdotool", "key", keys])
            if rc == 0:
                return ExecutionResult(ok=True, message=f"Pressed keys: {keys}", plugin=self.name)
        except FileNotFoundError:
            pass

        if pyautogui is not None:
            try:
                pyautogui.hotkey(*[part.strip() for part in keys.split("+") if part.strip()])
                return ExecutionResult(ok=True, message=f"Pressed keys using pyautogui: {keys}", plugin=self.name)
            except Exception:
                return ExecutionResult(ok=False, message=f"Could not press keys: {keys}", plugin=self.name)

        return ExecutionResult(ok=False, message="Key press failed. Install xdotool or pyautogui.", plugin=self.name)

    def _click(self, args: dict) -> ExecutionResult:
        x = self._safe_int(args.get("x"))
        y = self._safe_int(args.get("y"))
        if x is None or y is None:
            return ExecutionResult(ok=False, message="Click requires numeric x and y.", plugin=self.name)

        try:
            rc = subprocess.call(["xdotool", "mousemove", str(x), str(y), "click", "1"])
            if rc == 0:
                return ExecutionResult(ok=True, message=f"Clicked at ({x}, {y}).", plugin=self.name)
        except FileNotFoundError:
            pass

        if pyautogui is not None:
            pyautogui.click(x=x, y=y)
            return ExecutionResult(ok=True, message=f"Clicked at ({x}, {y}) using pyautogui.", plugin=self.name)

        return ExecutionResult(ok=False, message="Click failed. Install xdotool or pyautogui.", plugin=self.name)

    def _move(self, args: dict) -> ExecutionResult:
        x = self._safe_int(args.get("x"))
        y = self._safe_int(args.get("y"))
        if x is None or y is None:
            return ExecutionResult(ok=False, message="Move requires numeric x and y.", plugin=self.name)

        try:
            rc = subprocess.call(["xdotool", "mousemove", str(x), str(y)])
            if rc == 0:
                return ExecutionResult(ok=True, message=f"Moved pointer to ({x}, {y}).", plugin=self.name)
        except FileNotFoundError:
            pass

        if pyautogui is not None:
            pyautogui.moveTo(x=x, y=y)
            return ExecutionResult(ok=True, message=f"Moved pointer to ({x}, {y}) using pyautogui.", plugin=self.name)

        return ExecutionResult(ok=False, message="Move failed. Install xdotool or pyautogui.", plugin=self.name)

    @staticmethod
    def _safe_int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


def register() -> AutomationPlugin:
    return AutomationPlugin()
