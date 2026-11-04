"""state.json of a video: read (a version 1 state is moved to version 2), checked against the schema, written whole.

Every write is validated first and goes through a temporary file renamed over the old one, so a state is never left
half written and never breaks its published schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from video_factory import schemas
from video_factory.paths import STATE_SCHEMA

VERSION = 2


class StateError(Exception):
    """The state is unreadable, breaks its schema, or cannot be moved to the current version."""


def migrate(state: dict) -> dict:
    """A version 1 state as version 2: version 1 had no step that a chain ever wrote, so only empty ones move."""
    if state.get("schema_version") != 1:
        return state
    if state.get("steps"):
        raise StateError("état en version 1 avec des étapes : à refaire depuis vf new")
    return {**state, "schema_version": VERSION, "takes": [], "captures": {}, "steps": {}}


def problems(state: dict) -> list[str]:
    return schemas.problems(state, STATE_SCHEMA)


def load(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StateError(f"{path} illisible : {exc}") from exc
    state = migrate(state)
    found = problems(state)
    if found:
        raise StateError(f"{path} invalide :\n" + "\n".join(f"- {line}" for line in found))
    return state


def text(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def save(path: Path, state: dict) -> None:
    """Validate, then replace path in one rename."""
    found = problems(state)
    if found:
        raise StateError("état refusé, il ne suit pas son schéma :\n" + "\n".join(f"- {line}" for line in found))
    staged = path.with_name(f".{path.name}.new")
    staged.write_text(text(state), encoding="utf-8")
    staged.replace(path)
