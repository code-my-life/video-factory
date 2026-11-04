"""The studio board through the Hermès CLI (`hermes kanban --board studio …`): the only way the studio touches it.

Every call goes through a runner that the tests replace. No file is shared with Hermès: the CLI is its native
interface, and its JSON output is read, never its database.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from video_factory.studio.stations import Card, Comment, Event

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]
OPEN = ("triage", "todo", "ready", "running", "blocked", "scheduled", "review")
# Variables that would make the CLI act as a worker of another card, or on another board's database.
FOREIGN = ("HERMES_KANBAN_TASK", "HERMES_KANBAN_BOARD", "HERMES_PROFILE")


class BoardError(Exception):
    """The Hermès CLI refused a call or could not be run."""


def run_command(argv: Sequence[str]) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if key not in FOREIGN}
    try:
        return subprocess.run(list(argv), capture_output=True, text=True, timeout=180, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BoardError(f"{argv[0]} : {exc}") from exc


def card_of(shown: dict) -> Card:
    task = shown["task"]
    return Card(
        id=task["id"],
        title=task.get("title") or "",
        status=task.get("status") or "",
        assignee=task.get("assignee"),
        events=tuple(
            Event(item.get("kind") or "", item.get("payload") or {}, int(item.get("created_at") or 0))
            for item in shown.get("events", [])
        ),
        comments=tuple(
            Comment(item.get("author") or "", item.get("body") or "", int(item.get("created_at") or 0))
            for item in shown.get("comments", [])
        ),
    )


@dataclass
class Board:
    slug: str = "studio"
    hermes: str = "hermes"
    run: Runner = run_command
    author: str = "studio"

    def call(self, *args: str) -> str:
        done = self.run([self.hermes, "kanban", "--board", self.slug, *args])
        if done.returncode != 0:
            why = (done.stderr or done.stdout or "").strip()[-400:]
            raise BoardError(f"hermes kanban {args[0]} refusé ({done.returncode}) : {why}")
        return done.stdout

    def listing(self) -> list[dict]:
        found = json.loads(self.call("list", "--json") or "[]")
        return [task for task in found if task.get("status") in (*OPEN, "done")]

    def card(self, card_id: str) -> Card:
        return card_of(json.loads(self.call("show", card_id, "--json")))

    def create(self, title: str, lane: str, body: str, key: str) -> str:
        made = json.loads(
            self.call(
                "create",
                title,
                "--assignee",
                lane,
                "--body",
                body,
                "--created-by",
                self.author,
                "--idempotency-key",
                key,
                "--json",
            )
        )
        return made["id"]

    def assign(self, card_id: str, lane: str) -> None:
        self.call("assign", card_id, lane)

    def schedule(self, card_id: str, reason: str) -> None:
        self.call("schedule", card_id, reason)

    def unblock(self, card_id: str, reason: str = "") -> None:
        self.call("unblock", card_id, *(("--reason", reason) if reason else ()))

    def claim(self, card_id: str, ttl: int) -> None:
        self.call("claim", card_id, "--ttl", str(ttl))

    def comment(self, card_id: str, text: str) -> None:
        self.call("comment", card_id, "--author", self.author, text)

    def complete(self, card_id: str, result: str) -> None:
        self.call("complete", card_id, "--result", result)
