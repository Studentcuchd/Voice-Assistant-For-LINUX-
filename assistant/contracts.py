"""Shared contracts and typed models for the production assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Intent:
    """Canonical intent produced by rule engine or fallback parser."""

    id: str
    action: str
    category: str
    description: str
    args: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    dangerous: bool = False
    source: str = "rules"


@dataclass
class PlanStep:
    """One executable step in a plan."""

    id: str
    action: str
    plugin: str
    args: dict[str, Any] = field(default_factory=dict)
    dangerous: bool = False
    intent_id: str = ""


@dataclass
class ExecutionResult:
    """Execution status from plugins and orchestrator."""

    ok: bool
    message: str
    step_id: str = ""
    plugin: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    """Short-term in-memory context for follow-ups and preferences."""

    started_at: datetime = field(default_factory=datetime.utcnow)
    last_user_utterance: str = ""
    last_intents: list[Intent] = field(default_factory=list)
    last_results: list[ExecutionResult] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssistantContext:
    """Execution context shared across orchestrator and plugins."""

    cwd: str
    session_id: str
    state: SessionState
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyDecision:
    """Policy/risk decision outcome before execution."""

    allow: bool
    risk: str
    requires_confirmation: bool
    reason: str
    step: Optional[PlanStep] = None
