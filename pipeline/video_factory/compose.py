"""`compose`: the video as a HyperFrames project, checked by `hyperframes check`, rendered frame by frame offline.

The plan comes first, in Python: the face-camera track (the blurred take, cut by the decision list), the
full-frame shots the script notes (« stat », « etapes », « code », and « capture » for a registered still or clip of a
real screen), the word captions and their groups in output time, and the punch-ins. A shot noted at the end of a
sentence covers it; one inside a sentence starts on the word before it; either way it lasts until the next sentence
starts or the next shot does.

Then the project, written from templates/hyperframes/: index.html, the root at 1440x2560 and 30 frames per second, with
the take in a wrapper the punch-ins scale; one scene per shot under compositions/, each a paused GSAP timeline
registered under its id (the « etapes » and « stat » scenes and the captions are registry items, installed as source
and restyled); one captions track; the pinned libraries the scenes load, copied into assets/lib/ from the lock (GSAP
always). No URL of a CDN may remain: the project only loads its own files.

`hyperframes check` must pass before any render. Then HyperFrames renders the project twice in its pinned image,
started here with `docker run --network none` and its telemetry, update checks and installs off: the video pass gives
the PNG frames the master is made of, the text pass (texte.html: the same scenes, only their text, white on black)
gives, frame by frame, the box of everything written on screen, which `qc` holds to the safe zone. The music bed is
synthesized here (`music`). The look is provisional until the video design system.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from itertools import pairwise
from pathlib import Path

import numpy as np

from video_factory import cut, media
from video_factory.paths import HYPERFRAMES_TEMPLATE
from video_factory.script import Script
from video_factory.tools import Toolbox

WIDTH, HEIGHT, FPS = 1440, 2560, 30
# The strictest safe zone of TikTok, YouTube Shorts and Instagram Reels, as shares of the frame.
SAFE = {"top": 0.15, "bottom": 0.35, "left": 0.06, "right": 0.178}
# Where the provisional template writes: captions in a band at the bottom of the safe zone, shots above it.
CAPTION = {"left": 96, "top": 1424, "width": 1078, "height": 220}
SHOT = {"left": 96, "top": 404, "width": 1078, "height": 980}
CAPTION_HOLD = 0.5  # seconds a word stays after it is said, when a pause follows
CAPTION_SIZE = 96  # pixels: the largest caption size, fitted down to 60 % per group
GROUP_WORDS = 3  # words at most in a caption group (high-energy short)
GROUP_PAUSE = 0.15  # seconds of silence that close a caption group
SHOT_SIZES = {"etapes": 84, "code": 72}  # the largest text size of a shot, in pixels
ZOOM_HOLD = 1.0  # seconds a punch-in lasts after its word
WORKERS = 8
CAMERA_CRF = 12
CAMERA_PRESET = "veryfast"
SHOT_KINDS = ("stat", "etapes", "code", "capture")
# The scene template of each kind of shot, under templates/hyperframes/.
SCENES = {
    "etapes": "blocks/mk-specs-list.html",
    "stat": "blocks/mk-progress-stat.html",
    "code": "scenes/code.html",
    "capture": "scenes/capture.html",
}
CAPTIONS_SCENE = "components/caption-highlight.html"
LIBRARY_PATH = re.compile(r"assets/lib/([a-z0-9][a-z0-9.-]*)/")
# Hosts of CDNs and font services: none may appear in a project, which only loads its own files.
CDN_HOSTS = (
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
    "esm.sh",
    "cdn.skypack.dev",
    "jspm.io",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "use.typekit.net",
    "static.heygen.ai",
)
# In a page or a stylesheet, a reference to anything outside the project (absolute or protocol-relative URL).
EXTERNAL_REFERENCE = re.compile(
    r"""(?:\b(?:src|href)\s*=\s*["']|url\(\s*["']?|@import\s+["'])\s*((?:https?:)?//[^"')\s]+)""", re.I
)
TEXT_SUFFIXES = (".html", ".css", ".js", ".mjs", ".json", ".svg")
BT709_INPUT = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]


class ComposeError(Exception):
    """The composition cannot be made: a capture is missing, the project fails its check, or the render failed."""


def safe_box(width: int = WIDTH, height: int = HEIGHT) -> tuple[float, float, float, float]:
    """(left, top, right, bottom) of the safe zone in pixels."""
    return (
        SAFE["left"] * width,
        SAFE["top"] * height,
        width - SAFE["right"] * width,
        height - SAFE["bottom"] * height,
    )


def frame_of(seconds: float) -> int:
    return round(seconds * FPS)


def sentence_starts(edl: dict, script: Script) -> dict[int, float]:
    """The output time at which each sentence's first kept word starts."""
    found: dict[int, float] = {}
    for word in edl["words"]:
        if word["label"] == "kept" and word["script"] is not None:
            sentence = script.words[word["script"]].sentence
            found[sentence] = min(found.get(sentence, math.inf), word["start"])
    return found


def shot_start(edl: dict, script: Script, anchor: int) -> float | None:
    """When a shot noted on word anchor starts: that word, or the next kept word of its sentence."""
    end = script.sentences[script.words[anchor].sentence][1]
    kept = [w for w in edl["words"] if w["label"] == "kept" and w["script"] is not None and anchor <= w["script"] < end]
    return min(w["start"] for w in kept) if kept else None


def plan_shots(edl: dict, script: Script, captures: Mapping[str, dict]) -> list[dict]:
    """The shots in output frames; a capture the video has not registered stops here, before any render."""
    missing = sorted({s.content for s in script.shots if s.kind == "capture" and s.content not in captures})
    if missing:
        names = ", ".join(f"« {name} »" for name in missing)
        raise ComposeError(f"capture absente : {names} ; à verser par vf ingest <id> --capture <nom> <fichier>")
    starts = sentence_starts(edl, script)
    total = edl["frames"]
    found = []
    for shot in script.shots:
        start = shot_start(edl, script, shot.anchor)
        if start is None:
            continue
        sentence = script.words[shot.anchor].sentence
        later = [time for index, time in starts.items() if index > sentence]
        end = min(later) if later else edl["duration"]
        entry = {"kind": shot.kind, "parts": shot.parts(), "start": frame_of(start), "end": min(total, frame_of(end))}
        if shot.kind == "capture":
            entry["capture"] = shot.content
            entry["still"] = captures[shot.content]["kind"] == "image"
        found.append(entry)
    found.sort(key=lambda entry: entry["start"])
    for current, following in pairwise(found):
        current["end"] = min(current["end"], following["start"])
    return [entry for entry in found if entry["end"] > entry["start"]]


def plan_words(edl: dict, script: Script) -> list[dict]:
    """The captions: each said word in its written form (the script's for a kept word), in output frames."""
    words = edl["words"]
    found = []
    for index, word in enumerate(words):
        written = word["label"] == "kept" and word["script"] is not None
        text = script.words[word["script"]].text if written else word["text"]
        following = words[index + 1]["start"] if index + 1 < len(words) else edl["duration"]
        end = min(following, word["end"] + CAPTION_HOLD)
        start_frame = frame_of(word["start"])
        found.append({"text": text, "start": start_frame, "end": max(start_frame + 1, frame_of(end))})
    return found


def plan_groups(edl: dict, script: Script) -> list[dict]:
    """The caption groups: a group closes at a sentence end, before a pause of GROUP_PAUSE or more, or at GROUP_WORDS
    words. It opens on its first word and closes GROUP_HOLD after its last one, or when the next group opens: one
    group is visible at a time. Indices refer to plan_words; times are output frames."""
    words = edl["words"]
    groups: list[dict] = []
    current: list[int] = []

    def sentence(index: int) -> int | None:
        found = words[index]["script"]
        return script.words[found].sentence if found is not None and words[index]["label"] == "kept" else None

    for index, word in enumerate(words):
        current.append(index)
        following = words[index + 1] if index + 1 < len(words) else None
        closes = (
            following is None
            or len(current) == GROUP_WORDS
            or following["start"] - word["end"] >= GROUP_PAUSE
            or (sentence(index) is not None and sentence(index + 1) != sentence(index))
        )
        if closes:
            groups.append({"first": current[0], "last": index})
            current = []
    for position, group in enumerate(groups):
        start = frame_of(words[group["first"]]["start"])
        end = frame_of(words[group["last"]]["end"] + CAPTION_HOLD)
        if position + 1 < len(groups):
            end = min(end, frame_of(words[groups[position + 1]["first"]]["start"]))
        group["start"], group["end"] = start, max(start + 1, min(edl["frames"], end))
    return groups


def plan_zooms(edl: dict, script: Script) -> list[dict]:
    kept = {w["script"]: w for w in edl["words"] if w["label"] == "kept" and w["script"] is not None}
    found = []
    for zoom in script.zooms:
        word = kept.get(zoom.anchor)
        if word is not None:
            end = min(edl["frames"], frame_of(word["end"] + ZOOM_HOLD))
            found.append({"start": frame_of(word["start"]), "end": end})
    return found


def plan(edl: dict, script: Script, captures: Mapping[str, dict]) -> dict:
    """Everything the page draws, in output frames, and the share of the video left to the face camera."""
    shots = plan_shots(edl, script, captures)
    shot_frames = sum(shot["end"] - shot["start"] for shot in shots)
    return {
        "fps": FPS,
        "frames": edl["frames"],
        "width": WIDTH,
        "height": HEIGHT,
        "shots": shots,
        "words": plan_words(edl, script),
        "groups": plan_groups(edl, script),
        "zooms": plan_zooms(edl, script),
        "camera_frames": edl["frames"] - shot_frames,
    }


def seconds(frames: int) -> str:
    """A time in seconds as the project writes it: a whole frame, with six decimals."""
    return f"{frames / FPS:.6f}"


def script_json(document: object) -> str:
    """JSON safe inside a <script> element and a template: no « < » that could close it."""
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def fill(template: str, values: Mapping[str, str]) -> str:
    """The template with each {{NAME}} replaced; a placeholder left over is an error of the template."""
    for name, value in values.items():
        template = template.replace("{{" + name + "}}", value)
    left = re.findall(r"\{\{[A-Z]+\}\}", template)
    if left:
        raise ComposeError(f"gabarit : {', '.join(sorted(set(left)))} sans valeur")
    return template


def box(place: Mapping[str, int]) -> dict:
    return {key: place[key] for key in ("left", "top", "width", "height")}


def stat_config(parts: Sequence[str]) -> dict:
    """A stat's figure and caption: a figure that starts with a whole number counts up to it, the rest is its label."""
    figure = parts[0]
    caption = " ".join(parts[1:])
    match = re.fullmatch(r"(\d{1,9})(?:\s+(.+))?", figure)
    if match:
        return {"value": int(match.group(1)), "figure": figure, "label": match.group(2) or "", "caption": caption}
    return {"value": None, "figure": figure, "label": "", "caption": caption}


def shot_config(shot: dict) -> dict:
    kind = shot["kind"]
    if kind == "etapes":
        return {"rows": [{"label": part} for part in shot["parts"]], "box": box(SHOT), "size": SHOT_SIZES["etapes"]}
    if kind == "stat":
        return stat_config(shot["parts"]) | {"box": box(SHOT)}
    if kind == "code":
        return {"text": " | ".join(shot["parts"]), "box": box(SHOT), "size": SHOT_SIZES["code"]}
    return {"box": box(SHOT), "still": shot["still"]}


def shot_id(index: int) -> str:
    return f"shot-{index}"


def capture_media(index: int, shot: dict) -> str:
    """The media element of a capture scene: a still image, or the clip, timed over the whole shot and silent."""
    element = f"{shot_id(index)}-media"
    if shot["still"]:
        return f'<img id="{element}" src="assets/captures/{index}.png" alt="" />'
    duration = seconds(shot["end"] - shot["start"])
    return (
        f'<video id="{element}" class="clip" src="assets/captures/{index}.mp4" data-start="0" '
        f'data-duration="{duration}" data-track-index="0" muted playsinline></video>'
    )


def scene(template: Path, index: int, shot: dict) -> str:
    values = {
        "ID": shot_id(index),
        "DURATION": seconds(shot["end"] - shot["start"]),
        "CONFIG": script_json(shot_config(shot)),
    }
    if shot["kind"] == "capture":
        values["MEDIA"] = capture_media(index, shot)
    return fill((template / SCENES[shot["kind"]]).read_text("utf-8"), values)


def captions_scene(template: Path, plan_doc: dict) -> str:
    words = [{"text": w["text"], "start": w["start"] / FPS, "end": w["end"] / FPS} for w in plan_doc["words"]]
    groups = [g | {"start": g["start"] / FPS, "end": g["end"] / FPS} for g in plan_doc["groups"]]
    data = {"words": words, "groups": groups, "band": box(CAPTION), "size": CAPTION_SIZE}
    values = {"DURATION": seconds(plan_doc["frames"]), "CONFIG": script_json(data)}
    return fill((template / CAPTIONS_SCENE).read_text("utf-8"), values)


def host(name: str, start: int, end: int, track: int, kind: str, layer: int) -> str:
    """The element of the root that mounts a scene: its id, its composition id and its timeline key are one."""
    return (
        f'      <div id="{name}" data-composition-id="{name}" data-composition-src="compositions/{name}.html" '
        f'data-start="{seconds(start)}" data-duration="{seconds(end - start)}" data-track-index="{track}" '
        f'data-track-kind="{kind}" data-width="{WIDTH}" data-height="{HEIGHT}" style="z-index: {layer}"></div>'
    )


def hosts(plan_doc: dict) -> str:
    rows = [
        host(shot_id(index), shot["start"], shot["end"], 1, "graphics", 2)
        for index, shot in enumerate(plan_doc["shots"])
    ]
    rows.append(host("captions", 0, plan_doc["frames"], 2, "captions", 10))
    return "\n".join(rows)


def root_page(template: str, plan_doc: dict, with_camera: bool) -> str:
    duration = seconds(plan_doc["frames"])
    values = {"DURATION": duration, "HOSTS": hosts(plan_doc)}
    if with_camera:
        values["CAMERA"] = (
            '      <div id="camera-wrap"><video id="camera" class="clip" src="assets/camera.mp4" data-start="0" '
            f'data-duration="{duration}" data-track-index="0" muted playsinline></video></div>'
        )
        zooms = [{"start": zoom["start"] / FPS, "end": zoom["end"] / FPS} for zoom in plan_doc["zooms"]]
        values["ZOOMS"] = script_json(zooms)
    return fill(template, values)


def write_project(folder: Path, plan_doc: dict, template: Path = HYPERFRAMES_TEMPLATE) -> None:
    """The HyperFrames project: index.html (its one root), one scene per shot and the captions under compositions/,
    and the font. The take, the captures and the libraries are placed by the functions below."""
    scenes = folder / "compositions"
    scenes.mkdir(parents=True)
    (folder / "assets" / "captures").mkdir(parents=True)
    (folder / "index.html").write_text(root_page((template / "index.html").read_text("utf-8"), plan_doc, True), "utf-8")
    for index, shot in enumerate(plan_doc["shots"]):
        (scenes / f"{shot_id(index)}.html").write_text(scene(template, index, shot), "utf-8")
    (scenes / "captions.html").write_text(captions_scene(template, plan_doc), "utf-8")
    shutil.copytree(template / "assets" / "fonts", folder / "assets" / "fonts")


def write_text_root(path: Path, plan_doc: dict, template: Path = HYPERFRAMES_TEMPLATE) -> None:
    """The root of the text pass (texte.html), kept out of the project, which has one root: the render mounts it over
    the project's index.html."""
    path.write_text(root_page((template / "texte.html").read_text("utf-8"), plan_doc, False), "utf-8")


def text_files(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if path.is_file() and path.suffix in TEXT_SUFFIXES)


def used_libraries(folder: Path) -> list[str]:
    """The libraries the pages and scenes load from assets/lib/<name>/."""
    found = set()
    for path in folder.rglob("*.html"):
        found.update(LIBRARY_PATH.findall(path.read_text("utf-8")))
    return sorted(found)


def ship_libraries(folder: Path, toolbox: Toolbox) -> list[str]:
    """Copy each library a page loads from its pinned, verified copy (the lock) into assets/lib/<name>/."""
    known = toolbox.libraries()
    names = used_libraries(folder)
    unknown = [name for name in names if name not in known]
    if unknown:
        raise ComposeError(f"bibliothèque hors du lock : {', '.join(unknown)} ; bibliothèques : {', '.join(known)}")
    for name in names:
        target = folder / "assets" / "lib" / name
        target.mkdir(parents=True, exist_ok=True)
        for file, source in toolbox.library(name).items():
            shutil.copyfile(source, target / file)
    return names


def outside_references(folder: Path) -> list[str]:
    """Every URL of a CDN in the project's text files, and every page or stylesheet reference outside the project,
    as « file : url »."""
    found = []
    for path in text_files(folder):
        text = path.read_text("utf-8", errors="replace")
        relative = path.relative_to(folder).as_posix()
        found += [f"{relative} : {host}" for host in CDN_HOSTS if host in text]
        if path.suffix in (".html", ".css"):
            found += [f"{relative} : {url}" for url in EXTERNAL_REFERENCE.findall(text)]
    return found


def missing_files(folder: Path) -> list[str]:
    """Every local file a page or a scene names (src, href, url()) that is not in the project."""
    found = []
    pattern = re.compile(r"""(?:\b(?:src|href)\s*=\s*["']|url\(\s*["']?)([^"')\s:]+\.[a-z0-9]+)["')]""", re.I)
    for path in folder.rglob("*.html"):
        for reference in pattern.findall(path.read_text("utf-8")):
            if not (folder / reference).is_file():
                found.append(f"{path.relative_to(folder).as_posix()} : {reference}")
    return found


Checker = Callable[[list[str]], tuple[int, str]]


def run_checker(argv: list[str]) -> tuple[int, str]:
    """Run hyperframes check and keep its exit code and its standard output (the JSON report)."""
    try:
        done = subprocess.run(argv, capture_output=True, check=False)
    except OSError as exc:
        raise ComposeError(f"check : {argv[0]} ({exc})") from exc
    return done.returncode, done.stdout.decode("utf-8", "replace")


def check_command(image: str, env: Mapping[str, str], project: Path, work: Path) -> list[str]:
    """`hyperframes check --json` on the project, in the pinned render image, without the network."""
    mounts = [f"{project}:/project:ro", f"{work}:/vf-work"]
    return [*container(image, env, mounts, ("--entrypoint", "hyperframes")), "check", "/project", "--json"]


def findings(report: dict) -> list[dict]:
    """Every finding of a `hyperframes check --json` report, with the name of its section."""
    found = []
    for section, value in report.items():
        if isinstance(value, dict):
            found += [item | {"section": section} for item in value.get("findings", []) if isinstance(item, dict)]
    return found


def check_errors(report: dict) -> list[str]:
    """The errors of a check report, each as « section : code : message (file) »."""
    found = []
    for item in findings(report):
        if item.get("severity") == "error":
            where = item.get("sourceFile") or item.get("selector") or ""
            line = f"{item['section']} : {item.get('code', '?')} : {str(item.get('message', '')).strip()}"
            found.append(line + (f" ({where})" if where else ""))
    return found


def check_warnings(report: dict) -> list[str]:
    """The codes of the warnings of a check report, recorded in the step summary."""
    return sorted({str(item.get("code", "?")) for item in findings(report) if item.get("severity") == "warning"})


def check_project(command: list[str], checker: Checker = run_checker) -> dict:
    """Run the check; a report with an error (or no report) stops compose and names each error."""
    code, output = checker(command)
    try:
        report = json.loads(output[output.index("{") :])
    except ValueError as exc:
        raise ComposeError(
            f"hyperframes check n'a pas rendu de rapport (code {code}) : {output.strip()[-400:]}"
        ) from exc
    errors = check_errors(report)
    if errors or report.get("ok") is False or code != 0:
        lines = errors or [f"rapport refusé (ok = {report.get('ok')}, code {code})"]
        raise ComposeError("hyperframes check refuse le projet :\n" + "\n".join(f"- {line}" for line in lines))
    return report


def frame_runs(frames: Sequence[int]) -> list[tuple[int, int]]:
    """(first source frame, count) of each run of consecutive source frames."""
    runs: list[tuple[int, int]] = []
    for frame in frames:
        if runs and frame == runs[-1][0] + runs[-1][1]:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((frame, 1))
    return runs


def encode_args(output: Path) -> list[str | Path]:
    return [
        *media.NO_METADATA,
        *media.BITEXACT,
        "-c:v",
        "libx264",
        "-preset",
        CAMERA_PRESET,
        "-crf",
        str(CAMERA_CRF),
        "-threads",
        str(media.THREADS),
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_range",
        "tv",
        "-an",
        "-f",
        "mp4",
        output,
    ]


def camera_track(ffmpeg: Path, ffprobe: Path, blurred: Path, edl: dict, output: Path) -> None:
    """The face-camera track: for each output frame, the source frame the decision list puts on screen."""
    wanted = cut.source_frames(edl)
    summary = media.summary(media.probe(ffprobe, blurred))
    width, height = summary["width"], summary["height"]
    size = f"{width}x{height}"
    # Raw YUV both ways: the pixels are copied, never converted to RGB and back.
    input_args = ["-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", size, "-r", str(FPS), *BT709_INPUT]
    position = 0
    with media.RawWriter(ffmpeg, input_args, encode_args(output), "compose, piste caméra") as out:
        frames = media.frames(ffmpeg, blurred, width, height, "null", pix_fmt="yuv420p")
        current, index = None, -1
        for target in wanted:
            while index < target:
                current, index = next(frames), index + 1
            out.write(current)
            position += 1
        frames.close()
    if position != edl["frames"]:
        raise ComposeError(f"piste caméra : {position} images au lieu de {edl['frames']}")


def capture_clip(ffmpeg: Path, source: Path, frames: int, output: Path) -> None:
    """A capture clip held on its last frame, or trimmed, to exactly the frames of its shot, without sound."""
    seconds = frames / FPS
    filters = f"fps={FPS},tpad=stop_mode=clone:stop_duration={seconds:.6f},{media.BT709}"
    media.ffmpeg(ffmpeg, ["-i", source, "-vf", filters, "-frames:v", str(frames), *encode_args(output)], "capture")


def place_captures(ffmpeg: Path, folder: Path, plan_doc: dict, files: Mapping[str, Path]) -> None:
    for index, shot in enumerate(plan_doc["shots"]):
        if shot["kind"] != "capture":
            continue
        target = folder / "assets" / "captures" / f"{index}.{'png' if shot['still'] else 'mp4'}"
        if shot["still"]:
            shutil.copyfile(files[shot["capture"]], target)
            target.chmod(0o644)
        else:
            capture_clip(ffmpeg, files[shot["capture"]], shot["end"] - shot["start"], target)


def container(image: str, env: Mapping[str, str], mounts: Sequence[str], entrypoint: Sequence[str] = ()) -> list[str]:
    """docker run of the pinned image, without the network, as the current user, with HyperFrames' variables.

    Nothing heavy is written inside the container: its temporary files and home go to a folder of the media store
    mounted at /vf-work. The container's own disk is Docker Desktop's, on the Windows drive, which a render's gigabytes
    of frames would fill."""
    switches = [item for key, value in sorted(env.items()) for item in ("-e", f"{key}={value}")]
    volumes = [item for mount in mounts for item in ("-v", mount)]
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--platform",
        "linux/amd64",
        "--shm-size=2g",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "HOME=/vf-work",
        "-e",
        "TMPDIR=/vf-work",
        *switches,
        *volumes,
        *entrypoint,
        image,
    ]


def render_command(
    image: str, env: Mapping[str, str], project: Path, output: Path, work: Path, root: Path | None = None
) -> list[str]:
    """HyperFrames rendering the project to PNG frames under /output (no frame cache: the frames it extracts from the
    take go to the render's own folder). With root, that page is mounted over index.html (the text pass)."""
    mounts = [f"{project}:/project:ro", f"{output}:/output", f"{work}:/vf-work"]
    if root is not None:
        mounts.insert(1, f"{root}:/project/index.html:ro")
    return [
        *container(image, env, mounts),
        "/project",
        "--output",
        "/output/frames",
        "--fps",
        str(FPS),
        "--format",
        "png-sequence",
        "--workers",
        str(WORKERS),
        "--no-browser-gpu",
        "--video-frame-format",
        "png",
        "--frames-cache-dir",
        "off",
        "--quiet",
    ]


def rendered(output: Path, frames: int) -> Path:
    """The frames folder of a render, checked to hold exactly the expected frames (frame_000001.png, …)."""
    folder = output / "frames"
    found = sorted(folder.glob("frame_*.png")) if folder.is_dir() else []
    if len(found) != frames:
        raise ComposeError(f"rendu : {len(found)} images au lieu de {frames}")
    return folder


def text_runs(ffmpeg: Path, frames_folder: Path, width: int = WIDTH, height: int = HEIGHT) -> list[list[int]]:
    """From the text pass: for each run of frames with the same text box, [first, last, left, top, right, bottom]
    (right and bottom exclusive, in pixels); frames without text are left out."""
    pattern = frames_folder / "frame_%06d.png"
    runs: list[list[int]] = []
    sequence = ["-framerate", str(FPS), "-start_number", "1"]
    source = media.frames(ffmpeg, pattern, width, height, "null", pix_fmt="gray", input_args=sequence)
    for frame, pixels in enumerate(source):
        rows, cols = np.flatnonzero(pixels.any(axis=1)), np.flatnonzero(pixels.any(axis=0))
        if rows.size == 0:
            continue
        found = [int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1]
        if runs and runs[-1][1] == frame - 1 and runs[-1][2:] == found:
            runs[-1][1] = frame
        else:
            runs.append([frame, frame, *found])
    return runs
