"""The music bed: synthesized with a fixed seed, the same on every render, low under the voice."""

from __future__ import annotations

import wave

import numpy as np

from video_factory import music


def test_the_same_seed_gives_the_same_bed_and_another_seed_another_one():
    assert np.array_equal(music.bed(4.0), music.bed(4.0))
    assert not np.array_equal(music.bed(4.0), music.bed(4.0, seed=1))


def test_the_bed_has_its_length_its_level_and_fades(tmp_path):
    bed = music.bed(10.0)
    assert bed.shape == (480000, 2)
    rms = np.sqrt(np.mean(bed[music.SAMPLE_RATE * 2 : music.SAMPLE_RATE * 7] ** 2))
    assert 20 * np.log10(rms) > music.RMS_DBFS - 3
    assert np.abs(bed[0]).max() == 0.0 and np.abs(bed[-1]).max() == 0.0
    path = tmp_path / "music.wav"
    music.write(path, bed)
    with wave.open(str(path)) as read:
        assert (read.getnchannels(), read.getframerate(), read.getnframes()) == (2, 48000, 480000)
