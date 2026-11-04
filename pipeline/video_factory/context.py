"""The video a step works on: its folder in the content clone, its state, its script, the media store and the tools.

Steps read their inputs through this object (the outputs of the steps before them, the script, the takes, the
captures), so they never look up a path themselves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from video_factory import routes, state, store
from video_factory.hashing import sha256_file
from video_factory.paths import ROUTES_FILE, Places
from video_factory.tools import Toolbox
from video_factory.videos import SCRIPT_NAME, STATE_NAME


class StepError(Exception):
    """A step cannot run or failed; the message says why in French."""


@dataclass
class Video:
    id: str
    folder: Path
    state: dict
    places: Places
    toolbox: Toolbox
    routes_file: Path = ROUTES_FILE
    cache: dict = field(default_factory=dict)

    @classmethod
    def open(cls, places: Places, video_id: str, toolbox: Toolbox) -> Video:
        folder = places.content / "videos" / video_id
        if not (folder / STATE_NAME).is_file():
            raise StepError(f"vidéo « {video_id} » introuvable dans {places.content / 'videos'} : vf new {video_id}")
        try:
            loaded = state.load(folder / STATE_NAME)
        except state.StateError as exc:
            raise StepError(str(exc)) from exc
        return cls(video_id, folder, loaded, places, toolbox)

    @property
    def media(self) -> Path:
        return self.places.media

    @property
    def script_path(self) -> Path:
        return self.folder / SCRIPT_NAME

    def script_text(self) -> str:
        return self.script_path.read_text(encoding="utf-8")

    def script_sha256(self) -> str:
        return sha256_file(self.script_path)

    def route(self) -> tuple[str, dict]:
        try:
            loaded = routes.load(self.routes_file)
            return routes.pick(loaded, self.state.get("route"))
        except routes.RouteError as exc:
            raise StepError(str(exc)) from exc

    def record(self, step: str) -> dict:
        found = self.state["steps"].get(step)
        if found is None:
            raise StepError(f"l'étape {step} n'est pas encore passée")
        return found

    def output_ref(self, step: str, name: str) -> dict[str, str]:
        return self.record(step)["outputs"][name]

    def output(self, step: str, name: str) -> Path:
        """The stored output of an earlier step, checked to be in the store."""
        media_ref = self.output_ref(step, name)
        why = store.problem(self.media, media_ref)
        if why:
            raise StepError(f"sortie {name} de {step} : {why}")
        return store.path(self.media, media_ref)

    def output_json(self, step: str, name: str) -> dict:
        key = (step, name, self.output_ref(step, name)["sha256"])
        if key not in self.cache:
            self.cache[key] = json.loads(self.output(step, name).read_text(encoding="utf-8"))
        return self.cache[key]

    def save(self) -> None:
        state.save(self.folder / STATE_NAME, self.state)
