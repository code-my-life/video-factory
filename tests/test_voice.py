"""voice: the cut on the sample grid with short fades, the fixed chain, and the two loudness passes."""

from __future__ import annotations

import pytest

from conftest import ffmpeg
from video_factory import media, voice


def test_each_kept_segment_is_cut_on_the_sample_grid_with_fades():
    graph = voice.cut_graph([{"src_start": 0.5, "src_end": 1.0}, {"src_start": 2.0, "src_end": 2.002}])
    assert "atrim=start_sample=24000:end_sample=48000" in graph
    assert "afade=t=out:st=0.496000:d=0.004000" in graph
    assert "afade=t=in:st=0:d=0.001000" in graph  # a segment shorter than two fades fades over half of it
    assert graph.endswith("[s0][s1]concat=n=2:v=0:a=1[cut]")


def test_the_helmet_colour_is_band_limited_lightly_saturated_and_resonant():
    chain = ",".join(voice.HELMET)
    assert "highpass" in chain and "lowpass" in chain and "asoftclip" in chain and "aecho" in chain


def test_the_voice_comes_out_at_minus_14_lufs_with_its_true_peak_under_minus_1(tools, tmp_path):
    box = tools("ffmpeg")
    work = tmp_path / "work.mkv"
    tone = "sine=f=180:d=6,volume=0.1,tremolo=f=3:d=0.8"
    ffmpeg(box, "-f", "lavfi", "-i", tone, "-ar", "48000", "-ac", "1", "-c:a", "pcm_s24le", work)
    coloured, output = tmp_path / "c.wav", tmp_path / "v.wav"
    media.ffmpeg(box.ffmpeg, voice.coloured_command(work, [{"src_start": 0.0, "src_end": 6.0}], coloured), "voice")
    applied = voice.normalize(box.ffmpeg, coloured, voice.measure(box.ffmpeg, coloured), output)
    assert float(applied["output_i"]) == pytest.approx(-14.0, abs=0.5)
    assert float(applied["output_tp"]) <= -1.0
