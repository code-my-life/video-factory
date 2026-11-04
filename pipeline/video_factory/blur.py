"""`blur`: the background of the working copy blurred, the person kept sharp.

Two passes. First the person is cut out on every frame: MediaPipe Selfie Segmenter (the pinned model), on CPU through
LiteRT, writes its confidence mask as a lossless gray video (256x256, FFV1). Then FFmpeg blurs each frame with a
Gaussian of fixed sigma and lays the original back on top through the mask scaled to the frame, so the person (body and
helmet) stays as it was and everything else is blurred. The result is encoded losslessly (x264 at QP 0): the person
loses nothing to a second encoding.

The sharpness of each region is measured by the variance of the Laplacian, before and after, on one frame in
SAMPLE_EVERY: the background must lose at least 90 % of it and the person less than 5 % (criterion C6 of #4).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
from ai_edge_litert.interpreter import Interpreter

from video_factory import media

SIGMA = 18.0  # Gaussian sigma, in pixels of the working copy (1206 px wide)
MASK_SIZE = 256  # the segmenter's input and output size
QP = 0  # lossless
PRESET = "veryfast"
SAMPLE_EVERY = 30  # frames between two sharpness measures
PERSON, BACKGROUND = 0.98, 0.02  # mask levels that count as surely the person, surely the background
EDGE = 8  # pixels taken off each region's border before measuring, away from the soft edge of the mask


class Segmenter:
    """Selfie Segmenter on one CPU thread: a 256x256 RGB frame in, the person's confidence (0 to 1) out."""

    def __init__(self, model: Path):
        self.interpreter = Interpreter(model_path=str(model), num_threads=1)
        self.interpreter.allocate_tensors()
        self.input = self.interpreter.get_input_details()[0]["index"]
        self.output = self.interpreter.get_output_details()[0]["index"]

    def mask(self, frame: np.ndarray) -> np.ndarray:
        tensor = (frame.astype(np.float32) / 255.0)[None]
        self.interpreter.set_tensor(self.input, tensor)
        self.interpreter.invoke()
        return np.clip(self.interpreter.get_tensor(self.output)[0, :, :, 0], 0.0, 1.0)


def write_masks(ffmpeg: Path, video: Path, segmenter: Segmenter, output: Path) -> int:
    """The mask video of every frame of video (frames stretched to 256x256, as the model reads them); returns the
    number of frames."""
    count = 0
    input_args = ["-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{MASK_SIZE}x{MASK_SIZE}", "-r", str(media.FPS)]
    output_args = [*media.NO_METADATA, *media.BITEXACT, "-c:v", "ffv1", "-level", "3", "-g", "1", "-f", "matroska"]
    scale = f"scale={MASK_SIZE}:{MASK_SIZE}:flags=area"
    with media.RawWriter(ffmpeg, input_args, [*output_args, output], "blur, masque") as writer:
        for frame in media.frames(ffmpeg, video, MASK_SIZE, MASK_SIZE, scale):
            writer.write(np.round(segmenter.mask(frame) * 255.0).astype(np.uint8))
            count += 1
    return count


def composite_command(video: Path, mask: Path, width: int, height: int, output: Path) -> list[str | Path]:
    """The ffmpeg arguments that blur video around the person of mask (sound copied as it is)."""
    graph = (
        f"[1:v]scale={width}:{height}:flags=bilinear,format=gray[mask];"
        f"[0:v]split[sharp][soft];[soft]gblur=sigma={SIGMA}[blurred];"
        "[sharp][mask]alphamerge[person];"
        f"[blurred][person]overlay=format=yuv420,format=yuv420p,{media.BT709}[v]"
    )
    return [
        "-i",
        video,
        "-i",
        mask,
        "-filter_complex",
        graph,
        "-map",
        "[v]",
        "-map",
        "0:a:0",
        *media.NO_METADATA,
        *media.BITEXACT,
        "-c:v",
        "libx264",
        "-preset",
        PRESET,
        "-qp",
        str(QP),
        "-threads",
        str(media.THREADS),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-f",
        "matroska",
        output,
    ]


def laplacian(gray: np.ndarray) -> np.ndarray:
    """The 4-neighbour Laplacian of a gray image (its border row and column dropped)."""
    g = gray.astype(np.float32)
    return g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4.0 * g[1:-1, 1:-1]


def erode(region: np.ndarray, radius: int) -> np.ndarray:
    """The pixels of region whose whole (2 radius + 1) square neighbourhood is in region."""
    side = 2 * radius + 1
    padded = np.pad(region.astype(np.int32), radius + 1)
    integral = padded.cumsum(0).cumsum(1)
    window = integral[side:, side:] - integral[:-side, side:] - integral[side:, :-side] + integral[:-side, :-side]
    return window[: region.shape[0], : region.shape[1]] == side * side


class Sharpness:
    """Pooled variance of the Laplacian of each region, before and after the blur, over the sampled frames."""

    def __init__(self) -> None:
        # region -> [count, sum and sum of squares before, sum and sum of squares after]
        self.sums = {"person": np.zeros(5), "background": np.zeros(5)}

    def add(self, before: np.ndarray, after: np.ndarray, mask: np.ndarray) -> None:
        """One frame: its luma before and after, and the person mask (0 to 255), all at the same size."""
        lap_before, lap_after = laplacian(before), laplacian(after)
        inner = mask[1:-1, 1:-1].astype(np.float32) / 255.0
        for name, region in (("person", inner >= PERSON), ("background", inner <= BACKGROUND)):
            chosen = erode(region, EDGE)
            if chosen.any():
                b, a = lap_before[chosen].astype(np.float64), lap_after[chosen].astype(np.float64)
                self.sums[name] += [b.size, b.sum(), (b * b).sum(), a.sum(), (a * a).sum()]

    def drops(self) -> dict[str, float | None]:
        """Per region, the share of the Laplacian variance the blur removed (0.95 = 95 %), None when never seen."""
        found: dict[str, float | None] = {}
        for name, (count, s1, q1, s2, q2) in self.sums.items():
            if count == 0:
                found[name] = None
                continue
            before = q1 / count - (s1 / count) ** 2
            after = q2 / count - (s2 / count) ** 2
            found[name] = round(1.0 - after / before, 4) if before > 0 else None
        return found


def sampled(ffmpeg: Path, source: Path, width: int, height: int, scale: str, luma: bool) -> Iterator[np.ndarray]:
    """One frame in SAMPLE_EVERY of source: its raw luma plane (no conversion, whatever the colour tags say), or for a
    mask its gray level."""
    every = f"select='not(mod(n\\,{SAMPLE_EVERY}))',setpts=N/{media.FPS}/TB"
    if not luma:
        return media.frames(ffmpeg, source, width, height, f"{scale},{every}", pix_fmt="gray")
    planes = media.frames(ffmpeg, source, width, height, f"{scale},{every}", pix_fmt="yuv420p")
    return (frame[: width * height].reshape(height, width) for frame in planes)


def measure(ffmpeg: Path, before: Path, after: Path, mask: Path, width: int, height: int) -> dict[str, float | None]:
    """The sharpness drops of person and background, on the luma of one frame in SAMPLE_EVERY."""
    found = Sharpness()
    same = f"scale={width}:{height}"
    streams = zip(
        sampled(ffmpeg, before, width, height, same, luma=True),
        sampled(ffmpeg, after, width, height, same, luma=True),
        sampled(ffmpeg, mask, width, height, f"scale={width}:{height}:flags=bilinear", luma=False),
        strict=True,
    )
    for frame_before, frame_after, frame_mask in streams:
        found.add(frame_before, frame_after, frame_mask)
    return found.drops()
