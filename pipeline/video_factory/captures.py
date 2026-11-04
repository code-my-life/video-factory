"""Captures: the stills (PNG) or short silent clips (MP4) of a real screen that a script shows by its
« [capture: <name>] » shots.

`vf ingest <id> --capture <name> <file>` registers one under its name. What is stored is a clean copy made by the
pinned FFmpeg, never the file as given: a still is decoded and written again as an RGB PNG without any chunk of metadata
or colour profile; a clip loses its sound and its metadata and becomes H.264 at 30 frames per second in BT.709. The
state keeps the fingerprint of both the given file and the clean copy.
"""

from __future__ import annotations

from pathlib import Path

from video_factory import ingest, media

STILL_CODECS = frozenset({"png", "mjpeg", "webp", "bmp", "tiff"})
CRF = 12
PRESET = "veryfast"


class CaptureError(Exception):
    """The file is neither a still nor a clip FFmpeg can read."""


def kind_of(probed: dict) -> str:
    """« image » for a single picture, « video » for a clip."""
    video = next((s for s in probed.get("streams", []) if s.get("codec_type") == "video"), None)
    if video is None:
        raise CaptureError("aucune image dans ce fichier")
    single = video.get("codec_name") in STILL_CODECS and int(video.get("nb_frames", 1) or 1) <= 1
    return "image" if single else "video"


def clean_command(source: Path, kind: str, summary: dict, output: Path) -> list[str | Path]:
    """The ffmpeg arguments of the clean copy: PNG for a still, H.264 MP4 without sound for a clip."""
    common = ["-i", source, "-map", "0:v:0", "-an", *media.NO_METADATA, *media.BITEXACT]
    if kind == "image":
        filters = "sidedata=mode=delete:type=ICC_PROFILE,format=rgb24"
        return [*common, "-vf", filters, "-frames:v", "1", "-c:v", "png", "-f", "image2", output]
    filters = f"fps={media.FPS},{ingest.colour_filter(summary)},format=yuv420p,{media.BT709},setsar=1"
    return [
        *common,
        "-vf",
        filters,
        "-c:v",
        "libx264",
        "-preset",
        PRESET,
        "-crf",
        str(CRF),
        "-threads",
        str(media.THREADS),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        output,
    ]


def clean(ffmpeg: Path, ffprobe: Path, source: Path, folder: Path) -> tuple[Path, str]:
    """The clean copy of source in folder, and its kind."""
    probed = media.probe(ffprobe, source)
    kind = kind_of(probed)
    output = folder / ("capture.png" if kind == "image" else "capture.mp4")
    summary = media.summary(probed)
    media.ffmpeg(ffmpeg, clean_command(source, kind, summary, output), f"capture {source.name}")
    return output, kind
