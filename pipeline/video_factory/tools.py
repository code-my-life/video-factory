"""The pinned tools as the steps call them: where each one lives under VF_TOOLS, and the versions a step records.

The lock says what is pinned; `vf doctor` says whether the machine matches it. A step only asks this module for paths,
and a missing tool stops it with the command that installs it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from video_factory import __version__
from video_factory import lock as lockfile

# The Python packages a step's results depend on, recorded with their versions next to the external tools.
PYTHON_PACKAGES = ("ai-edge-litert", "numpy")


class ToolError(Exception):
    """A pinned tool is not installed."""


@dataclass(frozen=True)
class Toolbox:
    """The lock and the folder its tools are installed in."""

    pinned: Mapping[str, object]
    root: Path

    def entry(self, name: str) -> lockfile.Tool:
        return lockfile.by_name(self.pinned)[name]

    def home(self, name: str) -> Path:
        return lockfile.tool_dir(self.root, self.entry(name))

    def file(self, name: str, relative: str) -> Path:
        """A file of an installed tool; a missing one names the command that installs it."""
        found = self.home(name) / relative
        if not found.is_file():
            raise ToolError(f"{name} absent ({found}) : {lockfile.install_command(name)}")
        return found

    @property
    def ffmpeg(self) -> Path:
        return self.file("ffmpeg", "bin/ffmpeg")

    @property
    def ffprobe(self) -> Path:
        return self.file("ffmpeg", "bin/ffprobe")

    @property
    def whisper_cli(self) -> Path:
        return self.file("whisper.cpp", str(self.entry("whisper.cpp")["binary"]))

    def model(self, name: str) -> Path:
        """A model file of the lock (kind « file »)."""
        return self.file(name, str(self.entry(name)["file"]))

    def image(self, name: str) -> str:
        return str(self.entry(name)["image"])

    def versions(self, *names: str) -> dict[str, str]:
        """The versions a step records for the tools it calls: lock entries, then vf and its Python packages."""
        found = {name: str(self.entry(name)["version"]) for name in names}
        found["video-factory"] = __version__
        return found


def python_versions(*packages: str) -> dict[str, str]:
    """« python:<package> » → installed version, for the packages a step's results depend on."""
    return {f"python:{package}": metadata.version(package) for package in packages}
