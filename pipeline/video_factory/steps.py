"""The ten steps of the chain, each as three functions: its inputs (name → fingerprint), its parameters, and its run.

A run works in a scratch folder of the media store and returns the files it made (stored by the chain under their
fingerprints) and a summary of what it measured. Every external program is a pinned tool of the lock.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from video_factory import (
    align,
    blur,
    captures,
    compose,
    cut,
    faces,
    ingest,
    master,
    media,
    music,
    qc,
    routes,
    scan,
    script,
    transcribe,
    voice,
)
from video_factory.context import StepError, Video


@dataclass
class Result:
    outputs: dict[str, tuple[Path, str]] = field(default_factory=dict)  # name → (file or folder, extension)
    summary: dict = field(default_factory=dict)


def write_json(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def parsed_script(video: Video) -> script.Script:
    try:
        return script.parse(video.script_text())
    except (script.ScriptError, ValueError) as exc:
        raise StepError(f"script.md : {exc}") from exc


# --- ingest ---------------------------------------------------------------------------------------------------------


def ingest_inputs(video: Video) -> dict[str, str]:
    if not video.state["takes"]:
        raise StepError(f"aucune prise : vf ingest {video.id} <fichiers>")
    _name, route = video.route()
    found = {f"take-{index}": take["sha256"] for index, take in enumerate(video.state["takes"], 1)}
    return found | {"route": routes.fingerprint(route)}


def ingest_params(video: Video) -> dict:
    name, _route = video.route()
    return {"route": name, "fps": media.FPS, "sample_rate": media.SAMPLE_RATE, "crf": ingest.CRF}


def ingest_run(video: Video, scratch: Path) -> Result:
    _name, route = video.route()
    tools = video.toolbox
    takes = [video.media / take["file"] for take in video.state["takes"]]
    work = scratch / "work.mkv"
    try:
        described = ingest.make_working_copy(tools.ffmpeg, tools.ffprobe, takes, route, work)
    except ingest.IngestError as exc:
        raise StepError(str(exc)) from exc
    report = write_json(scratch / "probe.json", described)
    return Result({"work": (work, "mkv"), "probe": (report, "json")}, {"duration": described["work"]["duration"]})


# --- scan -----------------------------------------------------------------------------------------------------------


def work_input(video: Video) -> dict[str, str]:
    return {"work": video.output_ref("ingest", "work")["sha256"]}


def scan_params(_video: Video) -> dict:
    return {"threshold": faces.THRESHOLD, "margin": scan.MARGIN, "size": [faces.WIDTH, faces.HEIGHT]}


def scan_run(video: Video, scratch: Path) -> Result:
    detector = faces.Detector(video.toolbox.model("mediapipe-face-detector"))
    scores = scan.frame_scores(video.toolbox.ffmpeg, video.output("ingest", "work"), detector)
    report = scan.report(scores)
    summary = {"frames": report["frames"], "faces": len(report["faces"]), "ranges": len(report["ranges"])}
    return Result({"faces": (write_json(scratch / "faces.json", report), "json")}, summary)


# --- blur -----------------------------------------------------------------------------------------------------------


def blur_params(_video: Video) -> dict:
    return {"sigma": blur.SIGMA, "mask": blur.MASK_SIZE, "qp": blur.QP, "sample_every": blur.SAMPLE_EVERY}


def blur_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    work = video.output("ingest", "work")
    size = media.summary(media.probe(tools.ffprobe, work))
    mask, output = scratch / "mask.mkv", scratch / "blur.mkv"
    segmenter = blur.Segmenter(tools.model("mediapipe-selfie-segmenter"))
    count = blur.write_masks(tools.ffmpeg, work, segmenter, mask)
    command = blur.composite_command(work, mask, size["width"], size["height"], output)
    media.ffmpeg(tools.ffmpeg, command, "blur")
    drops = blur.measure(tools.ffmpeg, work, output, mask, size["width"], size["height"])
    summary = {"frames": count, "sharpness_drop": drops}
    return Result({"video": (output, "mkv"), "mask": (mask, "mkv")}, summary)


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
    return {
        "alignment": video.output_ref("align", "alignment")["sha256"],
        "faces": video.output_ref("scan", "faces")["sha256"],
    }


def cut_params(_video: Video) -> dict:
    return {"max_silence": cut.MAX_SILENCE, "kept_silence": cut.KEPT_SILENCE, "sample_rate": cut.SAMPLE_RATE}


def cut_run(video: Video, scratch: Path) -> Result:
    words = video.output_json("align", "alignment")["words"]
    ranges = video.output_json("scan", "faces")["ranges"]
    duration = video.record("ingest")["summary"]["duration"]
    try:
        edl = cut.decide(words, ranges, duration)
    except cut.CutError as exc:
        raise StepError(str(exc)) from exc
    off_script = [word["text"] for word in edl["words"] if word["label"] == align.OFF_SCRIPT]
    summary = {"segments": len(edl["segments"]), "duration": edl["duration"], "off_script_kept": off_script}
    return Result({"edl": (write_json(scratch / "edl.json", edl), "json")}, summary)


# --- voice ----------------------------------------------------------------------------------------------------------


def voice_inputs(video: Video) -> dict[str, str]:
    return work_input(video) | {"edl": video.output_ref("cut", "edl")["sha256"]}


def voice_params(_video: Video) -> dict:
    return {
        "clean": voice.CLEAN,
        "helmet": voice.HELMET,
        "lufs": voice.TARGET_LUFS,
        "true_peak": voice.TARGET_PEAK,
        "lra": voice.TARGET_LRA,
        "fade": voice.FADE,
    }


def voice_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    edl = video.output_json("cut", "edl")
    coloured, output = scratch / "coloured.wav", scratch / "voice.wav"
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
    found = {
        "camera": video.output_ref("blur", "video")["sha256"],
        "edl": video.output_ref("cut", "edl")["sha256"],
        "script": video.script_sha256(),
    }
    registered = video.state["captures"]
    used = [name for name in used_captures(video) if name in registered]
    return found | {f"capture:{name}": registered[name]["sha256"] for name in used}


def compose_params(video: Video) -> dict:
    return {
        "size": [compose.WIDTH, compose.HEIGHT],
        "fps": compose.FPS,
        "safe": compose.SAFE,
        "caption": compose.CAPTION,
        "shot": compose.SHOT,
        "workers": compose.WORKERS,
        "image": video.toolbox.entry("hyperframes-render")["sha256"],
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


def compose_run(video: Video, scratch: Path) -> Result:
    tools = video.toolbox
    edl = video.output_json("cut", "edl")
    registered = video.state["captures"]
    try:
        plan = compose.plan(edl, parsed_script(video), registered)
    except compose.ComposeError as exc:
        raise StepError(str(exc).replace("<id>", video.id)) from exc
    project, video_pass, text_pass, work = scratch / "project", scratch / "video", scratch / "texte", scratch / "work"
    for folder in (video_pass, text_pass, work):
        folder.mkdir()
    compose.write_project(project, plan)
    camera = project / "assets" / "camera.mp4"
    compose.camera_track(tools.ffmpeg, tools.ffprobe, video.output("blur", "video"), edl, camera)
    files = {name: video.media / registered[name]["file"] for name in used_captures(video)}
    compose.place_captures(tools.ffmpeg, project, plan, files)
    image = render_image(video)
    environment = dict(tools.entry("hyperframes")["env"])
    rendering = {}
    for name, entry, output in (("video", "index.html", video_pass), ("texte", "texte.html", text_pass)):
        started = time.monotonic()
        try:
            media.run(compose.render_command(image, environment, project, output, entry, work), f"rendu {entry}")
        except media.MediaError as exc:
            raise StepError(str(exc)) from exc
        rendering[name] = round(time.monotonic() - started, 1)
    frames = compose.rendered(video_pass, plan["frames"])
    text = compose.text_runs(tools.ffmpeg, compose.rendered(text_pass, plan["frames"]))
    bed = scratch / "music.wav"
    music.write(bed, music.bed(plan["frames"] / compose.FPS))
    summary = {
        "frames": plan["frames"],
        "shots": len(plan["shots"]),
        "camera_share": round(plan["camera_frames"] / plan["frames"], 4),
        "render_seconds": rendering,
    }
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
        "face_threshold": faces.THRESHOLD,
    }


def qc_facts(video: Video) -> dict:
    tools = video.toolbox
    master_file, tiktok_file = video.output("master", "master"), video.output("master", "tiktok")
    plan = video.output_json("compose", "plan")
    loudness, peak = qc.loudness(tools.ffmpeg, master_file)
    detector = faces.Detector(tools.model("mediapipe-face-detector"))
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
        "faces": qc.detected_faces(tools.ffmpeg, master_file, detector),
    }


def qc_run(video: Video, scratch: Path) -> Result:
    facts = qc_facts(video)
    document = qc.report(qc.judge(facts))
    document["faces"] = facts["faces"]
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
