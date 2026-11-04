"""`compose`: the video as HyperFrames draws it, frame by frame, without the network.

The plan comes first, in Python: the face-camera track (the blurred take, cut by the decision list), the
full-frame shots the script notes (« stat », « etapes », « code », and « capture » for a registered still or clip of a
real screen), the word captions in output time, and the punch-ins. A shot noted at the end of a sentence covers it; one
inside a sentence starts on the word before it; either way it lasts until the next sentence starts or the next shot
does.

Then HyperFrames renders the page twice in its pinned image, started here with `docker run --network none` and its
telemetry, update checks and installs off: the video pass gives the PNG frames the master is made of, the text pass
(only the text, white on black) gives, frame by frame, the box of everything written on screen, which `qc` holds to the
safe zone. The music bed is synthesized here (`music`). The template is provisional (templates/composition/).
"""

from __future__ import annotations

import json
import math
import os
import shutil
from collections.abc import Mapping, Sequence
from itertools import pairwise
from pathlib import Path

import numpy as np

from video_factory import cut, media
from video_factory.paths import COMPOSITION_TEMPLATE
from video_factory.script import Script

WIDTH, HEIGHT, FPS = 1440, 2560, 30
# The strictest safe zone of TikTok, YouTube Shorts and Instagram Reels, as shares of the frame.
SAFE = {"top": 0.15, "bottom": 0.35, "left": 0.06, "right": 0.178}
# Where the provisional template writes: captions in a band at the bottom of the safe zone, shots above it.
CAPTION = {"left": 96, "top": 1424, "width": 1078, "height": 220}
SHOT = {"left": 96, "top": 404, "width": 1078, "height": 980}
CAPTION_HOLD = 0.5  # seconds a word stays after it is said, when a pause follows
ZOOM_HOLD = 1.0  # seconds a punch-in lasts after its word
WORKERS = 8
CAMERA_CRF = 12
CAMERA_PRESET = "veryfast"
SHOT_KINDS = ("stat", "etapes", "code", "capture")
BT709_INPUT = ["-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]


class ComposeError(Exception):
    """The composition cannot be made: a capture is missing, or the render failed."""


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
        "zooms": plan_zooms(edl, script),
        "camera_frames": edl["frames"] - shot_frames,
    }


def page_data(plan_doc: dict) -> dict:
    return {
        "fps": plan_doc["fps"],
        "width": plan_doc["width"],
        "height": plan_doc["height"],
        "caption": CAPTION,
        "shot": SHOT,
        "words": plan_doc["words"],
        "shots": plan_doc["shots"],
        "zooms": plan_doc["zooms"],
    }


def style(place: Mapping[str, int]) -> str:
    return f"left:{place['left']}px;top:{place['top']}px;width:{place['width']}px;height:{place['height']}px"


def shot_markup(plan_doc: dict, with_media: bool) -> str:
    rows = []
    for index, shot in enumerate(plan_doc["shots"]):
        inner = ""
        if shot["kind"] == "capture" and with_media:
            if shot["still"]:
                inner = f'<img id="capture-{index}" src="assets/captures/{index}.png" alt="" />'
            else:
                start, length = shot["start"] / FPS, (shot["end"] - shot["start"]) / FPS
                inner = (
                    f'<video id="capture-{index}" class="clip" src="assets/captures/{index}.mp4" '
                    f'data-start="{start:.6f}" data-duration="{length:.6f}" muted playsinline></video>'
                )
        rows.append(
            f'      <div class="vf-shot" id="shot-{index}" data-kind="{shot["kind"]}">'
            f'<div class="vf-area" style="{style(SHOT)}">{inner}</div></div>'
        )
    return "\n".join(rows)


def page(template: str, plan_doc: dict, with_media: bool) -> str:
    duration = f"{plan_doc['frames'] / FPS:.6f}"
    camera = ""
    if with_media:
        camera = (
            '      <div id="camera-wrap"><video id="camera" class="clip" src="assets/camera.mp4" data-start="0" '
            f'data-duration="{duration}" muted playsinline></video></div>'
        )
    data = json.dumps(page_data(plan_doc), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return (
        template.replace("{{DURATION}}", duration)
        .replace("{{CAMERA}}", camera)
        .replace("{{SHOTS}}", shot_markup(plan_doc, with_media))
        .replace("{{CAPTION_BOX}}", style(CAPTION))
        .replace("{{DATA}}", data)
    )


def write_project(folder: Path, plan_doc: dict, template: Path = COMPOSITION_TEMPLATE) -> None:
    """The HyperFrames project of both passes: index.html (video), texte.html (text), the script and the font."""
    (folder / "assets" / "captures").mkdir(parents=True, exist_ok=True)
    (folder / "index.html").write_text(page((template / "index.html").read_text("utf-8"), plan_doc, True), "utf-8")
    (folder / "texte.html").write_text(page((template / "texte.html").read_text("utf-8"), plan_doc, False), "utf-8")
    shutil.copyfile(template / "vf-frames.js", folder / "vf-frames.js")
    shutil.copytree(template / "assets" / "fonts", folder / "assets" / "fonts")


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


def render_command(
    image: str, env: Mapping[str, str], project: Path, output: Path, entry: str, work: Path
) -> list[str]:
    """docker run of the pinned image, without the network, as the current user, HyperFrames writing PNG frames.

    Nothing heavy is written inside the container: its temporary files and home go to work, a folder of the media store
    mounted at /vf-work, and the extracted video frames to the render's own folder under /output (no frame cache). The
    container's own disk is Docker Desktop's, on the Windows drive, which a render's gigabytes of frames would fill."""
    switches = [item for key, value in sorted(env.items()) for item in ("-e", f"{key}={value}")]
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
        "-v",
        f"{project}:/project:ro",
        "-v",
        f"{output}:/output",
        "-v",
        f"{work}:/vf-work",
        image,
        "/project",
        "--composition",
        entry,
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
