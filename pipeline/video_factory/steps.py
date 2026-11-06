"""The eight steps of the chain, each as three functions: its inputs (name → fingerprint), its parameters, and its run.

A run works in a scratch folder of the media store and returns the files it made (stored by the chain under their
fingerprints) and a summary of what it measured. Every external program is a pinned tool of the lock.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from video_factory import (
    align,
    captures,
    compose,
    cut,
    ingest,
    master,
    media,
    montage,
    music,
    qc,
    script,
    transcribe,
    vitrine,
    voice,
)
from video_factory.context import StepError, Video
from video_factory.tools import ToolError


@dataclass
class Result:
    outputs: dict[str, tuple[Path, str]] = field(default_factory=dict)  # name → (file or folder, extension)
    summary: dict = field(default_factory=dict)


def write_json(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def is_vitrine(video: Video) -> bool:
    """Whether the video is a showcase (« genre: vitrine »): its voice is a file of its own, its shots are captures."""
    try:
        return script.genre_of(video.script_text()) == script.VITRINE
    except ValueError as exc:
        raise StepError(f"script.md : {exc}") from exc


def parsed_vitrine(video: Video) -> vitrine.Vitrine:
    try:
        return vitrine.parse(video.script_text())
    except ValueError as exc:
        raise StepError(f"script.md : {exc}") from exc


def showcase_captures(video: Video) -> dict[str, dict]:
    """The registered captures a showcase shows (its shots and its icon); one it names but lacks stops the step."""
    registered = video.state["captures"]
    names = montage.used_captures(parsed_vitrine(video))
    missing = [name for name in names if name not in registered]
    if missing:
        raise StepError(f"capture absente : {', '.join(missing)} : vf ingest {video.id} --capture <nom> <fichier>")
    return {name: registered[name] for name in names}


def parsed_script(video: Video) -> script.Script:
    try:
        return script.parse(video.script_text())
    except (script.ScriptError, ValueError) as exc:
        raise StepError(f"script.md : {exc}") from exc


# --- ingest ---------------------------------------------------------------------------------------------------------


def ingest_inputs(video: Video) -> dict[str, str]:
    if is_vitrine(video):
        if "voix" not in video.state:
            raise StepError(f"aucune voix : vf ingest {video.id} --voix <fichier>")
        return {"voix": video.state["voix"]["sha256"]}
    if not video.state["takes"]:
        raise StepError(f"aucune prise : vf ingest {video.id} <fichiers>")
    return {f"take-{index}": take["sha256"] for index, take in enumerate(video.state["takes"], 1)}


def ingest_params(_video: Video) -> dict:
    return {"fps": media.FPS, "sample_rate": media.SAMPLE_RATE, "crf": ingest.CRF}


def ingest_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    if is_vitrine(video):
        work = scratch / "work.wav"
        try:
            voice = video.media / video.state["voix"]["file"]
            described = ingest.make_voice_copy(tools.ffmpeg, tools.ffprobe, voice, work)
        except ingest.IngestError as exc:
            raise StepError(str(exc)) from exc
        report = write_json(scratch / "probe.json", described)
        return Result({"work": (work, "wav"), "probe": (report, "json")}, {"duration": described["work"]["duration"]})
    takes = [video.media / take["file"] for take in video.state["takes"]]
    work = scratch / "work.mkv"
    try:
        described = ingest.make_working_copy(tools.ffmpeg, tools.ffprobe, takes, work)
    except ingest.IngestError as exc:
        raise StepError(str(exc)) from exc
    report = write_json(scratch / "probe.json", described)
    return Result({"work": (work, "mkv"), "probe": (report, "json")}, {"duration": described["work"]["duration"]})


def work_input(video: Video) -> dict[str, str]:
    return {"work": video.output_ref("ingest", "work")["sha256"]}


# --- transcribe -----------------------------------------------------------------------------------------------------


def transcribe_params(_video: Video) -> dict:
    return {
        "language": transcribe.LANGUAGE,
        "temperature": 0,
        "fallback": False,
        "beam": transcribe.BEAM,
        "threads": transcribe.THREADS,
        "dtw": transcribe.DTW_PRESET,
        "prompt": transcribe.PROMPT,
        "silence_db": transcribe.SILENCE_DB,
        "silence_min": transcribe.SILENCE_MIN,
    }


def transcribe_run(video: Video, scratch: Path, runner: transcribe.Runner = transcribe.run_whisper) -> Result:
    tools = video.toolbox
    audio = scratch / "audio16k.wav"
    media.ffmpeg(tools.ffmpeg, transcribe.audio_command(video.output("ingest", "work"), audio), "transcribe, son")
    base = scratch / "whisper"
    runner(transcribe.whisper_command(tools.whisper_cli, tools.model("whisper-large-v3-turbo"), audio, base))
    duration = float(media.probe(tools.ffprobe, audio)["format"]["duration"])
    silent = transcribe.silences(tools.ffmpeg, audio, duration)
    document = transcribe.transcript(transcribe.read_json(base.with_suffix(".json")), silent, duration)
    summary = {"words": len(document["words"]), "silences": len(document["silences"]), "duration": duration}
    return Result({"transcript": (write_json(scratch / "transcript.json", document), "json")}, summary)


# --- align ----------------------------------------------------------------------------------------------------------


def align_inputs(video: Video) -> dict[str, str]:
    return {"transcript": video.output_ref("transcribe", "transcript")["sha256"], "script": video.script_sha256()}


def align_params(_video: Video) -> dict:
    return {
        "costs": {
            "near": align.NEAR,
            "substitute": align.SUBSTITUTE,
            "insert": align.INSERT,
            "insert_filler": align.INSERT_FILLER,
            "delete": align.DELETE,
            "restart": align.RESTART,
            "abandon": align.ABANDON,
        },
        "fillers": [" ".join(phrase) for phrase in align.FILLERS],
        "pieces": list(align.PIECES),
    }


def align_run(video: Video, scratch: Path) -> Result:
    document = align.align(video.output_json("transcribe", "transcript")["words"], parsed_script(video))
    counts: dict[str, int] = {}
    for word in document["words"]:
        counts[word["label"]] = counts.get(word["label"], 0) + 1
    summary = {"labels": counts, "missing": len(document["missing"])}
    return Result({"alignment": (write_json(scratch / "alignment.json", document), "json")}, summary)


# --- cut ------------------------------------------------------------------------------------------------------------


def cut_inputs(video: Video) -> dict[str, str]:
    found = {"alignment": video.output_ref("align", "alignment")["sha256"]}
    if not is_vitrine(video):
        return found
    # A showcase's decision list also reads the silences of the voice, the lines of its script and its captures.
    shown = {f"capture:{name}": capture["sha256"] for name, capture in showcase_captures(video).items()}
    return (
        found
        | {
            "transcript": video.output_ref("transcribe", "transcript")["sha256"],
            "script": video.script_sha256(),
        }
        | shown
    )


def cut_params(video: Video) -> dict:
    if is_vitrine(video):
        return {
            "pad": [montage.PAD_IN, montage.PAD_OUT],
            "captions": {
                "words": montage.CAPTION_WORDS,
                "pause": montage.CAPTION_PAUSE,
                "hold": montage.CAPTION_HOLD,
                "short_word": montage.SHORT_WORD,
                "whole_line": montage.WHOLE_LINE,
            },
            "fps": montage.FPS,
        }
    return {"max_silence": cut.MAX_SILENCE, "kept_silence": cut.KEPT_SILENCE, "sample_rate": cut.SAMPLE_RATE}


def capture_lengths(video: Video, shown: dict[str, dict], showcase: vitrine.Vitrine) -> dict[str, float]:
    """The length in seconds of each capture a shot runs to the end of (a piece without « durée »)."""
    open_ended = {piece.capture for line in showcase.lines for piece in line.pieces if piece.length is None}
    found = {}
    for name in sorted(open_ended):
        probed = media.probe(video.toolbox.ffprobe, video.media / shown[name]["file"])
        found[name] = media.summary(probed)["duration"]
    return found


def showcase_cut_run(video: Video, scratch: Path) -> Result:
    showcase = parsed_vitrine(video)
    shown = showcase_captures(video)
    transcript = video.output_json("transcribe", "transcript")
    words = video.output_json("align", "alignment")["script_words"]
    try:
        lengths = capture_lengths(video, shown, showcase)
        edl = montage.decide(showcase, words, transcript["silences"], transcript["duration"], lengths)
    except (montage.MontageError, media.MediaError) as exc:
        raise StepError(str(exc)) from exc
    summary = {
        "shots": len(edl["shots"]),
        "lines": len(edl["spoken"]),
        "caption_groups": len(edl["groups"]),
        "duration": edl["duration"],
    }
    return Result({"edl": (write_json(scratch / "edl.json", edl), "json")}, summary)


def cut_run(video: Video, scratch: Path) -> Result:
    if is_vitrine(video):
        return showcase_cut_run(video, scratch)
    words = video.output_json("align", "alignment")["words"]
    duration = video.record("ingest")["summary"]["duration"]
    try:
        edl = cut.decide(words, duration)
    except cut.CutError as exc:
        raise StepError(str(exc)) from exc
    off_script = [word["text"] for word in edl["words"] if word["label"] == align.OFF_SCRIPT]
    summary = {"segments": len(edl["segments"]), "duration": edl["duration"], "off_script_kept": off_script}
    return Result({"edl": (write_json(scratch / "edl.json", edl), "json")}, summary)


# --- voice ----------------------------------------------------------------------------------------------------------


def voice_inputs(video: Video) -> dict[str, str]:
    return work_input(video) | {"edl": video.output_ref("cut", "edl")["sha256"]}


def voice_params(video: Video) -> dict:
    loudness = {"lufs": voice.TARGET_LUFS, "true_peak": voice.TARGET_PEAK, "lra": voice.TARGET_LRA, "fade": voice.FADE}
    if is_vitrine(video):
        # A showcase's voice is used as delivered: placed line by line, then brought to the loudness of every video.
        return loudness | {"pad": [montage.PAD_IN, montage.PAD_OUT]}
    return {"clean": voice.CLEAN, "helmet": voice.HELMET} | loudness


def voice_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    edl = video.output_json("cut", "edl")
    coloured, output = scratch / "coloured.wav", scratch / "voice.wav"
    if is_vitrine(video):
        try:
            command = montage.voice_command(video.output("ingest", "work"), edl["spoken"], edl["duration"], coloured)
        except montage.MontageError as exc:
            raise StepError(str(exc)) from exc
        media.ffmpeg(tools.ffmpeg, command, "voice, répliques placées")
    else:
        command = voice.coloured_command(video.output("ingest", "work"), edl["segments"], coloured)
        media.ffmpeg(tools.ffmpeg, command, "voice, chaîne")
    measured = voice.measure(tools.ffmpeg, coloured)
    applied = voice.normalize(tools.ffmpeg, coloured, measured, output)
    summary = {
        "measured_lufs": float(measured["input_i"]),
        "output_lufs": float(applied["output_i"]),
        "output_true_peak": float(applied["output_tp"]),
        "mode": applied.get("normalization_type"),
    }
    return Result({"voice": (output, "wav")}, summary)


# --- compose --------------------------------------------------------------------------------------------------------


def used_captures(video: Video) -> list[str]:
    return sorted({shot.content for shot in parsed_script(video).shots if shot.kind == "capture"})


def compose_inputs(video: Video) -> dict[str, str]:
    if is_vitrine(video):
        shown = {f"capture:{name}": capture["sha256"] for name, capture in showcase_captures(video).items()}
        return {"edl": video.output_ref("cut", "edl")["sha256"], "script": video.script_sha256()} | shown
    found = {
        "camera": video.output_ref("ingest", "work")["sha256"],
        "edl": video.output_ref("cut", "edl")["sha256"],
        "script": video.script_sha256(),
    }
    registered = video.state["captures"]
    used = [name for name in used_captures(video) if name in registered]
    return found | {f"capture:{name}": registered[name]["sha256"] for name in used}


def compose_params(video: Video) -> dict:
    if is_vitrine(video):
        return {
            "size": [compose.WIDTH, compose.HEIGHT],
            "fps": compose.FPS,
            "safe": compose.SAFE,
            "twin_margin": montage.TWIN_MARGIN,
            "workers": compose.WORKERS,
            "image": video.toolbox.entry("hyperframes-render")["sha256"],
            "libraries": {name: video.toolbox.entry(name)["files"] for name in video.toolbox.libraries()},
        }
    return {
        "size": [compose.WIDTH, compose.HEIGHT],
        "fps": compose.FPS,
        "safe": compose.SAFE,
        "caption": compose.CAPTION,
        "caption_size": compose.CAPTION_SIZE,
        "groups": {"words": compose.GROUP_WORDS, "pause": compose.GROUP_PAUSE},
        "shot": compose.SHOT,
        "shot_sizes": compose.SHOT_SIZES,
        "workers": compose.WORKERS,
        "image": video.toolbox.entry("hyperframes-render")["sha256"],
        "libraries": {name: video.toolbox.entry(name)["files"] for name in video.toolbox.libraries()},
        "music": {"seed": music.SEED, "tempo": music.TEMPO, "rms_dbfs": music.RMS_DBFS},
    }


def render_image(video: Video) -> str:
    """The id of the pinned render image, checked before it runs."""
    tool = video.toolbox.entry("hyperframes-render")
    done = media.run(["docker", "image", "inspect", "--format", "{{.Id}}", str(tool["image"])], "docker")
    found = done.stdout.decode().strip()
    accepted = {f"sha256:{tool['sha256']}", f"sha256:{tool['config_sha256']}"}
    if found not in accepted:
        raise StepError(f"{tool['image']} n'est pas l'image figée : uv run vf doctor --install hyperframes-render")
    return found


def check_and_render(
    video: Video, project: Path, text_root: Path, frames: int, scratch: Path
) -> tuple[Path, list, dict]:
    """hyperframes check on the project, then the render of its frames and of its text pass: the frames folder, the
    text runs and what was measured."""
    tools = video.toolbox
    video_pass, text_pass, work = scratch / "video", scratch / "texte", scratch / "work"
    for folder in (video_pass, text_pass, work):
        folder.mkdir(exist_ok=True)
    outside = compose.outside_references(project) + [f"absent : {name}" for name in compose.missing_files(project)]
    if outside:
        raise StepError("le projet ne doit charger que ses propres fichiers :\n" + "\n".join(f"- {o}" for o in outside))
    image = render_image(video)
    environment = dict(tools.entry("hyperframes")["env"])
    started = time.monotonic()
    try:
        report = compose.check_project(compose.check_command(image, environment, project, work))
    except compose.ComposeError as exc:
        raise StepError(str(exc)) from exc
    measured = {"check": {"seconds": round(time.monotonic() - started, 1), "warnings": compose.check_warnings(report)}}
    rendering = {}
    for name, root, output in (("video", None, video_pass), ("texte", text_root, text_pass)):
        started = time.monotonic()
        try:
            media.run(compose.render_command(image, environment, project, output, work, root), f"rendu {name}")
        except media.MediaError as exc:
            raise StepError(str(exc)) from exc
        rendering[name] = round(time.monotonic() - started, 1)
    try:
        found = compose.rendered(video_pass, frames)
        text = compose.text_runs(tools.ffmpeg, compose.rendered(text_pass, frames))
    except compose.ComposeError as exc:
        raise StepError(str(exc)) from exc
    return found, text, measured | {"render_seconds": rendering}


def showcase_compose_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    showcase = parsed_vitrine(video)
    edl = video.output_json("cut", "edl")
    files = {name: video.media / capture["file"] for name, capture in showcase_captures(video).items()}
    project = scratch / "project"
    try:
        theme = montage.theme_folder(showcase.theme)
        document = montage.write_project(tools.ffmpeg, tools.ffprobe, project, theme, showcase, edl, files)
        libraries = compose.ship_libraries(project, tools)
        text_root = scratch / "texte.html"
        text_root.write_text(montage.text_root(document), encoding="utf-8")
    except (montage.MontageError, compose.ComposeError, ToolError, media.MediaError) as exc:
        raise StepError(str(exc)) from exc
    frames, text, measured = check_and_render(video, project, text_root, edl["frames"], scratch)
    # No music under a showcase for now: a silent track takes its place, so master mixes it like any other.
    bed = scratch / "music.wav"
    music.write(bed, np.zeros((round(edl["duration"] * music.SAMPLE_RATE), 2)))
    plan = {
        "genre": "vitrine",
        "frames": edl["frames"],
        "camera_frames": 0,
        "words": [
            {
                "text": word["text"],
                "start": compose.frame_of(word["start"]),
                "end": max(compose.frame_of(word["start"]) + 1, compose.frame_of(word["end"])),
            }
            for word in edl["words"]
        ],
        "groups": [
            group | {"start": compose.frame_of(group["start"]), "end": compose.frame_of(group["end"])}
            for group in edl["groups"]
        ],
    }
    summary = {
        "frames": edl["frames"],
        "shots": len(edl["shots"]),
        "caption_groups": len(edl["groups"]),
        "theme": showcase.theme,
        "libraries": libraries,
    } | measured
    outputs = {
        "frames": (frames, "frames"),
        "music": (bed, "wav"),
        "plan": (write_json(scratch / "plan.json", plan), "json"),
        "text": (write_json(scratch / "text.json", {"runs": text}), "json"),
    }
    return Result(outputs, summary)


def compose_run(video: Video, scratch: Path) -> Result:
    if is_vitrine(video):
        return showcase_compose_run(video, scratch)
    tools = video.toolbox
    edl = video.output_json("cut", "edl")
    registered = video.state["captures"]
    try:
        plan = compose.plan(edl, parsed_script(video), registered)
    except compose.ComposeError as exc:
        raise StepError(str(exc).replace("<id>", video.id)) from exc
    project = scratch / "project"
    try:
        compose.write_project(project, plan)
        libraries = compose.ship_libraries(project, tools)
    except (compose.ComposeError, ToolError) as exc:
        raise StepError(str(exc)) from exc
    camera = project / "assets" / "camera.mp4"
    compose.camera_track(tools.ffmpeg, tools.ffprobe, video.output("ingest", "work"), edl, camera)
    files = {name: video.media / registered[name]["file"] for name in used_captures(video)}
    compose.place_captures(tools.ffmpeg, project, plan, files)
    text_root = scratch / "texte.html"
    compose.write_text_root(text_root, plan)
    frames, text, measured = check_and_render(video, project, text_root, plan["frames"], scratch)
    bed = scratch / "music.wav"
    music.write(bed, music.bed(plan["frames"] / compose.FPS))
    summary = {
        "frames": plan["frames"],
        "shots": len(plan["shots"]),
        "caption_groups": len(plan["groups"]),
        "camera_share": round(plan["camera_frames"] / plan["frames"], 4),
        "libraries": libraries,
    } | measured
    outputs = {
        "frames": (frames, "frames"),
        "music": (bed, "wav"),
        "plan": (write_json(scratch / "plan.json", plan), "json"),
        "text": (write_json(scratch / "text.json", {"runs": text}), "json"),
    }
    return Result(outputs, summary)


# --- master ---------------------------------------------------------------------------------------------------------


def master_inputs(video: Video) -> dict[str, str]:
    return {
        "frames": video.output_ref("compose", "frames")["sha256"],
        "music": video.output_ref("compose", "music")["sha256"],
        "voice": video.output_ref("voice", "voice")["sha256"],
    }


def master_params(_video: Video) -> dict:
    return {"sizes": master.SIZES, "crf": master.CRF, "preset": master.PRESET, "gop": master.GOP, "audio": "aac 192k"}


def master_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    plan = video.output_json("compose", "plan")
    frames, voice_file = video.output("compose", "frames"), video.output("voice", "voice")
    music_file = video.output("compose", "music")
    outputs: dict[str, tuple[Path, str]] = {}
    summary = {}
    for name in master.SIZES:
        target = scratch / f"{name}.mp4"
        command = master.command(frames, voice_file, music_file, plan["frames"], name, target)
        media.ffmpeg(tools.ffmpeg, command, f"master {name}")
        digest = scratch / f"{name}.framemd5"
        media.ffmpeg(tools.ffmpeg, master.framemd5_command(target, digest), f"framemd5 {name}")
        outputs[name] = (target, "mp4")
        outputs[f"{name}_framemd5"] = (digest, "framemd5")
        summary[f"{name}_bytes"] = target.stat().st_size
    return Result(outputs, summary)


# --- qc -------------------------------------------------------------------------------------------------------------


def qc_inputs(video: Video) -> dict[str, str]:
    return {
        "master": video.output_ref("master", "master")["sha256"],
        "tiktok": video.output_ref("master", "tiktok")["sha256"],
        "plan": video.output_ref("compose", "plan")["sha256"],
        "text": video.output_ref("compose", "text")["sha256"],
    }


def qc_params(_video: Video) -> dict:
    return {
        "duration": list(qc.DURATION),
        "lufs": qc.LOUDNESS,
        "lufs_tolerance": qc.LOUDNESS_TOLERANCE,
        "true_peak_max": qc.PEAK_MAX,
        "safe": compose.SAFE,
        "camera_share_max": qc.CAMERA_SHARE_MAX,
    }


def qc_facts(video: Video) -> dict:
    tools = video.toolbox
    master_file, tiktok_file = video.output("master", "master"), video.output("master", "tiktok")
    plan = video.output_json("compose", "plan")
    loudness, peak = qc.loudness(tools.ffmpeg, master_file)
    master_facts = qc.stream_facts(tools.ffprobe, master_file)
    return {
        "duration": master_facts["duration"],
        "loudness": loudness,
        "true_peak": peak,
        "master": master_facts,
        "tiktok": qc.stream_facts(tools.ffprobe, tiktok_file),
        "text": video.output_json("compose", "text")["runs"],
        "camera_frames": plan["camera_frames"],
        "frames": plan["frames"],
    }


def qc_run(video: Video, scratch: Path) -> Result:
    facts = qc_facts(video)
    document = qc.report(qc.judge(facts))
    summary = {
        "passed": document["passed"],
        "failed": [check["message"] for check in document["checks"] if not check["ok"]],
        "loudness": facts["loudness"],
        "true_peak": facts["true_peak"],
        "duration": facts["duration"],
    }
    return Result({"report": (write_json(scratch / "qc.json", document), "json")}, summary)


# --- captures -------------------------------------------------------------------------------------------------------


def clean_capture(video: Video, source: Path, scratch: Path) -> tuple[Path, str]:
    try:
        return captures.clean(video.toolbox.ffmpeg, video.toolbox.ffprobe, source, scratch)
    except (captures.CaptureError, media.MediaError) as exc:
        raise StepError(f"capture {source.name} : {exc}") from exc
