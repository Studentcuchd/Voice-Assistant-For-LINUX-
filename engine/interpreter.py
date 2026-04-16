"""Intent-aware natural-language interpreter for the voice assistant.

This module performs four jobs:
1. Normalize and split user input into independent command fragments.
2. Score each fragment against commands loaded from JSON using a mix of
   fuzzy matching, intent cues, and priority rules.
3. Extract command arguments from the natural-language fragment.
4. Provide suggestions when no confident match is found.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Optional

from utils.logger import get_logger

log = get_logger(__name__)

DATA_FILE = Path(__file__).resolve().parent / "data" / "commands.json"
FUZZY_THRESHOLD = 0.68
MIN_CONFIDENCE = 0.58
AMBIGUITY_GAP = 0.06

_PHRASE_SPLIT_WORDS = (
    "and then",
    "after that",
    "followed by",
    "and also",
    "next",
    "then",
    "also",
    "and",
)

_ALIAS_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bopen\s+(?:the\s+)?files?\b", re.IGNORECASE), "show files"),
    (re.compile(r"\bshow\s+me\s+files?\b", re.IGNORECASE), "show files"),
    (re.compile(r"\bcan\s+you\s+show\s+me\s+files?\b", re.IGNORECASE), "show files"),
    (re.compile(r"\bgo\s+to\s+folder\b", re.IGNORECASE), "go to"),
    (re.compile(r"\bgo\s+to\s+directory\b", re.IGNORECASE), "go to"),
    (re.compile(r"\bopen\s+the\s+browser\b", re.IGNORECASE), "open browser"),
    (re.compile(r"\bopen\s+the\s+terminal\b", re.IGNORECASE), "open terminal"),
)

_GENERIC_STOPWORDS = {
    "a",
    "an",
    "the",
    "to",
    "into",
    "in",
    "inside",
    "of",
    "for",
    "please",
    "kindly",
    "just",
    "me",
    "my",
    "your",
    "this",
    "that",
    "some",
    "can",
    "you",
    "could",
    "would",
    "do",
    "open",
    "launch",
    "start",
    "run",
    "go",
    "move",
    "change",
    "navigate",
    "create",
    "make",
    "new",
    "delete",
    "remove",
    "erase",
    "file",
    "folder",
    "directory",
}

_DEFAULT_CATEGORY_PRIORITY = {
    "system_control": 100,
    "file_operation": 95,
    "navigation": 80,
    "application": 70,
    "utility": 50,
    "system_monitor": 45,
}


@dataclass(frozen=True)
class CommandDefinition:
    """Normalized command definition loaded from JSON."""

    id: str
    category: str
    action: str
    description: str
    phrases: tuple[str, ...]
    dangerous: bool = False
    requires_name: bool = False
    priority: int = 0
    app_candidates: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def canonical_phrase(self) -> str:
        return self.phrases[0] if self.phrases else self.description


@dataclass
class Command:
    """Resolved, executable command returned to the executor."""

    id: str
    action: str
    description: str
    dangerous: bool
    argument: Optional[str] = None
    app_candidates: list[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_fragment: str = ""
    matched_phrase: str = ""
    category: str = ""
    priority: int = 0

    def __repr__(self) -> str:
        arg_str = f" -> '{self.argument}'" if self.argument else ""
        return f"<Command {self.id}{arg_str} [{self.confidence:.0%}]>"


@dataclass(frozen=True)
class _CandidateScore:
    definition: CommandDefinition
    phrase: str
    score: float
    base_score: float
    intent_score: float


class Interpreter:
    """Parse free-text input into a list of structured command objects."""

    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self._definitions: list[CommandDefinition] = []
        self._last_command: Optional[Command] = None
        self._last_application: Optional[str] = None
        self._load_commands(data_file)

    def parse(self, text: str) -> list[Command]:
        """Parse one natural-language utterance into executable commands."""
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            return []

        fragments = self._split_into_fragments(normalized_text)
        resolved: list[Command] = []

        for fragment in fragments:
            command = self._resolve_fragment(fragment)
            if command is None:
                log.warning("No command matched for fragment: %s", fragment)
                continue
            resolved.append(command)
            self._update_context(command)

        log.info("Parsed %d fragment(s) into %d command(s)", len(fragments), len(resolved))
        return resolved

    def suggest(self, text: str, top_n: int = 3) -> list[str]:
        """Return a short list of likely commands for an unclear fragment."""
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            return []

        scored = self._score_all(normalized_text)
        scored.sort(key=lambda item: (-item.score, -item.definition.priority, item.definition.description))

        suggestions: list[str] = []
        for item in scored:
            if item.score <= 0:
                continue
            suggestion = item.definition.canonical_phrase or item.definition.description
            if suggestion not in suggestions:
                suggestions.append(suggestion)
            if len(suggestions) >= top_n:
                break
        return suggestions

    def _load_commands(self, path: Path) -> None:
        try:
            with path.open(encoding="utf-8") as handle:
                raw_data = json.load(handle)
        except FileNotFoundError:
            log.error("commands.json not found at %s", path)
            return
        except json.JSONDecodeError as exc:
            log.error("Failed to parse commands.json: %s", exc)
            return

        entries: list[dict[str, Any]]
        if isinstance(raw_data, dict) and "commands" in raw_data:
            entries = list(raw_data.get("commands", []))
        elif isinstance(raw_data, list):
            entries = list(raw_data)
        elif isinstance(raw_data, dict):
            entries = []
            for command_id, entry in raw_data.items():
                if isinstance(entry, dict):
                    merged = dict(entry)
                    merged.setdefault("id", command_id)
                    entries.append(merged)
        else:
            log.error("Unsupported commands.json structure: %s", type(raw_data).__name__)
            return

        self._definitions = [self._build_definition(entry) for entry in entries if isinstance(entry, dict)]
        self._definitions = [definition for definition in self._definitions if definition.id]
        log.info("Loaded %d command definitions from %s", len(self._definitions), path)

    def _build_definition(self, entry: dict[str, Any]) -> CommandDefinition:
        phrases = self._collect_phrases(entry)
        category = str(entry.get("category", "utility")).strip().lower() or "utility"

        raw_priority = entry.get("priority", _DEFAULT_CATEGORY_PRIORITY.get(category, 50))
        try:
            priority = int(raw_priority)
        except (TypeError, ValueError):
            priority = _DEFAULT_CATEGORY_PRIORITY.get(category, 50)

        return CommandDefinition(
            id=str(entry.get("id", "")).strip(),
            category=category,
            action=str(entry.get("action", "")).strip(),
            description=str(entry.get("description", entry.get("id", ""))).strip(),
            phrases=phrases,
            dangerous=bool(entry.get("dangerous", False)),
            requires_name=bool(entry.get("requires_name", False)),
            priority=priority,
            app_candidates=tuple(str(item).strip() for item in entry.get("app_candidates", []) if str(item).strip()),
            metadata={
                key: value
                for key, value in entry.items()
                if key
                not in {
                    "id",
                    "category",
                    "action",
                    "description",
                    "phrases",
                    "keywords",
                    "dangerous",
                    "requires_name",
                    "priority",
                    "app_candidates",
                }
            },
        )

    def _collect_phrases(self, entry: dict[str, Any]) -> tuple[str, ...]:
        phrases: list[str] = []
        raw_phrases = entry.get("phrases")
        if isinstance(raw_phrases, list):
            phrases.extend(str(item).strip().lower() for item in raw_phrases if str(item).strip())

        raw_keywords = entry.get("keywords")
        if isinstance(raw_keywords, list):
            phrases.extend(str(item).strip().lower() for item in raw_keywords if str(item).strip())

        if not phrases and entry.get("description"):
            phrases.append(str(entry["description"]).strip().lower())

        normalized: list[str] = []
        seen: set[str] = set()
        for phrase in phrases:
            phrase = self._normalize_text(phrase)
            if phrase and phrase not in seen:
                normalized.append(phrase)
                seen.add(phrase)

        return tuple(normalized)

    def _normalize_text(self, text: str) -> str:
        value = text.strip().lower()
        if not value:
            return ""

        for pattern, replacement in _ALIAS_RULES:
            value = pattern.sub(replacement, value)

        value = re.sub(r"[^a-z0-9\s/._~:-]+", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _split_into_fragments(self, text: str) -> list[str]:
        fragments: list[str] = []
        buffer: list[str] = []
        index = 0
        quote_char: Optional[str] = None
        lowered = text.lower()

        while index < len(text):
            char = text[index]

            if char in {'"', "'"}:
                if quote_char is None:
                    quote_char = char
                elif quote_char == char:
                    quote_char = None
                buffer.append(char)
                index += 1
                continue

            if quote_char is None:
                separator = self._match_split_separator(lowered, index)
                if separator is not None:
                    fragment = "".join(buffer).strip()
                    if fragment:
                        fragments.append(fragment)
                    buffer.clear()
                    index += len(separator)
                    continue

            buffer.append(char)
            index += 1

        fragment = "".join(buffer).strip()
        if fragment:
            fragments.append(fragment)

        return fragments or [text]

    def _match_split_separator(self, lowered_text: str, index: int) -> Optional[str]:
        for separator in _PHRASE_SPLIT_WORDS:
            if not lowered_text.startswith(separator, index):
                continue

            before_ok = index == 0 or not lowered_text[index - 1].isalnum()
            after_index = index + len(separator)
            after_ok = after_index >= len(lowered_text) or not lowered_text[after_index].isalnum()
            if before_ok and after_ok:
                return separator
        return None

    def _score_all(self, fragment: str) -> list[_CandidateScore]:
        scored: list[_CandidateScore] = []
        for definition in self._definitions:
            scored.append(self._score_definition(fragment, definition))
        return scored

    def _score_definition(self, fragment: str, definition: CommandDefinition) -> _CandidateScore:
        best_phrase = ""
        best_base = 0.0

        phrases = definition.phrases or (definition.description.lower(),)
        for phrase in phrases:
            phrase_score = self._score_phrase(fragment, phrase)
            if phrase_score > best_base:
                best_base = phrase_score
                best_phrase = phrase

        intent_score = self._intent_score(fragment, definition, best_phrase)
        priority_bonus = min(max(definition.priority, 0) / 100.0, 1.0) * 0.12
        confidence = min(1.0, (best_base * 0.72) + intent_score + priority_bonus)

        return _CandidateScore(
            definition=definition,
            phrase=best_phrase,
            score=confidence,
            base_score=best_base,
            intent_score=intent_score,
        )

    def _score_phrase(self, fragment: str, phrase: str) -> float:
        if not phrase:
            return 0.0

        if phrase in fragment:
            return 1.0

        fragment_tokens = fragment.split()
        phrase_tokens = phrase.split()
        if not fragment_tokens or not phrase_tokens:
            return 0.0

        best = 0.0
        window_size = len(phrase_tokens)
        windows = [
            " ".join(fragment_tokens[index : index + window_size])
            for index in range(max(1, len(fragment_tokens) - window_size + 1))
        ]

        for window in windows:
            best = max(best, SequenceMatcher(None, phrase, window).ratio())

        best = max(best, SequenceMatcher(None, phrase, fragment).ratio())

        phrase_set = set(phrase_tokens)
        fragment_set = set(fragment_tokens)
        overlap = len(phrase_set & fragment_set) / max(len(phrase_set), 1)
        best = max(best, overlap * 0.92)

        return best if best >= FUZZY_THRESHOLD else 0.0

    def _intent_score(self, fragment: str, definition: CommandDefinition, matched_phrase: str) -> float:
        tokens = set(fragment.split())
        score = 0.0

        if definition.category == "file_operation":
            if tokens & {"file", "files", "folder", "directory", "directories", "list", "show"}:
                score += 0.18
            if "open" in tokens and "files" in tokens:
                score += 0.20
            if "show files" in matched_phrase or "list files" in matched_phrase:
                score += 0.12

        elif definition.category == "application":
            if tokens & {"open", "launch", "start", "run"}:
                score += 0.08
            if tokens & {"browser", "terminal", "vscode", "editor", "code", "manager"}:
                score += 0.18

        elif definition.category == "navigation":
            if tokens & {"go", "change", "navigate", "move", "cd"}:
                score += 0.16
            if tokens & {"home", "folder", "directory", "path"}:
                score += 0.12

        elif definition.category == "system_control":
            if tokens & {"shutdown", "reboot", "restart", "power", "off", "turn"}:
                score += 0.24

        elif definition.category == "system_monitor":
            if tokens & {"cpu", "memory", "ram", "disk", "processes", "uptime", "ip"}:
                score += 0.16

        elif definition.category == "utility":
            if tokens & {"date", "time", "clock", "ip", "uptime", "clear"}:
                score += 0.14

        if definition.dangerous and tokens & {"delete", "remove", "erase", "shutdown", "reboot", "destroy"}:
            score += 0.08

        return min(score, 0.35)

    def _resolve_fragment(self, fragment: str) -> Optional[Command]:
        contextual = self._resolve_contextual_reference(fragment)
        if contextual is not None:
            return contextual

        candidates = self._score_all(fragment)
        candidates.sort(key=lambda item: (-item.score, -item.definition.priority, item.definition.description))

        if not candidates:
            return None

        top = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        if top.score < MIN_CONFIDENCE:
            return None

        if second and top.score < 0.86 and (top.score - second.score) < AMBIGUITY_GAP:
            log.info(
                "Ambiguous fragment rejected: '%s' (top=%s %.2f, second=%s %.2f)",
                fragment,
                top.definition.id,
                top.score,
                second.definition.id,
                second.score,
            )
            return None

        argument = self._extract_argument(fragment, top.definition, top.phrase)

        command = Command(
            id=top.definition.id,
            action=top.definition.action,
            description=top.definition.description,
            dangerous=top.definition.dangerous,
            argument=argument,
            app_candidates=list(top.definition.app_candidates),
            confidence=top.score,
            raw_fragment=fragment,
            matched_phrase=top.phrase or top.definition.canonical_phrase,
            category=top.definition.category,
            priority=top.definition.priority,
        )

        log.info(
            "Detected intent: %s | action=%s | confidence=%.2f | argument=%s",
            command.id,
            command.action,
            command.confidence,
            command.argument,
        )
        return command

    def _extract_argument(
        self,
        fragment: str,
        definition: CommandDefinition,
        matched_phrase: str,
    ) -> Optional[str]:
        if not definition.requires_name:
            return None

        tail = fragment
        if matched_phrase and matched_phrase in fragment:
            tail = fragment.split(matched_phrase, 1)[1]

        tail = tail.strip()

        if not tail:
            tokens = fragment.split()
            phrase_tokens = set(matched_phrase.split())
            remaining = [token for token in tokens if token not in phrase_tokens and token not in _GENERIC_STOPWORDS]
            candidate = " ".join(remaining)
        else:
            candidate = re.sub(
                r"^(?:to|into|in|inside|the|a|an|my|your|this|that|folder|file|directory|for|of|on|at)\b\s*",
                "",
                tail,
                flags=re.IGNORECASE,
            )
            candidate = candidate.strip()

        candidate = candidate.strip(' "\'')
        candidate = re.sub(r"\s+", " ", candidate)
        return candidate or None

    def _resolve_contextual_reference(self, fragment: str) -> Optional[Command]:
        normalized = fragment.strip().lower()
        if not normalized or self._last_command is None:
            return None

        reference_phrases = {
            "open it",
            "launch it",
            "start it",
            "run it",
            "open again",
            "launch again",
            "start again",
        }

        if normalized not in reference_phrases:
            return None

        if self._last_command.category != "application":
            return None

        contextual = replace(
            self._last_command,
            raw_fragment=fragment,
            confidence=max(self._last_command.confidence, 0.72),
        )
        log.info("Resolved contextual reference '%s' -> %s", fragment, contextual.id)
        return contextual

    def _update_context(self, command: Command) -> None:
        self._last_command = command
        if command.category == "application":
            self._last_application = command.app_candidates[0] if command.app_candidates else command.id
