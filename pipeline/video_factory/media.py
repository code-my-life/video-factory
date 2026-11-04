"""FFmpeg and ffprobe as the steps use them: the flags that keep outputs deterministic, probing, and frame streams.

Every command runs the pinned binaries given by the caller. Encoders get fixed thread counts and the « bitexact » flags,
so the same inputs give the same bytes; containers get no metadata. Frames reach Python as raw pixels through a pipe,
never as image files.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

BITEXACT = ["-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact"]
BT709 = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
# No metadata from the inputs, no chapters, and no encoder name on the streams (the muxer keeps only its own name).
NO_METADATA = ["-map_metadata", "-1", "-map_chapters", "-1", "-metadata:s", "encoder="]
# One thread count for every encoder: x264 output depends on it, so it is a parameter, not the machine's core count.
THREADS = 8
FPS = 30
SAMPLE_RATE = 48000


class MediaError(Exception):
    """An FFmpeg or ffprobe command failed; the message carries the end of its output."""


@dataclass(frozen=True)
class Done:
    returncode: int
    stdout: bytes
    stderr: str


def run(argv: Sequence[str | Path], what: str, stdin: bytes | None = None) -> Done:
    """Run a command to completion; a non-zero exit raises MediaError with the last lines of its stderr."""
    command = [str(part) for part in argv]
    try:
        done = subprocess.run(command, input=stdin, capture_output=True, check=False)
    except OSError as exc:
        raise MediaError(f"{what} : {command[0]} ({exc})") from exc
    stderr = done.stderr.decode("utf-8", "replace")
    if done.returncode != 0:
        tail = "\n".join(stderr.strip().splitlines()[-8:])
        raise MediaError(f"{what} : code {done.returncode}\n{tail}")
    return Done(done.returncode, done.stdout, stderr)


def ffmpeg(binary: Path, args: Sequence[str | Path], what: str, loglevel: str = "error") -> str:
    """Run the pinned ffmpeg (no prompt, no stdin, overwrite) and return its stderr, where filters print reports."""
    return run([binary, "-hide_banner", "-nostdin", "-y", "-loglevel", loglevel, *args], what).stderr


def probe(binary: Path, source: Path) -> dict:
    """ffprobe's JSON for a file: format, streams and their side data."""
    done = run(
        [binary, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", source],
        f"ffprobe {source.name}",
    )
    return json.loads(done.stdout)


def rate(text: str | None) -> Fraction | None:
    """« 30000/1001 » as a fraction; None for « 0/0 » or nothing."""
    if not text or text.startswith("0/") or text == "0":
        return None
    return Fraction(text)


def rotation(stream: dict) -> int:
    """The display rotation of a video stream, in degrees, from its display matrix (0 when none)."""
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            return round(float(side["rotation"])) % 360
    return 0


def summary(probed: dict) -> dict:
    """The technical description of a take that the state keeps: never its tags (place, device, date)."""
    streams = probed.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise MediaError("aucune piste vidéo")
    found = {
        "codec": video.get("codec_name", ""),
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "rotation": rotation(video),
        "pix_fmt": video.get("pix_fmt", ""),
        "frame_rate": str(rate(video.get("avg_frame_rate")) or rate(video.get("r_frame_rate")) or ""),
        "color_primaries": video.get("color_primaries", ""),
        "color_transfer": video.get("color_transfer", ""),
        "color_space": video.get("color_space", ""),
        "duration": round(float(probed.get("format", {}).get("duration", 0.0)), 3),
        "audio": None,
    }
    if audio is not None:
        found["audio"] = {"codec": audio.get("codec_name", ""), "sample_rate": int(audio.get("sample_rate", 0))}
    return found


def frame_size(width: int, height: int, pix_fmt: str) -> int:
    return {"rgb24": width * height * 3, "gray": width * height, "yuv420p": width * height * 3 // 2}[pix_fmt]


def frames(
    binary: Path,
    source: Path,
    width: int,
    height: int,
    filters: str,
    pix_fmt: str = "rgb24",
    input_args: Sequence[str] = (),
) -> Iterator[np.ndarray]:
    """Decode every frame of source through filters (which must end at width x height) as arrays of pix_fmt pixels:
    height x width x 3 for rgb24, height x width for gray, the flat planes for yuv420p."""
    size = frame_size(width, height, pix_fmt)
    shape = {"rgb24": (height, width, 3), "gray": (height, width), "yuv420p": (size,)}[pix_fmt]
    command = [
        str(binary),
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        *input_args,
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        f"{filters},format={pix_fmt}",
        "-f",
        "rawvideo",
        "-pix_fmt",
        pix_fmt,
        "pipe:1",
    ]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        assert process.stdout is not None
        while chunk := process.stdout.read(size):
            if len(chunk) != size:
                raise MediaError(f"{source.name} : image tronquée ({len(chunk)} octets au lieu de {size})")
            yield np.frombuffer(chunk, dtype=np.uint8).reshape(shape)
        error = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
        if process.wait() != 0:
            raise MediaError(f"{source.name} : décodage impossible\n{error.strip()}")


class RawWriter:
    """An ffmpeg process that reads raw frames on its stdin and encodes them, as a context manager."""

    def __init__(self, binary: Path, input_args: Sequence[str], output_args: Sequence[str | Path], what: str):
        self.what = what
        command = [str(binary), "-hide_banner", "-nostdin", "-y", "-loglevel", "error", *input_args, "-i", "pipe:0"]
        command += [str(part) for part in output_args]
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def write(self, frame: np.ndarray) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(np.ascontiguousarray(frame).tobytes())

    def __enter__(self) -> RawWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()
        error = self.process.stderr.read().decode("utf-8", "replace") if self.process.stderr else ""
        if self.process.wait() != 0 and exc[0] is None:
            raise MediaError(f"{self.what} : code {self.process.returncode}\n{error.strip()}")


def frame_count(binary: Path, source: Path) -> int:
    """The number of video frames, counted by decoding (exact, whatever the container says)."""
    count = ["-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0"]
    done = run([binary, "-v", "error", *count, source], f"ffprobe {source.name}")
    return int(done.stdout.decode().strip())
