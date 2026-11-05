"""A plan shot: the driver run with the pinned Node.js, Playwright and Chromium on the built demo, then the fingerprint
of every frame and of the track, so two captures of the same plan can be told identical or not."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

from video_factory import lock as lockfile
from video_factory.capture.plan import Source
from video_factory.hashing import sha256_bytes, sha256_file
from video_factory.tools import Toolbox

DRIVER = Path(__file__).with_name("driver.mjs")
FINGERPRINTS = "empreintes.json"


class ShootError(Exception):
    """The driver failed or wrote less than the plan asks for."""


def job(plan: Mapping[str, object], source: Source, toolbox: Toolbox, demo: Path, out: Path) -> dict:
    """What the driver reads: the plan, where the pinned tools and the demo are, and how the app starts."""
    chromium = toolbox.entry("chromium-headless-shell")
    return {
        "plan": dict(plan),
        "playwright": str(toolbox.home("playwright") / "node_modules" / "playwright-core"),
        "chromium": str(toolbox.file("chromium-headless-shell", "chrome-headless-shell")),
        "chromium_version": chromium["version"],
        "demo": str(demo),
        "out": str(out),
        "storage": dict(source.doc.get("storage", {})),
        "ready": source.doc["ready"],
        "font": source.doc.get("font"),
    }


def driver_env(toolbox: Toolbox, base: Mapping[str, str]) -> dict[str, str]:
    """The pinned Node.js first on PATH and Playwright's own variables (no browser download)."""
    tool = toolbox.entry("playwright")
    return lockfile.tool_env(tool, toolbox.pinned, toolbox.root, base)


def run_driver(job_doc: Mapping[str, object], toolbox: Toolbox, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    job_file = out / "job.json"
    job_file.write_text(json.dumps(job_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    node = toolbox.file("node", "bin/node")
    toolbox.file("playwright", "node_modules/playwright-core/package.json")
    try:
        done = subprocess.run([str(node), str(DRIVER), str(job_file)], env=driver_env(toolbox, os.environ), check=False)
    except OSError as exc:
        raise ShootError(f"capture : {node} ({exc})") from exc
    if done.returncode != 0:
        raise ShootError(f"capture : le pilote s'est arrêté (code {done.returncode})")


def frame_count(plan: Mapping[str, object]) -> int:
    scenario = plan["scenario"]
    return round((round(scenario["end"] * 1000) - round(scenario["start"] * 1000)) * plan["fps"] / 1000)


def fingerprints(out: Path, frames: int) -> dict:
    """The SHA-256 of each frame and of the track, and one over all of them: two captures of a plan are identical
    when their « all » match."""
    names = sorted(path.name for path in (out / "frames").glob("f_*.png"))
    if len(names) != frames:
        raise ShootError(f"capture : {len(names)} images au lieu de {frames}")
    found = {name: sha256_file(out / "frames" / name) for name in names}
    track = sha256_file(out / "track.json")
    lines = "".join(f"{name}\0{digest}\n" for name, digest in found.items()) + f"track.json\0{track}\n"
    return {"all": sha256_bytes(lines.encode()), "track": track, "frames": found}


def shoot(plan: Mapping[str, object], source: Source, toolbox: Toolbox, demo: Path, out: Path) -> dict:
    run_driver(job(plan, source, toolbox, demo, out), toolbox, out)
    found = fingerprints(out, frame_count(plan))
    (out / FINGERPRINTS).write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
    return found
