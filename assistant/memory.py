"""Session and long-term memory stores."""

from __future__ import annotations

import json
import sqlite3
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
        self.state.conversation_history.append({"role": "user", "text": utterance})

        result_text = " | ".join(result.message for result in results if result.message)
        if result_text:
            self.state.conversation_history.append({"role": "assistant", "text": result_text})

        # Keep history bounded for lightweight context retrieval.
        if len(self.state.conversation_history) > 30:
            self.state.conversation_history = self.state.conversation_history[-30:]

        self._update_entities(intents)

    def set_slot(self, key: str, value: Any) -> None:
        self.state.slots[key] = value

    def get_slot(self, key: str, default: Any = None) -> Any:
        return self.state.slots.get(key, default)

    def context_payload(self) -> dict[str, Any]:
        return {
            "slots": dict(self.state.slots),
            "entities": dict(self.state.entities),
            "history": list(self.state.conversation_history[-8:]),
        }

    def _update_entities(self, intents: list[Intent]) -> None:
        for intent in intents:
            target = str(intent.args.get("target", "")).strip()
            query = str(intent.args.get("query", "")).strip()

            if intent.category == "application":
                self.state.entities["last_app"] = intent.id

            if intent.action == "search_web" or query:
                self.state.entities["last_query"] = query or target

            if intent.action == "open_search_result":
                try:
                    self.state.entities["last_result_index"] = int(intent.args.get("index", 1))
                except (TypeError, ValueError):
                    self.state.entities["last_result_index"] = 1

            if intent.category == "file_operation" and target:
                self.state.entities["last_file"] = target

            if intent.action == "change_directory" and target:
                self.state.entities["last_directory"] = target


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_usage (
                    action TEXT PRIMARY KEY,
                    usage_count INTEGER NOT NULL,
                    last_used_at TEXT NOT NULL
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
            conn.execute(
                """
                INSERT INTO command_usage(action, usage_count, last_used_at)
                VALUES (?, 1, ?)
                ON CONFLICT(action) DO UPDATE SET
                    usage_count=usage_count+1,
                    last_used_at=excluded.last_used_at
                """,
                (intent.action, datetime.utcnow().isoformat()),
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

    def top_actions(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT action, usage_count, last_used_at
                FROM command_usage
                ORDER BY usage_count DESC, last_used_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "action": row[0],
                "usage_count": int(row[1]),
                "last_used_at": row[2],
            }
            for row in rows
        ]
