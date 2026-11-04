"""Shared helpers: throwaway git repositories and archives built in the test's temporary directory, the pinned tools,
and synthetic media made with them."""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

import numpy as np
import pytest

GIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


def git(repository: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(repository), **GIT_IDENTITY},
    )
    return done.stdout


@pytest.fixture
def make_repo(tmp_path: Path):
    """A git repository holding the given files ({relative path: bytes}), all added to the index."""

    def build(files: dict[str, bytes], name: str = "repo") -> Path:
        repository = tmp_path / name
        repository.mkdir()
        git(repository, "init", "-q")
        for relative, content in files.items():
            path = repository / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if files:
            git(repository, "add", "--force", "--", *files)
        return repository

    return build


def tar_bytes(members: dict[str, bytes], top: str = "pkg-1.0", pax: dict[str, str] | None = None) -> bytes:
    """A gzipped tar archive whose files sit under one top directory, like a release archive."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT, pax_headers=pax or {}) as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(f"{top}/{name}")
            info.size = len(content)
            info.mode = 0o755
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def pinned_toolbox():
    """The pinned tools as installed on this machine (VF_TOOLS or its default)."""
    from video_factory import lock, paths
    from video_factory.tools import Toolbox

    places = paths.places(os.environ, Path.home())
    return Toolbox(lock.load(paths.LOCK_FILE), places.tools)


@pytest.fixture
def tools():
    """The pinned tools, for the tests that run them. A missing tool skips the test, unless VF_REQUIRE_TOOLS=1 (the
    CI sets it after installing them), where it fails it: a test that needs FFmpeg never passes without it."""
    from video_factory.tools import ToolError

    box = pinned_toolbox()

    def need(*names: str):
        for name in names:
            try:
                box.ffmpeg if name == "ffmpeg" else box.model(name)
            except ToolError as exc:
                if os.environ.get("VF_REQUIRE_TOOLS") == "1":
                    pytest.fail(f"outil figé requis : {exc}")
                pytest.skip(f"outil figé absent : {exc}")
        return box

    return need


def ffmpeg(box, *args: str | Path) -> None:
    """Run the pinned ffmpeg quietly, for building synthetic media in a test's folder."""
    quiet = ["-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    subprocess.run([str(box.ffmpeg), *quiet, *map(str, args)], check=True)


def ellipse(image: np.ndarray, centre: tuple[float, float], radii: tuple[float, float], colour) -> None:
    rows, cols = np.ogrid[: image.shape[0], : image.shape[1]]
    inside = ((rows - centre[0]) / radii[0]) ** 2 + ((cols - centre[1]) / radii[1]) ** 2 <= 1
    image[inside] = colour


def drawn_face(height: int = 256, width: int = 144) -> np.ndarray:
    """A face drawn with ellipses (hair, skin, eyes, brows, nose, mouth), which the face detector takes for one."""
    image = np.full((height, width, 3), (70, 90, 110), np.uint8)
    middle, top = width / 2, height * 0.35
    ellipse(image, (top - 8, middle), (42, 36), (60, 40, 30))
    ellipse(image, (top, middle), (38, 30), (224, 172, 140))
    for side in (-12, 12):
        ellipse(image, (top - 6, middle + side), (5, 8), (255, 255, 255))
        ellipse(image, (top - 6, middle + side), (4, 4), (40, 30, 30))
        ellipse(image, (top - 16, middle + side), (2.5, 9), (70, 50, 40))
    ellipse(image, (top + 6, middle), (8, 4), (200, 140, 110))
    ellipse(image, (top + 20, middle), (4, 12), (150, 60, 60))
    return image


def write_video(box, frames: list[np.ndarray], path: Path, fps: int = 30) -> Path:
    """Encode RGB frames losslessly enough (x264 at CRF 1) into path with the pinned ffmpeg."""
    height, width = frames[0].shape[:2]
    command = [str(box.ffmpeg), "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-f", "rawvideo"]
    command += ["-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
    command += ["-c:v", "libx264", "-crf", "1", "-preset", "ultrafast", "-pix_fmt", "yuv444p", str(path)]
    subprocess.run(command, input=b"".join(frame.tobytes() for frame in frames), check=True)
    return path
