"""`vf doctor`: every tool of the lock is present, at its version and its SHA-256, and the outside places exist.

Each check returns the problems it finds; a problem names its subject (a tool or a place), the gap, and the exact
command that fixes it. Commands go through a runner, so tests replace the processes with recorded answers.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from video_factory import lock as lockfile
from video_factory.hashing import sha256_file, tree_sha256
from video_factory.paths import Places

BUILD_STAMP = ".vf-build.json"
INSTALL_STAMP = ".vf-install.json"
STAMPS = frozenset({BUILD_STAMP, INSTALL_STAMP})
CONTENT_REMOTE = "https://github.com/code-my-life/video-content.git"


@dataclass(frozen=True)
class Problem:
    subject: str
    gap: str
    fix: str


@dataclass(frozen=True)
class Completed:
    returncode: int
    output: str


Runner = Callable[[list[str], Mapping[str, str] | None], Completed]


def run_command(argv: list[str], env: Mapping[str, str] | None = None) -> Completed:
    """Run a command and keep its exit code and its output (stdout then stderr); never raises."""
    try:
        done = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=300, check=False)
    except FileNotFoundError:
        return Completed(127, f"{argv[0]} introuvable")
    except subprocess.TimeoutExpired:
        return Completed(124, f"{argv[0]} : délai dépassé")
    except OSError as exc:
        return Completed(126, f"{argv[0]} : {exc}")
    return Completed(done.returncode, done.stdout + done.stderr)


def short(digest: str) -> str:
    return digest[:16] + "…"


def first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "(rien)")


def version_problem(tool: lockfile.Tool, home: Path, env: Mapping[str, str], run: Runner) -> Problem | None:
    """The version command of a tool (its program given relative to the tool's directory) prints the expected text."""
    check = tool["version_check"]
    command = [str(home / check["command"][0]), *check["command"][1:]]
    done = run(command, env)
    if done.returncode == 0 and check["expect"] in done.output:
        return None
    shown = " ".join([PurePosixPath(check["command"][0]).name, *check["command"][1:]])
    return Problem(
        str(tool["name"]),
        f"version : « {check['expect'].strip()} » attendue, « {shown} » répond « {first_line(done.output)} »",
        str(tool["install"]),
    )


def tree_problem(tool: lockfile.Tool, root: Path, expected: str, what: str) -> Problem | None:
    if not root.is_dir():
        return Problem(str(tool["name"]), f"{what} absent ({root})", str(tool["install"]))
    found = tree_sha256(root, STAMPS)
    if found != expected:
        return Problem(
            str(tool["name"]),
            f"{what} : empreinte {short(found)} au lieu de {short(expected)} ({root})",
            str(tool["install"]),
        )
    return None


def check_archive(tool: lockfile.Tool, home: Path, env: Mapping[str, str], run: Runner) -> list[Problem]:
    problem = tree_problem(tool, home, str(tool["tree_sha256"]), "dossier")
    if problem:
        return [problem]
    problem = version_problem(tool, home, env, run)
    return [problem] if problem else []


def check_file(tool: lockfile.Tool, home: Path) -> list[Problem]:
    path = home / str(tool["file"])
    if not path.is_file():
        return [Problem(str(tool["name"]), f"{tool['file']} absent ({path})", str(tool["install"]))]
    found = sha256_file(path)
    if found != tool["sha256"]:
        return [
            Problem(
                str(tool["name"]),
                f"{tool['file']} : empreinte {short(found)} au lieu de {short(str(tool['sha256']))}",
                str(tool["install"]),
            )
        ]
    return []


def read_stamp(path: Path) -> dict:
    try:
        stamp = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return stamp if isinstance(stamp, dict) else {}


def build_stamp(tool: lockfile.Tool) -> dict:
    """What a source build records next to its binary: the verified source and the exact build options."""
    return {"source_sha256": tool["sha256"], "commit": tool["commit"], "cmake_args": list(tool["cmake_args"])}


def check_source_build(tool: lockfile.Tool, home: Path, env: Mapping[str, str], run: Runner) -> list[Problem]:
    name, fix = str(tool["name"]), str(tool["install"])
    binary = home / str(tool["binary"])
    if not binary.is_file():
        return [Problem(name, f"{tool['binary']} absent ({binary})", fix)]
    stamp = read_stamp(home / BUILD_STAMP)
    recorded = {key: stamp.get(key) for key in build_stamp(tool)}
    if recorded != build_stamp(tool):
        return [
            Problem(name, f"construit depuis une autre source ou d'autres options que celles du lock ({home})", fix)
        ]
    if sha256_file(binary) != stamp.get("binary_sha256"):
        return [Problem(name, f"{tool['binary']} modifié depuis sa construction", fix)]
    problem = version_problem(tool, home, env, run)
    return [problem] if problem else []


def config_problem(tool: lockfile.Tool, user_home: Path) -> Problem | None:
    """A setting the tool keeps in its own file, such as HyperFrames' telemetry choice."""
    expect = tool.get("config_expect")
    if not expect:
        return None
    path = user_home / str(expect["path"]).removeprefix("~/")
    stamp = read_stamp(path)
    wrong = {key: stamp.get(key) for key, value in expect["values"].items() if stamp.get(key) != value}
    if wrong:
        wanted = ", ".join(f"{key} = {json.dumps(expect['values'][key])}" for key in wrong)
        return Problem(str(tool["name"]), f"réglage attendu dans {path} : {wanted}", str(tool["install"]))
    return None


def check_npm(
    tool: lockfile.Tool, home: Path, env: Mapping[str, str], run: Runner, repo_root: Path, user_home: Path
) -> list[Problem]:
    name, fix = str(tool["name"]), str(tool["install"])
    package_dir = home / "node_modules" / str(tool["package"])
    manifest = read_stamp(package_dir / "package.json")
    if not manifest:
        return [Problem(name, f"paquet npm absent ({package_dir})", fix)]
    if manifest.get("version") != tool["version"]:
        return [Problem(name, f"version {manifest.get('version')} installée au lieu de {tool['version']}", fix)]
    problem = tree_problem(tool, package_dir, str(tool["tree_sha256"]), "paquet")
    if problem:
        return [problem]
    if read_stamp(home / INSTALL_STAMP).get("lockfile_sha256") != sha256_file(repo_root / str(tool["lockfile"])):
        return [Problem(name, f"installé depuis un autre {tool['lockfile']}", fix)]
    found = [version_problem(tool, home, env, run), config_problem(tool, user_home)]
    return [problem for problem in found if problem]


def image_repository(image: str) -> str:
    """« node:22-bookworm-slim » gives « node »: the name RepoDigests uses."""
    last = image.rsplit("/", 1)[-1]
    return image[: len(image) - len(last)] + last.split(":", 1)[0]


def check_docker_image(tool: lockfile.Tool, run: Runner) -> list[Problem]:
    name, fix, image = str(tool["name"]), str(tool["install"]), str(tool["image"])
    digest = f"{image_repository(image)}@sha256:{tool['sha256']}"
    done = run(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", image], None)
    if done.returncode == 127:
        return [Problem(name, "docker introuvable", f"installer Docker Desktop (intégration WSL), puis {fix}")]
    if done.returncode != 0:
        if "No such image" in done.output or "no such image" in done.output.lower():
            return [Problem(name, f"image {image} absente", fix)]
        return [
            Problem(name, f"Docker ne répond pas : {first_line(done.output)}", f"démarrer Docker Desktop, puis {fix}")
        ]
    if digest not in done.output:
        return [Problem(name, f"{image} n'est pas l'image figée {short(str(tool['sha256']))}", fix)]
    return []


def check_tool(
    tool: lockfile.Tool,
    lock: Mapping[str, object],
    places: Places,
    run: Runner,
    base_env: Mapping[str, str],
    repo_root: Path,
    user_home: Path,
) -> list[Problem]:
    home = lockfile.tool_dir(places.tools, tool)
    env = lockfile.tool_env(tool, lock, places.tools, base_env)
    kind = tool["kind"]
    if kind == "archive":
        return check_archive(tool, home, env, run)
    if kind == "file":
        return check_file(tool, home)
    if kind == "source-build":
        return check_source_build(tool, home, env, run)
    if kind == "npm":
        return check_npm(tool, home, env, run, repo_root, user_home)
    return check_docker_image(tool, run)


def check_places(places: Places) -> list[tuple[str, list[Problem]]]:
    """The content clone and the media store: present, and the store on the WSL disk, not on a Windows drive."""
    content = []
    if not (places.content / ".git").exists():
        content.append(
            Problem("dépôt de contenu", f"{places.content} absent", f"git clone {CONTENT_REMOTE} {places.content}")
        )
    media = []
    if places.media.is_relative_to("/mnt"):
        media.append(
            Problem(
                "magasin des médias",
                f"{places.media} est sur un disque Windows : les médias vont sur le disque de WSL",
                "export VF_MEDIA=~/studio/media",
            )
        )
    elif not places.media.is_dir():
        media.append(Problem("magasin des médias", f"{places.media} absent", f"mkdir -p {places.media}"))
    return [(f"dépôt de contenu {places.content}", content), (f"magasin des médias {places.media}", media)]


def diagnose(
    lock: Mapping[str, object],
    places: Places,
    run: Runner,
    base_env: Mapping[str, str],
    repo_root: Path,
    user_home: Path,
) -> list[tuple[str, list[Problem]]]:
    """(label, problems) for each tool of the lock, then for each outside place."""
    results = []
    for tool in lock["tools"]:
        label = f"{tool['name']} {tool['version']}"
        results.append((label, check_tool(tool, lock, places, run, base_env, repo_root, user_home)))
    return results + check_places(places)


def report(results: list[tuple[str, list[Problem]]], lock_path: Path, tools_root: Path) -> tuple[str, int]:
    """The text vf doctor prints and its exit code: 0 when nothing is wrong, 1 otherwise."""
    lines = [f"Outils de {lock_path.name}, dans {tools_root} :"]
    count = 0
    for label, problems in results:
        if not problems:
            lines.append(f"  ok     {label}")
        for problem in problems:
            count += 1
            lines.append(f"  écart  {problem.subject} : {problem.gap}")
            lines.append(f"         répare : {problem.fix}")
    lines.append("")
    if count:
        lines.append(f"vf doctor : {count} problème{'s' if count > 1 else ''}.")
    else:
        lines.append("vf doctor : tout est en place.")
    return "\n".join(lines), 1 if count else 0
