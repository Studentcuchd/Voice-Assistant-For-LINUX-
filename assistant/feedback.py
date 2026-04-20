"""Feedback renderers for CLI output."""

from __future__ import annotations

from assistant.contracts import ExecutionResult


def render_results(results: list[ExecutionResult]) -> str:
    if not results:
        return "No actions executed."

    lines: list[str] = []
    for item in results:
        prefix = "OK" if item.ok else "ERR"
        step = f"[{item.step_id}] " if item.step_id else ""
        lines.append(f"{prefix} {step}{item.message}")
    return "\n".join(lines)
