"""The shooting routes (mask/routes.json): how each way of filming the masked take is cropped and set right.

The schema fixes the shape; this module adds what a schema cannot say: the default route exists, each crop lies inside
its source and is 9:16. A route's fingerprint is that of its canonical JSON, so editing a route makes `ingest` stale.
"""

from __future__ import annotations

import json
from pathlib import Path

from video_factory import schemas
from video_factory.hashing import sha256_bytes
from video_factory.paths import ROUTES_SCHEMA


class RouteError(Exception):
    """The routes file is unreadable or breaks a rule, or the named route does not exist."""


def rule_problems(routes: dict) -> list[str]:
    found = []
    if routes["default"] not in routes["routes"]:
        found.append(f"default : la voie « {routes['default']} » n'existe pas")
    for name, route in routes["routes"].items():
        crop, source = route["crop"], route["source"]
        if crop["x"] + crop["width"] > source["width"] or crop["y"] + crop["height"] > source["height"]:
            found.append(f"{name} : la zone utile dépasse l'image source")
        if crop["width"] * 16 != crop["height"] * 9:
            found.append(f"{name} : la zone utile n'est pas en 9:16 ({crop['width']}x{crop['height']})")
    return found


def load(path: Path, schema_path: Path = ROUTES_SCHEMA) -> dict:
    try:
        routes = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RouteError(f"{path} illisible : {exc}") from exc
    found = schemas.problems(routes, schema_path) or rule_problems(routes)
    if found:
        raise RouteError(f"{path} invalide :\n" + "\n".join(f"- {line}" for line in found))
    return routes


def pick(routes: dict, name: str | None) -> tuple[str, dict]:
    chosen = name or routes["default"]
    if chosen not in routes["routes"]:
        raise RouteError(f"voie « {chosen} » inconnue ; voies : {', '.join(routes['routes'])}")
    return chosen, routes["routes"][chosen]


def fingerprint(route: dict) -> str:
    """The SHA-256 of the route's canonical JSON (sorted keys, no spaces)."""
    return sha256_bytes(json.dumps(route, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
