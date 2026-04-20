"""Session and long-term memory stores."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from assistant.contracts import ExecutionResult, Intent, SessionState


class SessionMemoryStore:
    """Short-term volatile memory for active session context."""

    def __init__(self) -> None:
        self.state = SessionState()

    def record_turn(self, utterance: str, intents: list[Intent], results: list[ExecutionResult]) -> None:
        self.state.last_user_utterance = utterance
        self.state.last_intents = intents
        self.state.last_results = results

    def set_slot(self, key: str, value: Any) -> None:
        self.state.slots[key] = value

    def get_slot(self, key: str, default: Any = None) -> Any:
        return self.state.slots.get(key, default)


class SQLiteLongTermMemory:
    """Persistent memory using SQLite for portability and reliability."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def set_preference(self, key: str, value: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, value, now),
            )

    def get_preference(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def record_action(self, intent: Intent, result: ExecutionResult) -> None:
        import json

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO action_history(intent_id, action, args_json, success, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    intent.id,
                    intent.action,
                    json.dumps(intent.args, ensure_ascii=True),
                    1 if result.ok else 0,
                    result.message,
                    datetime.utcnow().isoformat(),
                ),
            )

    def last_actions(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT intent_id, action, args_json, success, message, created_at
                FROM action_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "intent_id": row[0],
                "action": row[1],
                "args_json": row[2],
                "success": bool(row[3]),
                "message": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]
