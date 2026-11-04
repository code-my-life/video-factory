"""Where vf finds its own resources, the content clone, the media store and the pinned tools.

The repository resources (lock, schemas, templates) are read from the checkout that runs vf: the package is installed
in editable mode by `uv sync` and is never distributed on its own. The three outside places come from the environment,
with defaults under the home directory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCK_FILE = REPO_ROOT / "toolchain" / "tools.lock.json"
LOCK_SCHEMA = REPO_ROOT / "toolchain" / "tools.lock.schema.json"
SCHEMAS_DIR = REPO_ROOT / "schemas"
STATE_SCHEMA = SCHEMAS_DIR / "state.schema.json"
SCRIPT_SCHEMA = SCHEMAS_DIR / "script.schema.json"
SCRIPT_TEMPLATE = REPO_ROOT / "templates" / "script.md"
ROUTES_FILE = REPO_ROOT / "mask" / "routes.json"
ROUTES_SCHEMA = SCHEMAS_DIR / "routes.schema.json"
COMPOSITION_TEMPLATE = REPO_ROOT / "templates" / "composition"

CONTENT_VAR = "VF_CONTENT"
MEDIA_VAR = "VF_MEDIA"
TOOLS_VAR = "VF_TOOLS"


@dataclass(frozen=True)
class Places:
    """The content clone (scripts and states), the media store and the directory of the pinned tools."""

    content: Path
    media: Path
    tools: Path


def places(env: Mapping[str, str], home: Path) -> Places:
    """Read VF_CONTENT, VF_MEDIA and VF_TOOLS from env; an unset or empty variable falls back to its default."""

    def pick(name: str, default: Path) -> Path:
        value = env.get(name, "").strip()
        if not value:
            return default
        if value == "~" or value.startswith("~/"):
            return home / value[2:]
        return Path(value)

    return Places(
        content=pick(CONTENT_VAR, home / "perso" / "video-content"),
        media=pick(MEDIA_VAR, home / "studio" / "media"),
        tools=pick(TOOLS_VAR, home / ".local" / "share" / "video-factory" / "tools"),
    )
