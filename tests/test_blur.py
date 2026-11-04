"""blur: the background is blurred and the person kept sharp, measured by the variance of the Laplacian."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import ellipse, ffmpeg, write_video
from video_factory import blur, ingest, media

WIDTH, HEIGHT = 216, 384


def textured(seed: int) -> np.ndarray:
    """A frame of 6-pixel squares of random colours: sharp edges everywhere, so blurring shows."""
    rng = np.random.default_rng(seed)
    squares = (rng.random((HEIGHT // 6, WIDTH // 6, 3)) * 255).astype(np.uint8)
    return np.kron(squares, np.ones((6, 6, 1), dtype=np.uint8))


def person_mask() -> np.ndarray:
    """A standing figure, as the segmenter would give it: 255 on the person, 0 elsewhere, 256x256 like the model."""
    mask = np.zeros((blur.MASK_SIZE, blur.MASK_SIZE, 3), np.uint8)
    ellipse(mask, (90, 128), (40, 30), (255, 255, 255))
    ellipse(mask, (200, 128), (70, 60), (255, 255, 255))
    return mask


@pytest.mark.acceptance("le flou laisse nette la personne détourée et floute tout le reste")
def test_the_blur_keeps_the_cut_out_person_sharp_and_blurs_everything_else(tools, tmp_path):
    box = tools("ffmpeg")
    frames = [textured(seed) for seed in range(60)]
    work = tmp_path / "work.mkv"
    raw = write_video(box, frames, tmp_path / "raw.mp4")
    ffmpeg(
        box,
        "-i",
        raw,
        "-f",
        "lavfi",
        "-i",
        "sine=d=2",
        "-shortest",
        "-c:v",
        "libx264",
        "-crf",
        str(ingest.CRF),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "pcm_s24le",
        work,
    )
    mask_frames = tmp_path / "mask.mp4"
    write_video(box, [person_mask()] * 60, mask_frames)
    mask = tmp_path / "mask.mkv"
    ffmpeg(box, "-i", mask_frames, "-vf", "format=gray", "-c:v", "ffv1", mask)
    output = tmp_path / "blur.mkv"
    media.ffmpeg(box.ffmpeg, blur.composite_command(work, mask, WIDTH, HEIGHT, output), "blur")
    drops = blur.measure(box.ffmpeg, work, output, mask, WIDTH, HEIGHT)
    assert drops["background"] >= 0.90
    assert abs(drops["person"]) < 0.05


def test_the_sharpness_measure_reads_each_region_apart():
    rng = np.random.default_rng(1)
    sharp = (rng.random((120, 120)) * 255).astype(np.uint8)
    flat = np.full_like(sharp, 128)
    mask = np.zeros_like(sharp)
    mask[:, :60] = 255
    after = sharp.copy()
    after[:, 60:] = flat[:, 60:]
    found = blur.Sharpness()
    found.add(sharp, after, mask)
    drops = found.drops()
    assert drops["person"] == pytest.approx(0.0, abs=1e-6)
    assert drops["background"] == pytest.approx(1.0, abs=1e-6)


def test_the_segmenter_gives_a_mask_between_0_and_1_and_the_same_one_twice(tools):
    box = tools("mediapipe-selfie-segmenter")
    frame = textured(3)[:256, :216]
    frame = np.pad(frame, ((0, 0), (0, 40), (0, 0)))
    first = blur.Segmenter(box.model("mediapipe-selfie-segmenter")).mask(frame)
    second = blur.Segmenter(box.model("mediapipe-selfie-segmenter")).mask(frame)
    assert first.shape == (256, 256)
    assert 0.0 <= first.min() <= first.max() <= 1.0
    assert np.array_equal(first, second)
