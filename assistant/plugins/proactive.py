"""Proactive intelligence plugin: reminders and usage-based suggestions."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from assistant.contracts import AssistantContext, ExecutionResult, PlanStep


@dataclass
class ProactivePlugin:
    name: str = "proactive"

    def __post_init__(self) -> None:
        db_path = os.getenv("ASSISTANT_DB_PATH", "")
        if not db_path:
            db_path = str(Path("data") / "assistant.db")
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def can_handle(self, step: PlanStep) -> bool:
        return step.plugin == self.name or step.action in {"set_reminder", "check_reminders", "suggest_next_action"}

    def execute(self, intent: str, args: dict, context: AssistantContext) -> ExecutionResult:
        if intent == "set_reminder":
            return self._set_reminder(args)
        if intent == "check_reminders":
            return self._check_reminders()
        if intent == "suggest_next_action":
            return self._suggest_next_action()

        return ExecutionResult(ok=False, message=f"Unsupported proactive action: {intent}", plugin=self.name)

    def _set_reminder(self, args: dict) -> ExecutionResult:
        try:
            minutes = int(args.get("minutes", 0))
        except (TypeError, ValueError):
            minutes = 0

        message = str(args.get("message", "")).strip()
        if minutes <= 0 or not message:
            return ExecutionResult(ok=False, message="Reminder requires positive minutes and a message.", plugin=self.name)

        due_at = datetime.utcnow() + timedelta(minutes=minutes)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reminders(message, due_at, delivered, created_at)
                VALUES (?, ?, 0, ?)
                """,
                (message, due_at.isoformat(), datetime.utcnow().isoformat()),
            )

        return ExecutionResult(
            ok=True,
            message=f"Reminder set for {minutes} minute(s): {message}",
            plugin=self.name,
            details={"due_at": due_at.isoformat()},
        )

    def _check_reminders(self) -> ExecutionResult:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, message FROM reminders
                WHERE delivered = 0 AND due_at <= ?
                ORDER BY due_at ASC
                LIMIT 3
                """,
                (now,),
            ).fetchall()

            if rows:
                conn.executemany("UPDATE reminders SET delivered = 1 WHERE id = ?", [(row[0],) for row in rows])

        if not rows:
            return ExecutionResult(ok=True, message="", plugin=self.name)

        messages = "; ".join(row[1] for row in rows)
        return ExecutionResult(ok=True, message=f"Reminder: {messages}", plugin=self.name)

    def _suggest_next_action(self) -> ExecutionResult:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT action, usage_count
                FROM command_usage
                ORDER BY usage_count DESC, last_used_at DESC
                LIMIT 1
                """
            ).fetchone()

        if not row:
            return ExecutionResult(ok=True, message="No preference learned yet.", plugin=self.name)

        action, count = row
        return ExecutionResult(
            ok=True,
            message=f"Suggestion: you often use '{action}' ({count} times). Want to run it now?",
            plugin=self.name,
        )


def register() -> ProactivePlugin:
    return ProactivePlugin()
