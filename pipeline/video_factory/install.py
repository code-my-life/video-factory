"""`vf doctor --install`: download each tool of the lock, check its SHA-256 before any use, then put it in place.

Nothing reaches the tools directory unverified: a download is hashed while it is written and refused on any gap, an
archive is extracted with the « data » filter (no absolute path, no escape, no device), a source archive must also carry
the pinned commit, and a tool directory is replaced in one rename once it is complete.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from video_factory import doctor
from video_factory import lock as lockfile
from video_factory.hashing import CHUNK, npm_integrity, sha256_file, tree_sha256
from video_factory.paths import Places

Opener = Callable[[str], object]


class InstallError(Exception):
    """A step of an installation failed; nothing unverified was put in place."""


def open_url(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "video-factory"})
    return urllib.request.urlopen(request, timeout=60)


def download(url: str, expected: str, target: Path, opener: Opener = open_url) -> Path:
    """Write url to target while hashing it; keep it only if its SHA-256 is the expected one."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    try:
        with opener(url) as response, partial.open("wb") as out:
            while chunk := response.read(CHUNK):
                digest.update(chunk)
                out.write(chunk)
    except (OSError, http.client.HTTPException) as exc:
        partial.unlink(missing_ok=True)
        raise InstallError(f"{url} : téléchargement impossible ({exc})") from exc
    if digest.hexdigest() != expected:
        partial.unlink(missing_ok=True)
        raise InstallError(f"{url} : empreinte {digest.hexdigest()} au lieu de {expected}, fichier refusé")
    partial.replace(target)
    return target


def strip_filter(strip: int) -> Callable[[tarfile.TarInfo, str], tarfile.TarInfo | None]:
    """The « data » extraction filter, after removing the first `strip` components of every name."""

    def keep(member: tarfile.TarInfo, destination: str) -> tarfile.TarInfo | None:
        parts = PurePosixPath(member.name).parts
        if len(parts) <= strip:
            return None
        changes = {"name": "/".join(parts[strip:])}
        if member.islnk():
            changes["linkname"] = "/".join(PurePosixPath(member.linkname).parts[strip:])
        return tarfile.data_filter(member.replace(**changes, deep=False), destination)

    return keep


def zip_member_path(name: str, strip: int) -> PurePosixPath | None:
    """Where a zip member goes once its first `strip` components are removed; None for what is left out. A name that
    is absolute or climbs out of the destination is refused."""
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise InstallError(f"membre de zip refusé : {name}")
    parts = path.parts[strip:]
    return PurePosixPath(*parts) if parts else None


def extract_zip(archive: Path, destination: Path, strip: int) -> None:
    """A zip (Chrome for Testing ships its builds so): regular files only, each with its Unix mode, no link."""
    try:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise InstallError(f"{archive.name} : lien symbolique refusé ({member.filename})")
                relative = zip_member_path(member.filename, strip)
                if relative is None or member.is_dir():
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out)
                target.chmod(0o755 if mode & 0o111 else 0o644)
    except (zipfile.BadZipFile, OSError) as exc:
        raise InstallError(f"{archive.name} : archive refusée ({exc})") from exc


def extract(archive: Path, destination: Path, strip: int) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        extract_zip(archive, destination, strip)
        return
    try:
        with tarfile.open(archive) as tar:
            tar.extractall(destination, filter=strip_filter(strip))
    except tarfile.TarError as exc:
        raise InstallError(f"{archive.name} : archive refusée ({exc})") from exc


def archive_commit(archive: Path) -> str | None:
    """The commit GitHub writes in the pax header of a source archive."""
    with tarfile.open(archive) as tar:
        return tar.pax_headers.get("comment")


def swap_in(staged: Path, final: Path) -> None:
    """Replace final by staged in one rename; the previous directory is removed only afterwards."""
    final.parent.mkdir(parents=True, exist_ok=True)
    old = final.with_name(final.name + ".old")
    if old.exists():
        shutil.rmtree(old)
    if final.exists():
        final.rename(old)
    staged.rename(final)
    if old.exists():
        shutil.rmtree(old)


@contextmanager
def workspace(tools_root: Path, name: str):
    """A scratch directory next to the tools, so the final rename never crosses a file system."""
    tools_root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=tools_root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def run_step(argv: list[str], env: Mapping[str, str], cwd: Path, what: str) -> None:
    """A build or install command, its output shown as it runs; a failure stops the installation."""
    print(f"  $ {' '.join(argv)}", flush=True)
    try:
        done = subprocess.run(argv, env=dict(env), cwd=cwd, check=False)
    except OSError as exc:
        raise InstallError(f"{what} : {argv[0]} ({exc})") from exc
    if done.returncode != 0:
        raise InstallError(f"{what} : « {' '.join(argv)} » a échoué (code {done.returncode})")


def install_archive(tool: lockfile.Tool, final: Path, scratch: Path, opener: Opener) -> None:
    archive = download(str(tool["url"]), str(tool["sha256"]), scratch / "download", opener)
    staged = scratch / "staged"
    extract(archive, staged, int(tool["strip_components"]))
    found = tree_sha256(staged)
    if found != tool["tree_sha256"]:
        raise InstallError(f"{tool['name']} : contenu extrait d'empreinte {found} au lieu de {tool['tree_sha256']}")
    swap_in(staged, final)


def install_file(tool: lockfile.Tool, final: Path, scratch: Path, opener: Opener) -> None:
    staged = scratch / "staged"
    download(str(tool["url"]), str(tool["sha256"]), staged / str(tool["file"]), opener)
    swap_in(staged, final)


def install_source_build(
    tool: lockfile.Tool, lock: Mapping[str, object], places: Places, final: Path, scratch: Path, opener: Opener
) -> None:
    archive = download(str(tool["url"]), str(tool["sha256"]), scratch / "download", opener)
    commit = archive_commit(archive)
    if commit != tool["commit"]:
        raise InstallError(f"{tool['name']} : l'archive porte le commit {commit} au lieu de {tool['commit']}")
    source, build, staged = scratch / "source", scratch / "build", scratch / "staged"
    extract(archive, source, 1)
    env = lockfile.tool_env(tool, lock, places.tools, os.environ)
    cmake = str(lockfile.tool_dir(places.tools, lockfile.by_name(lock)["cmake"]) / "bin" / "cmake")
    run_step([cmake, "-S", str(source), "-B", str(build), *map(str, tool["cmake_args"])], env, scratch, "configuration")
    jobs = str(os.cpu_count() or 2)
    run_step([cmake, "--build", str(build), "--target", str(tool["target"]), "-j", jobs], env, scratch, "compilation")
    binary = staged / str(tool["binary"])
    binary.parent.mkdir(parents=True)
    shutil.copy2(build / str(tool["binary"]), binary)
    stamp = doctor.build_stamp(tool) | {"binary_sha256": sha256_file(binary)}
    (staged / doctor.BUILD_STAMP).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    swap_in(staged, final)


def lockfile_integrity(lockfile_path: Path, package: str) -> str | None:
    data = json.loads(lockfile_path.read_text(encoding="utf-8"))
    return data.get("packages", {}).get(f"node_modules/{package}", {}).get("integrity")


def install_npm(
    tool: lockfile.Tool,
    lock: Mapping[str, object],
    places: Places,
    final: Path,
    scratch: Path,
    opener: Opener,
    repo_root: Path,
) -> None:
    tarball = download(str(tool["url"]), str(tool["sha256"]), scratch / "download", opener)
    npm_lock = repo_root / str(tool["lockfile"])
    pinned = lockfile_integrity(npm_lock, str(tool["package"]))
    if npm_integrity(tarball) != pinned:
        raise InstallError(f"{tool['name']} : {tool['lockfile']} ne fige pas l'archive vérifiée ({pinned})")
    staged = scratch / "staged"
    staged.mkdir()
    shutil.copy2(npm_lock, staged / "package-lock.json")
    shutil.copy2(npm_lock.with_name("package.json"), staged / "package.json")
    env = lockfile.tool_env(tool, lock, places.tools, os.environ)
    npm = str(lockfile.tool_dir(places.tools, lockfile.by_name(lock)["node"]) / "bin" / "npm")
    run_step([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], env, staged, "npm ci")
    found = tree_sha256(staged / "node_modules" / str(tool["package"]))
    if found != tool["tree_sha256"]:
        raise InstallError(f"{tool['name']} : paquet installé d'empreinte {found} au lieu de {tool['tree_sha256']}")
    stamp = {"lockfile_sha256": sha256_file(npm_lock)}
    (staged / doctor.INSTALL_STAMP).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    swap_in(staged, final)
    for command in tool.get("post_install", []):
        run_step([str(final / command[0]), *command[1:]], env, final, "après l'installation")


def install_library(tool: lockfile.Tool, final: Path, scratch: Path, opener: Opener) -> None:
    """Only the files the lock names, taken from the verified archive and each checked against its own SHA-256."""
    archive = download(str(tool["url"]), str(tool["sha256"]), scratch / "download", opener)
    staged = scratch / "staged"
    staged.mkdir()
    try:
        with tarfile.open(archive) as tar:
            for name, pinned in dict(tool["files"]).items():
                try:
                    member = tar.getmember(str(pinned["path"]))
                except KeyError as exc:
                    raise InstallError(f"{tool['name']} : {pinned['path']} absent de l'archive") from exc
                source = tar.extractfile(member) if member.isfile() else None
                if source is None:
                    raise InstallError(f"{tool['name']} : {pinned['path']} n'est pas un fichier")
                (staged / name).write_bytes(source.read())
    except tarfile.TarError as exc:
        raise InstallError(f"{archive.name} : archive refusée ({exc})") from exc
    for name, pinned in dict(tool["files"]).items():
        found = sha256_file(staged / name)
        if found != pinned["sha256"]:
            raise InstallError(f"{tool['name']} : {name} d'empreinte {found} au lieu de {pinned['sha256']}")
    swap_in(staged, final)


def install_docker_image(tool: lockfile.Tool) -> None:
    image = str(tool["image"])
    pinned = f"{doctor.image_repository(image)}@sha256:{tool['sha256']}"
    run_step(["docker", "pull", pinned], os.environ, Path.cwd(), "docker pull")
    run_step(["docker", "tag", pinned, image], os.environ, Path.cwd(), "docker tag")


def build_command(tool: lockfile.Tool, repo_root: Path, archive: Path) -> list[str]:
    """docker buildx build with the pinned arguments, exported as an OCI archive with clamped timestamps and without
    attestations, so the same build folder gives the same image digest."""
    args = [item for key, value in dict(tool["build_args"]).items() for item in ("--build-arg", f"{key}={value}")]
    return [
        "docker",
        "buildx",
        "build",
        "--platform",
        "linux/amd64",
        "--provenance=false",
        "--sbom=false",
        *args,
        "--output",
        f"type=oci,dest={archive},name={tool['image']},rewrite-timestamp=true",
        "-f",
        str(repo_root / str(tool["dockerfile"])),
        str(repo_root / str(tool["context"])),
    ]


def install_docker_build(tool: lockfile.Tool, repo_root: Path, scratch: Path) -> None:
    """Build the image from the pinned folder, load it, and refuse it unless its digest is the pinned one."""
    context = repo_root / str(tool["context"])
    found = tree_sha256(context)
    if found != tool["context_sha256"]:
        pinned = tool["context_sha256"]
        raise InstallError(f"{tool['name']} : {tool['context']} d'empreinte {found} au lieu de {pinned}")
    archive = scratch / "image.oci.tar"
    run_step(build_command(tool, repo_root, archive), os.environ, scratch, "docker buildx build")
    run_step(["docker", "load", "-i", str(archive)], os.environ, scratch, "docker load")
    done = doctor.run_command(["docker", "image", "inspect", "--format", "{{.Id}}", str(tool["image"])])
    if done.output.strip() not in doctor.built_image_ids(tool):
        raise InstallError(
            f"{tool['name']} : image construite d'identifiant {done.output.strip()} au lieu de sha256:{tool['sha256']}"
        )


def install_tool(
    tool: lockfile.Tool, lock: Mapping[str, object], places: Places, repo_root: Path, opener: Opener = open_url
) -> None:
    kind = tool["kind"]
    if kind == "docker-image":
        install_docker_image(tool)
        return
    if kind == "docker-build":
        with workspace(places.tools, str(tool["name"])) as scratch:
            install_docker_build(tool, repo_root, scratch)
        return
    final = lockfile.tool_dir(places.tools, tool)
    try:
        with workspace(places.tools, str(tool["name"])) as scratch:
            if kind == "archive":
                install_archive(tool, final, scratch, opener)
            elif kind == "file":
                install_file(tool, final, scratch, opener)
            elif kind == "source-build":
                install_source_build(tool, lock, places, final, scratch, opener)
            elif kind == "library":
                install_library(tool, final, scratch, opener)
            else:
                install_npm(tool, lock, places, final, scratch, opener, repo_root)
    except OSError as exc:
        raise InstallError(f"{tool['name']} : {exc}") from exc


def install(
    lock: Mapping[str, object],
    names: list[str],
    places: Places,
    repo_root: Path,
    check: Callable[[lockfile.Tool], list[doctor.Problem]],
    opener: Opener = open_url,
) -> list[str]:
    """Install the named tools (all of them when names is empty) and what they require, skipping those already in
    place; returns the names installed. A failure stops at the first tool that cannot be installed."""
    order = lockfile.requirement_order(lock, names or [str(tool["name"]) for tool in lock["tools"]])
    tools = lockfile.by_name(lock)
    done = []
    for name in order:
        if not check(tools[name]):
            print(f"ok     {name} {tools[name]['version']} : déjà en place", flush=True)
            continue
        print(f"…      {name} {tools[name]['version']} : installation", flush=True)
        install_tool(tools[name], lock, places, repo_root, opener)
        done.append(name)
    return done


def main_install(
    lock: Mapping[str, object],
    names: list[str],
    places: Places,
    repo_root: Path,
    check: Callable[[lockfile.Tool], list[doctor.Problem]],
) -> int:
    try:
        install(lock, names, places, repo_root, check)
    except (InstallError, lockfile.LockError) as exc:
        print(f"vf doctor --install : {exc}", file=sys.stderr)
        return 1
    return 0
