"""Phase 3 memory — lightweight short-term and long-term stores.

Kept separate from the agent/coordination code so a later phase can swap
these for a proper database (or vector store) without rewriting main.py.
"""

import json
from pathlib import Path

# Cap stored turns per session so the in-memory store stays small.
_MAX_TURNS = 20


class ShortTermMemory:
    """In-session conversation history, keyed by session id. In-process only."""

    def __init__(self):
        self._sessions: dict[str, list[dict[str, str]]] = {}

    def history(self, session_id: str) -> list[dict[str, str]]:
        return self._sessions.get(session_id, [])

    def add_turn(self, session_id: str, user_message: str, reply: str) -> None:
        turns = self._sessions.setdefault(session_id, [])
        turns.append({"user": user_message, "assistant": reply})
        del turns[:-_MAX_TURNS]


class PreferenceStore:
    """Durable user preferences in a small JSON file — survives restarts."""

    def __init__(self, path: Path):
        self._path = path
        self._prefs: dict[str, str] = {}
        if path.exists():
            try:
                self._prefs = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                print("[MEMORY] preferences file unreadable, starting empty")
        print(f"[MEMORY] loaded {len(self._prefs)} preferences")

    def all(self) -> dict[str, str]:
        return dict(self._prefs)

    def save(self, key: str, value: str) -> None:
        self._prefs[key] = value
        self._path.write_text(
            json.dumps(self._prefs, indent=2), encoding="utf-8"
        )
        print(f"[MEMORY] saved preference: {key}={value}")
