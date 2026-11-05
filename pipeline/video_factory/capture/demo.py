"""The app's demo, built at its pinned commit with its scenario variant, in a work folder of its own.

The app's repository is never touched: the pinned commit is fetched alone (git fetch --depth 1) into a fresh folder,
the variant applied there by `git apply` (which refuses a patch that does not fit), then the app's own install and build
run with the Node.js of the lock. A finished build is kept under a key made of everything it depends on (commit,
variant, Node.js, commands and their variables), so the next capture of the same demo starts at once.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from video_factory.capture.plan import Source
from video_factory.hashing import sha256_bytes, sha256_file
from video_factory.tools import Toolbox

BUILD_STAMP = "build.json"
GIT = ("git", "-c", "core.fsmonitor=false", "-c", "advice.detachedHead=false")

Runner = Callable[[Sequence[str], Path, Mapping[str, str], str], None]


class DemoError(Exception):
    """The demo cannot be built: the commit cannot be fetched, the variant does not apply, or the build failed."""


def run_command(argv: Sequence[str], cwd: Path, env: Mapping[str, str], what: str) -> None:
    """A step of the build, its output shown as it runs; a failure stops it."""
    print(f"  $ {' '.join(argv)}", flush=True)
    try:
        done = subprocess.run(list(argv), cwd=cwd, env=dict(env), check=False)
    except OSError as exc:
        raise DemoError(f"{what} : {argv[0]} ({exc})") from exc
    if done.returncode != 0:
        raise DemoError(f"{what} : « {' '.join(argv)} » a échoué (code {done.returncode})")


def git_env(base: Mapping[str, str]) -> dict[str, str]:
    """git without the user's configuration, so no hook, filter or credential helper of the machine takes part."""
    env = dict(base)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})
    return env


def fetch(repository: str, commit: str, target: Path, run: Runner = run_command) -> None:
    """The pinned commit alone, checked out in target; the checkout must be that very commit."""
    target.mkdir(parents=True)
    env = git_env(os.environ)
    run([*GIT, "init", "-q"], target, env, "git init")
    run([*GIT, "fetch", "-q", "--depth", "1", repository, commit], target, env, f"git fetch {commit[:7]}")
    run([*GIT, "checkout", "-q", "--detach", "FETCH_HEAD"], target, env, "git checkout")
    head = subprocess.run([*GIT, "rev-parse", "HEAD"], cwd=target, env=env, capture_output=True, text=True, check=False)
    if head.stdout.strip() != commit:
        raise DemoError(f"commit {head.stdout.strip() or '?'} récupéré au lieu de {commit}")


def apply_variant(target: Path, patch: Path, run: Runner = run_command) -> None:
    """The scenario variant, checked then applied; a patch that does not fit the pinned commit stops everything."""
    env = git_env(os.environ)
    run([*GIT, "apply", "--check", str(patch)], target, env, f"la variante {patch.name} ne s'applique pas")
    run([*GIT, "apply", str(patch)], target, env, f"git apply {patch.name}")


def build_key(source: Source, node_version: str) -> dict:
    """Everything a build depends on; its SHA-256 names the build's folder."""
    doc = source.doc
    return {
        "app": doc["app"],
        "repository": doc["repository"],
        "commit": doc["commit"],
        "patch_sha256": sha256_file(source.patch),
        "node": f"{doc['node']} {node_version}",
        "install": doc["install"],
        "build": doc["build"],
        "build_env": doc["build_env"],
    }


def key_digest(key: Mapping[str, object]) -> str:
    return sha256_bytes(json.dumps(key, sort_keys=True, ensure_ascii=False).encode())


def built(folder: Path, key: Mapping[str, object]) -> bool:
    stamp = folder / BUILD_STAMP
    if not stamp.is_file() or not (folder / "demo" / "index.html").is_file():
        return False
    try:
        return json.loads(stamp.read_text(encoding="utf-8")) == dict(key)
    except ValueError:
        return False


def build(source: Source, toolbox: Toolbox, work: Path, run: Runner = run_command) -> Path:
    """The folder of the built demo (served as it is), built now unless the same build is already there."""
    node = toolbox.entry(str(source.doc["node"]))
    key = build_key(source, str(node["version"]))
    folder = work / str(source.doc["app"]) / key_digest(key)[:16]
    if built(folder, key):
        return folder / "demo"
    if folder.exists():
        shutil.rmtree(folder)
    src = folder / "src"
    fetch(str(source.doc["repository"]), str(source.doc["commit"]), src, run)
    apply_variant(src, source.patch, run)
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(toolbox.home(str(node["name"])) / "bin"), env.get("PATH", "")])
    env.update({str(name): str(value) for name, value in dict(source.doc["build_env"]).items()})
    env[str(source.doc["out_dir_env"])] = str(folder / "demo")
    run([str(part) for part in source.doc["install"]], src, env, "installation de la démo")
    run([str(part) for part in source.doc["build"]], src, env, "construction de la démo")
    if not (folder / "demo" / "index.html").is_file():
        raise DemoError(f"la construction n'a pas écrit {folder / 'demo' / 'index.html'}")
    (folder / BUILD_STAMP).write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return folder / "demo"
