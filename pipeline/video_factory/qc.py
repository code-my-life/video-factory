"""`qc`: the blocking checks of a master and its TikTok export (criterion C2 of #4). Each failure names its bound.

The facts are measured first (ffprobe, FFmpeg's EBU R 128 meter, the face detector on every frame of the master, the
text boxes the text pass of `compose` found, the plan of `compose`), then judged by pure rules:
- duration within the bounds of « duree_visee » in the script schema (61 to 65 s);
- loudness at -14 LUFS to within 1 LU, true peak at -1 dBTP or below;
- H.264 High, 1440x2560 for the master and 1080x1920 for TikTok, 30 frames per second, constant, BT.709, AAC 48 kHz;
- all text inside the strictest safe zone of the three platforms (15 % at the top, 35 % at the bottom, 6 % on the
  left, 17.8 % on the right);
- face-camera shots on half of the duration at most;
- no frame where the detector finds a face, each one named by its number and time.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from video_factory import compose, faces, media, schemas
from video_factory.paths import SCRIPT_SCHEMA

DURATION = schemas.duration_bounds(SCRIPT_SCHEMA)
LOUDNESS, LOUDNESS_TOLERANCE, PEAK_MAX = -14.0, 1.0, -1.0
CAMERA_SHARE_MAX = 0.5
SIZES = {"master": (1440, 2560), "tiktok": (1080, 1920)}
SHOWN = 10  # frames named in a message before « … »
INTEGRATED = re.compile(r"Integrated loudness:\s*I:\s*(-?[0-9.]+|-inf) LUFS", re.S)
TRUE_PEAK = re.compile(r"True peak:\s*Peak:\s*(-?[0-9.]+|-inf) dBFS", re.S)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str


def number(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def time_of(frame: int, fps: int = compose.FPS) -> str:
    return f"{number(frame / fps)} s"


def frames_named(frames: Sequence[int], fps: int = compose.FPS) -> str:
    shown = ", ".join(f"image {frame} ({time_of(frame, fps)})" for frame in frames[:SHOWN])
    return shown + (f", … ({len(frames)} images)" if len(frames) > SHOWN else "")


def check_duration(seconds: float) -> Check:
    low, high = DURATION
    ok = low <= seconds <= high
    return Check("durée", ok, f"durée : {number(seconds)} s" + ("" if ok else f", hors de {low} à {high} s"))


def check_loudness(integrated: float, peak: float) -> list[Check]:
    loud_ok = abs(integrated - LOUDNESS) <= LOUDNESS_TOLERANCE
    peak_ok = peak <= PEAK_MAX
    return [
        Check(
            "sonie",
            loud_ok,
            f"sonie : {number(integrated, 1)} LUFS" + ("" if loud_ok else ", hors de -14 LUFS à 1 LU près"),
        ),
        Check(
            "crête vraie",
            peak_ok,
            f"crête vraie : {number(peak, 1)} dBTP" + ("" if peak_ok else ", au-dessus de -1 dBTP"),
        ),
    ]


def check_format(name: str, facts: dict) -> Check:
    """H.264 High at the size of its platform, 30 frames per second at a constant rate, BT.709, AAC at 48 kHz."""
    width, height = SIZES[name]
    gaps = []
    if (facts["codec"], facts["profile"]) != ("h264", "High"):
        gaps.append(f"{facts['codec']} {facts['profile']} au lieu de H.264 High")
    if (facts["width"], facts["height"]) != (width, height):
        gaps.append(f"{facts['width']}x{facts['height']} au lieu de {width}x{height}")
    if facts["frame_rate"] != Fraction(30):
        gaps.append(f"{facts['frame_rate']} images par seconde au lieu de 30")
    elif not facts["constant"]:
        gaps.append("cadence variable au lieu de 30 images par seconde constantes")
    colour = (facts["color_primaries"], facts["color_transfer"], facts["color_space"], facts["color_range"])
    if colour != ("bt709", "bt709", "bt709", "tv"):
        gaps.append(f"couleurs {'/'.join(str(value) for value in colour)} au lieu de BT.709")
    if (facts["audio_codec"], facts["sample_rate"]) != ("aac", 48000):
        gaps.append(f"son {facts['audio_codec']} à {facts['sample_rate']} Hz au lieu d'AAC à 48 kHz")
    label = "du master" if name == "master" else "de l'export TikTok"
    message = f"format {label} : " + ("; ".join(gaps) if gaps else f"H.264 High, {width}x{height}, 30 i/s, BT.709")
    return Check(f"format {name}", not gaps, message)


def check_text(runs: Sequence[Sequence[int]], width: int = compose.WIDTH, height: int = compose.HEIGHT) -> Check:
    """Every text box inside the safe zone; the failure names the side crossed and the frames."""
    left, top, right, bottom = compose.safe_box(width, height)
    sides = {
        "15 % en haut": lambda box: box[1] < top,
        "35 % en bas": lambda box: box[3] > bottom,
        "6 % à gauche": lambda box: box[0] < left,
        "17,8 % à droite": lambda box: box[2] > right,
    }
    crossed: dict[str, list[int]] = {}
    for first, last, *box in runs:
        for side, outside in sides.items():
            if outside(box):
                crossed.setdefault(side, []).extend(range(first, last + 1))
    if not crossed:
        return Check("zone sûre", True, "texte : dans la zone sûre")
    parts = [f"{side} : {frames_named(sorted(set(frames)))}" for side, frames in crossed.items()]
    return Check("zone sûre", False, "texte hors de la zone sûre, " + " ; ".join(parts))


def check_camera(camera_frames: int, frames: int) -> Check:
    share = camera_frames / frames if frames else 1.0
    ok = share <= CAMERA_SHARE_MAX
    message = f"plans face caméra : {number(100 * share, 1)} % de la durée"
    return Check("face caméra", ok, message + ("" if ok else ", plus de la moitié"))


def check_faces(found: Sequence[dict], fps: int = compose.FPS) -> Check:
    if not found:
        return Check("visages", True, "visages : aucun")
    frames = [face["frame"] for face in found]
    return Check("visages", False, f"visage détecté : {frames_named(frames, fps)}")


def judge(facts: dict) -> list[Check]:
    """Every check of a master, from its measured facts."""
    return [
        check_duration(facts["duration"]),
        *check_loudness(facts["loudness"], facts["true_peak"]),
        check_format("master", facts["master"]),
        check_format("tiktok", facts["tiktok"]),
        check_text(facts["text"]),
        check_camera(facts["camera_frames"], facts["frames"]),
        check_faces(facts["faces"]),
    ]


def report(checks: Sequence[Check]) -> dict:
    return {
        "passed": all(check.ok for check in checks),
        "checks": [{"name": c.name, "ok": c.ok, "message": c.message} for c in checks],
    }


def stream_facts(ffprobe: Path, source: Path) -> dict:
    """What check_format reads, from ffprobe, the constant rate checked on every video packet."""
    probed = media.probe(ffprobe, source)
    video = next(s for s in probed["streams"] if s["codec_type"] == "video")
    audio = next((s for s in probed["streams"] if s["codec_type"] == "audio"), {})
    packets = ["-select_streams", "v:0", "-show_entries", "packet=duration", "-of", "csv=p=0"]
    durations = media.run([ffprobe, "-v", "error", *packets, source], f"ffprobe {source.name}").stdout.split()
    return {
        "codec": video.get("codec_name"),
        "profile": video.get("profile"),
        "width": video.get("width"),
        "height": video.get("height"),
        "frame_rate": media.rate(video.get("avg_frame_rate")) or Fraction(0),
        "constant": len(set(durations)) == 1 and video.get("r_frame_rate") == video.get("avg_frame_rate"),
        "color_primaries": video.get("color_primaries"),
        "color_transfer": video.get("color_transfer"),
        "color_space": video.get("color_space"),
        "color_range": video.get("color_range"),
        "audio_codec": audio.get("codec_name"),
        "sample_rate": int(audio.get("sample_rate", 0)),
        "duration": float(probed["format"]["duration"]),
    }


def loudness(ffmpeg: Path, source: Path) -> tuple[float, float]:
    """Integrated loudness (LUFS) and true peak (dBTP) of a file's sound, by FFmpeg's EBU R 128 meter."""
    report_text = media.ffmpeg(
        ffmpeg, ["-i", source, "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-"], "sonie", "info"
    )
    integrated, peak = INTEGRATED.findall(report_text), TRUE_PEAK.findall(report_text)
    if not integrated or not peak:
        raise media.MediaError("ebur128 : aucune mesure")
    return float(integrated[-1]), float(peak[-1])


def detected_faces(ffmpeg: Path, source: Path, detector: faces.Detector, threshold: float = faces.THRESHOLD) -> list:
    """Each frame of source where the detector finds a face: number, time, score."""
    scale = f"scale={faces.WIDTH}:{faces.HEIGHT}:flags=area"
    found = []
    for frame, pixels in enumerate(media.frames(ffmpeg, source, faces.WIDTH, faces.HEIGHT, scale)):
        score = detector.score(pixels)
        if score >= threshold:
            found.append({"frame": frame, "time": round(frame / compose.FPS, 3), "score": round(score, 4)})
    return found
