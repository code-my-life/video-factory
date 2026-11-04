"""master: H.264 High in BT.709 at 30 frames per second with AAC 48 kHz, bitexact and without metadata; the same
inputs give the same frames, hashed by framemd5."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from conftest import ffmpeg
from video_factory import master, media, music, qc

FRAMES = 12


def inputs(box, folder: Path) -> tuple[Path, Path, Path]:
    """PNG frames like those of compose (a moving pattern), a mono voice and the music bed."""
    frames = folder / "frames"
    frames.mkdir()
    ffmpeg(
        box,
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size=144x256:rate=30:duration={FRAMES / 30}",
        "-start_number",
        "1",
        frames / "frame_%06d.png",
    )
    voice = folder / "voice.wav"
    ffmpeg(
        box, "-f", "lavfi", "-i", "sine=f=220:sample_rate=48000:duration=0.3", "-ac", "1", "-c:a", "pcm_s24le", voice
    )
    bed = folder / "music.wav"
    music.write(bed, music.bed(FRAMES / 30))
    return frames, voice, bed


def render(box, folder: Path, frames: Path, voice: Path, bed: Path, name: str) -> tuple[Path, Path]:
    output, digest = folder / f"{name}.mp4", folder / f"{name}.framemd5"
    media.ffmpeg(box.ffmpeg, master.command(frames, voice, bed, FRAMES, name, output), "master")
    media.ffmpeg(box.ffmpeg, master.framemd5_command(output, digest), "framemd5")
    return output, digest


@pytest.mark.acceptance("deux rendus des mêmes entrées donnent les mêmes framemd5")
def test_two_renders_of_the_same_inputs_give_the_same_framemd5(tools, tmp_path):
    box = tools("ffmpeg")
    frames, voice, bed = inputs(box, tmp_path)
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    one = render(box, first, frames, voice, bed, "master")
    two = render(box, second, frames, voice, bed, "master")
    lines = one[1].read_text().splitlines()
    assert lines == two[1].read_text().splitlines()
    assert sum(1 for line in lines if line.startswith("0,")) == FRAMES
    assert any(line.startswith("1,") for line in lines)
    # Not only the decoded frames: the files themselves are the same bytes.
    assert one[0].read_bytes() == two[0].read_bytes()
    # A different input gives different hashes, so the comparison means something.
    other = tmp_path / "other"
    other.mkdir()
    louder = tmp_path / "louder.wav"
    ffmpeg(box, "-i", voice, "-af", "volume=2", "-c:a", "pcm_s24le", louder)
    assert render(box, other, frames, louder, bed, "master")[1].read_text() != one[1].read_text()


def test_the_master_and_the_tiktok_export_have_the_platform_formats_and_no_metadata(tools, tmp_path):
    box = tools("ffmpeg")
    frames, voice, bed = inputs(box, tmp_path)
    for name in ("master", "tiktok"):
        output, _digest = render(box, tmp_path, frames, voice, bed, name)
        facts = qc.stream_facts(box.ffprobe, output)
        assert qc.check_format(name, facts).ok, qc.check_format(name, facts).message
        assert facts["duration"] == pytest.approx(FRAMES / 30, abs=0.03)
        probed = json.loads(
            subprocess.run(
                [
                    str(box.ffprobe),
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(output),
                ],
                capture_output=True,
                check=True,
            ).stdout
        )
        assert set(probed["format"].get("tags", {})) <= {"major_brand", "minor_version", "compatible_brands"}
        assert all(set(s.get("tags", {})) <= {"handler_name", "vendor_id", "language"} for s in probed["streams"])
        data = output.read_bytes()
        assert b"x264 - core" not in data  # x264's settings SEI is removed
        assert data.index(b"moov") < data.index(b"mdat")  # faststart


def test_the_voice_is_mixed_at_minus_3_db_per_channel_so_the_stereo_keeps_its_loudness(tools, tmp_path):
    box = tools("ffmpeg")
    frames, voice, _bed = inputs(box, tmp_path)
    silence = tmp_path / "silence.wav"
    music.write(silence, np.zeros((round(FRAMES / 30 * music.SAMPLE_RATE), 2)))
    output, _digest = render(box, tmp_path, frames, voice, silence, "master")

    def samples(path: Path, channels: int) -> np.ndarray:
        raw = tmp_path / f"{path.stem}.f32"
        ffmpeg(box, "-i", path, "-f", "f32le", "-ac", str(channels), raw)
        return np.frombuffer(raw.read_bytes(), dtype="<f4").reshape(-1, channels)

    said = samples(voice, 1)[:, 0]
    stereo = samples(output, 2)[: said.size // 2]  # the first half of the voice, away from its fade and the AAC tail
    level = np.sqrt(np.mean(said[: said.size // 2] ** 2))
    for channel in (0, 1):
        assert np.sqrt(np.mean(stereo[:, channel] ** 2)) == pytest.approx(level * 10 ** (-3 / 20), rel=0.05)
