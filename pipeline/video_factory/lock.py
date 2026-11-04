"""The toolchain lock (toolchain/tools.lock.json): every external tool, pinned by version and SHA-256.

The schema (toolchain/tools.lock.schema.json) fixes the shape of each kind of entry; this module adds the rules a schema
cannot say: unique names, dependencies declared before the tools that need them, and an install command that is the one
`vf doctor` prints.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from video_factory import schemas
from video_factory.paths import LOCK_SCHEMA

Tool = Mapping[str, object]

INSTALL_COMMAND = "uv run vf doctor --install {name}"


class LockError(Exception):
    """The lock file is unreadable or breaks one of its rules."""


def install_command(name: str) -> str:
    return INSTALL_COMMAND.format(name=name)


def rule_problems(lock: Mapping[str, object]) -> list[str]:
    """The rules beyond the schema, for a lock that already matches it."""
    found = []
    seen: set[str] = set()
    for tool in lock["tools"]:
        name = str(tool["name"])
        if name in seen:
            found.append(f"{name} : nom en double")
        for needed in tool.get("requires", []):
            if needed not in seen:
                found.append(f"{name} : « {needed} » doit être déclaré avant lui")
        if tool["install"] != install_command(name):
            found.append(f"{name} : la commande d'installation doit être « {install_command(name)} »")
        seen.add(name)
    return found


def load(path: Path, schema_path: Path = LOCK_SCHEMA) -> dict:
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LockError(f"{path} illisible : {exc}") from exc
    found = schemas.problems(lock, schema_path) or rule_problems(lock)
    if found:
        raise LockError(f"{path} invalide :\n" + "\n".join(f"- {line}" for line in found))
    return lock


def by_name(lock: Mapping[str, object]) -> dict[str, Tool]:
    return {str(tool["name"]): tool for tool in lock["tools"]}


def tool_dir(tools_root: Path, tool: Tool) -> Path:
    """Each tool lives in its own versioned directory, so two versions never overwrite each other."""
    return tools_root / str(tool["name"]) / str(tool["version"])


def tool_env(tool: Tool, lock: Mapping[str, object], tools_root: Path, base: Mapping[str, str]) -> dict[str, str]:
    """The environment a tool runs in: the bin directories of the tools it requires first on PATH, then its own
    variables (for HyperFrames: telemetry, update checks and optional installs turned off)."""
    tools = by_name(lock)
    env = dict(base)
    bins = [str(tool_dir(tools_root, tools[name]) / "bin") for name in tool.get("requires", [])]
    env["PATH"] = os.pathsep.join([*bins, base.get("PATH", "")]).rstrip(os.pathsep)
    env.update({str(key): str(value) for key, value in dict(tool.get("env", {})).items()})
    return env


def requirement_order(lock: Mapping[str, object], names: list[str]) -> list[str]:
    """The named tools and everything they require, in lock order (dependencies first)."""
    tools = by_name(lock)
    unknown = [name for name in names if name not in tools]
    if unknown:
        raise LockError("outil inconnu : " + ", ".join(unknown) + " ; outils : " + ", ".join(tools))
    wanted: set[str] = set()
    pending = list(names)
    while pending:
        name = pending.pop()
        if name not in wanted:
            wanted.add(name)
            pending.extend(str(needed) for needed in tools[name].get("requires", []))
    return [name for name in tools if name in wanted]
