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

from video_factory.studio.board import BoardError
from video_factory.studio.stations import Card, Comment, Event

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


def write_video(box, frames: list[np.ndarray], path: Path, fps: int = 30) -> Path:
    """Encode RGB frames losslessly enough (x264 at CRF 1) into path with the pinned ffmpeg."""
    height, width = frames[0].shape[:2]
    command = [str(box.ffmpeg), "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-f", "rawvideo"]
    command += ["-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0"]
    command += ["-c:v", "libx264", "-crf", "1", "-preset", "ultrafast", "-pix_fmt", "yuv444p", str(path)]
    subprocess.run(command, input=b"".join(frame.tobytes() for frame in frames), check=True)
    return path


class FakeBoard:
    """The studio board as the Hermès CLI behaves, in memory: statuses, assignments, comments and events, in order.

    Only what the studio calls is kept, with the rules it relies on: a card is created ready, `schedule` parks a ready
    or running card and comments « SCHEDULED: », `unblock` puts a parked card back to ready, a reason being commented
    « UNBLOCK: » first, `claim` runs a ready card, `complete` closes it. A refused call raises, like the CLI.
    """

    slug = "studio"

    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self.calls: list[tuple[str, ...]] = []
        self.clock = 1_000

    def now(self) -> int:
        self.clock += 1
        return self.clock

    def event(self, card_id: str, kind: str, payload: dict | None = None) -> None:
        self.tasks[card_id]["events"].append(Event(kind, payload or {}, self.now()))

    def note(self, card_id: str, body: str) -> None:
        self.tasks[card_id]["comments"].append(Comment("studio", body, self.now()))

    def refuse(self, card_id: str, verb: str, *allowed: str) -> None:
        if card_id not in self.tasks or self.tasks[card_id]["status"] not in allowed:
            raise BoardError(f"hermes kanban {verb} refusé")

    def listing(self) -> list[dict]:
        self.calls.append(("list",))
        return [
            {"id": key, "title": task["title"], "status": task["status"], "assignee": task["assignee"]}
            for key, task in self.tasks.items()
        ]

    def card(self, card_id: str):
        task = self.tasks[card_id]
        return Card(
            card_id, task["title"], task["status"], task["assignee"], tuple(task["events"]), tuple(task["comments"])
        )

    def create(self, title: str, lane: str, body: str, key: str) -> str:
        self.calls.append(("create", title, lane))
        card_id = f"t_{len(self.tasks) + 1:04d}"
        self.tasks[card_id] = {"title": title, "status": "ready", "assignee": lane, "events": [], "comments": []}
        self.event(card_id, "created", {"assignee": lane})
        return card_id

    def assign(self, card_id: str, lane: str) -> None:
        self.calls.append(("assign", card_id, lane))
        self.tasks[card_id]["assignee"] = lane
        self.event(card_id, "assigned", {"assignee": lane})

    def schedule(self, card_id: str, reason: str) -> None:
        self.calls.append(("schedule", card_id, reason))
        self.refuse(card_id, "schedule", "ready", "running", "todo", "blocked")
        self.note(card_id, f"SCHEDULED: {reason}")
        self.tasks[card_id]["status"] = "scheduled"
        self.event(card_id, "scheduled", {"reason": reason})

    def unblock(self, card_id: str, reason: str = "") -> None:
        self.calls.append(("unblock", card_id, reason))
        self.refuse(card_id, "unblock", "scheduled", "blocked")
        if reason:
            self.note(card_id, f"UNBLOCK: {reason}")
        self.tasks[card_id]["status"] = "ready"
        self.event(card_id, "unblocked")

    def claim(self, card_id: str, ttl: int) -> None:
        self.calls.append(("claim", card_id))
        self.refuse(card_id, "claim", "ready")
        self.tasks[card_id]["status"] = "running"
        self.event(card_id, "claimed")

    def comment(self, card_id: str, text: str) -> None:
        self.calls.append(("comment", card_id, text))
        self.note(card_id, text)

    def complete(self, card_id: str, result: str) -> None:
        self.calls.append(("complete", card_id, result))
        self.tasks[card_id]["status"] = "done"
        self.event(card_id, "completed", {"result": result})

    def statuses(self, card_id: str) -> tuple[str, str]:
        task = self.tasks[card_id]
        return task["assignee"], task["status"]


@pytest.fixture
def fake_board() -> FakeBoard:
    return FakeBoard()
