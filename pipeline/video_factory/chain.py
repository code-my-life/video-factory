"""The chain of a video: its ten steps in order, when each is stale, and the run that redoes only what must be redone.

A step is up to date when its inputs, parameters, tool versions and code have the fingerprints it recorded, and its
outputs are still in the store. Otherwise it is stale, with the reasons. A step after a stale or missing one is waiting:
it runs again only if its own inputs come out different. `vf run` goes through the steps in order and runs those that
never ran, are stale, or are asked for; each run writes its record into state.json at once.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from video_factory import state as statefile
from video_factory import steps, store
from video_factory.context import StepError, Video
from video_factory.hashing import sha256_bytes, sha256_file
from video_factory.paths import REPO_ROOT
from video_factory.tools import PYTHON_PACKAGES, python_versions

PACKAGE = "pipeline/video_factory"


@dataclass(frozen=True)
class Step:
    name: str
    after: tuple[str, ...]
    tools: tuple[str, ...]
    code: tuple[str, ...]
    inputs: Callable[[Video], dict[str, str]]
    params: Callable[[Video], dict]
    run: Callable[[Video, Path], steps.Result]

    def versions(self, video: Video) -> dict[str, str]:
        return video.toolbox.versions(*self.tools) | python_versions(*PYTHON_PACKAGES)


def modules(*names: str) -> tuple[str, ...]:
    """The sources that make a step's result: its own modules, and steps.py, which runs every step."""
    return tuple(f"{PACKAGE}/{name}.py" for name in (*names, "steps"))


# The project templates and the registry items of compose: every file counts in its fingerprint, except the scene of
# `vf capture` (camera-follow/), which compose never reads.
CAPTURE_SCENE = REPO_ROOT / "templates" / "hyperframes" / "camera-follow"
TEMPLATE = tuple(
    sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "templates" / "hyperframes").rglob("*")
        if path.is_file() and not path.is_relative_to(CAPTURE_SCENE)
    )
)
LIBRARIES = ("gsap", "lottie-web", "dotlottie-web", "animejs", "three")
STEPS = (
    Step(
        "ingest",
        (),
        ("ffmpeg",),
        modules("ingest", "media"),
        steps.ingest_inputs,
        steps.ingest_params,
        steps.ingest_run,
    ),
    Step(
        "transcribe",
        ("ingest",),
        ("ffmpeg", "whisper.cpp", "whisper-large-v3-turbo"),
        modules("transcribe", "media"),
        steps.work_input,
        steps.transcribe_params,
        steps.transcribe_run,
    ),
    Step(
        "align",
        ("transcribe",),
        (),
        modules("align", "script"),
        steps.align_inputs,
        steps.align_params,
        steps.align_run,
    ),
    Step("cut", ("align",), (), modules("cut"), steps.cut_inputs, steps.cut_params, steps.cut_run),
    Step(
        "voice",
        ("ingest", "cut"),
        ("ffmpeg",),
        modules("voice", "media"),
        steps.voice_inputs,
        steps.voice_params,
        steps.voice_run,
    ),
    Step(
        "compose",
        ("ingest", "cut"),
        ("ffmpeg", "hyperframes-render", *LIBRARIES),
        modules("compose", "music", "script", "cut", "media", "tools") + TEMPLATE,
        steps.compose_inputs,
        steps.compose_params,
        steps.compose_run,
    ),
    Step(
        "master",
        ("compose", "voice"),
        ("ffmpeg",),
        modules("master", "media"),
        steps.master_inputs,
        steps.master_params,
        steps.master_run,
    ),
    Step(
        "qc",
        ("master", "compose"),
        ("ffmpeg",),
        modules("qc", "compose", "media"),
        steps.qc_inputs,
        steps.qc_params,
        steps.qc_run,
    ),
)
BY_NAME = {step.name: step for step in STEPS}
UP_TO_DATE, STALE, NEVER, WAITING = "à jour", "périmée", "jamais passée", "en attente"


@dataclass(frozen=True)
class Status:
    step: str
    label: str
    reasons: tuple[str, ...] = ()


def code_fingerprint(step: Step, root: Path = REPO_ROOT) -> str:
    lines = "".join(f"{path}\0{sha256_file(root / path)}\n" for path in sorted(step.code))
    return sha256_bytes(lines.encode())


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def changes(name: str, recorded: dict, current: dict) -> list[str]:
    found = []
    for key in sorted(set(recorded) | set(current)):
        if key not in current:
            found.append(f"{name} « {key} » retiré")
        elif key not in recorded:
            found.append(f"{name} « {key} » ajouté")
        elif recorded[key] != current[key]:
            found.append(f"{name} « {key} » modifié")
    return found


def reasons(video: Video, step: Step) -> list[str] | None:
    """Why a step that ran is stale (empty when up to date); None when it never ran."""
    record = video.state["steps"].get(step.name)
    if record is None:
        return None
    try:
        current = step.inputs(video)
    except StepError as exc:
        return [str(exc)]
    found = changes("entrée", record["inputs"], current)
    if step.params(video) != record["params"]:
        found.append("paramètres modifiés")
    found += changes("outil", record["tools"], step.versions(video))
    if code_fingerprint(step) != record["code"]:
        found.append("code de l'étape modifié")
    for ref in record["outputs"].values():
        why = store.problem(video.media, ref)
        if why:
            found.append(why)
    return found


def status(video: Video) -> list[Status]:
    found: list[Status] = []
    behind: set[str] = set()
    for step in STEPS:
        why = reasons(video, step)
        late = [name for name in step.after if name in behind]
        if why is None:
            found.append(Status(step.name, NEVER if not late else WAITING))
            behind.add(step.name)
        elif why:
            found.append(Status(step.name, STALE, tuple(why)))
            behind.add(step.name)
        elif late:
            found.append(Status(step.name, WAITING, (f"après {', '.join(late)}",)))
            behind.add(step.name)
        else:
            found.append(Status(step.name, UP_TO_DATE))
    return found


def store_outputs(video: Video, result: steps.Result) -> dict[str, dict[str, str]]:
    stored = {}
    for name, (path, ext) in result.outputs.items():
        stored[name] = store.put_tree(video.media, path, ext) if path.is_dir() else store.put(video.media, path, ext)
    return stored


def run_step(video: Video, step: Step, say: Callable[[str], None]) -> dict:
    """Run one step and record it in the state (written at once); return its record."""
    inputs, params = step.inputs(video), step.params(video)
    started, clock = utc_now(), time.monotonic()
    say(f"…      {step.name}")
    with store.scratch(video.media, step.name) as scratch:
        try:
            result = step.run(video, scratch)
            outputs = store_outputs(video, result)
        finally:
            store.writable(scratch)
    record = {
        "inputs": inputs,
        "outputs": outputs,
        "tools": step.versions(video),
        "params": params,
        "code": code_fingerprint(step),
        "summary": result.summary,
        "started_at": started,
        "finished_at": utc_now(),
        "seconds": round(time.monotonic() - clock, 1),
    }
    video.state["steps"][step.name] = record
    video.save()
    say(f"fait   {step.name} en {record['seconds']} s")
    return record


def run(video: Video, again: Sequence[str] = (), say: Callable[[str], None] = print) -> list[str]:
    """Run, in order, the steps that never ran, are stale, or are named in again; return the names run."""
    done = []
    for step in STEPS:
        why = reasons(video, step)
        if why is None or why or step.name in again:
            run_step(video, step, say)
            done.append(step.name)
        else:
            say(f"ok     {step.name}")
    return done


def register_takes(video: Video, files: Sequence[Path]) -> None:
    """Store the takes as shot (copies, the originals stay where they are) and make them the video's takes."""
    for file in files:
        if not file.is_file():
            raise StepError(f"{file} introuvable")
    video.state["takes"] = [store.put(video.media, file, extension(file), keep_source=True) for file in files]
    video.save()


def register_capture(video: Video, name: str, file: Path) -> dict:
    """Clean the capture and record it under name; the given file stays where it is."""
    if not file.is_file():
        raise StepError(f"{file} introuvable")
    source = sha256_file(file)
    with store.scratch(video.media, "capture") as scratch:
        cleaned, kind = steps.clean_capture(video, file, scratch)
        stored = store.put(video.media, cleaned, cleaned.suffix.lstrip("."))
    video.state["captures"][name] = stored | {"kind": kind, "source_sha256": source}
    found = statefile.problems(video.state)
    if found:
        del video.state["captures"][name]
        raise StepError("capture refusée :\n" + "\n".join(found))
    video.save()
    return video.state["captures"][name]


def extension(file: Path) -> str:
    found = file.suffix.lower().lstrip(".")
    return found if found.isalnum() else "bin"
