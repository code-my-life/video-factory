"""Captures: a still or a short clip of a real screen, stored as a clean copy under the name the script gives it."""

from __future__ import annotations

import json
import subprocess

import pytest

from conftest import ffmpeg
from video_factory import captures, chain, compose


def tags(box, path) -> str:
    done = subprocess.run(
        [str(box.ffprobe), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        check=True,
    )
    probed = json.loads(done.stdout)
    return json.dumps([probed["format"].get("tags", {}), *(s.get("tags", {}) for s in probed["streams"])])


def test_a_still_and_a_clip_are_cleaned_of_metadata_and_sound(tools, tmp_path):
    box = tools("ffmpeg")
    still, clip = tmp_path / "ecran.png", tmp_path / "extrait.mp4"
    ffmpeg(
        box, "-f", "lavfi", "-i", "testsrc=size=320x240:rate=1", "-frames:v", "1", "-metadata", "Comment=secret", still
    )
    ffmpeg(
        box,
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=320x240:rate=25:duration=1",
        "-f",
        "lavfi",
        "-i",
        "sine=d=1",
        "-c:v",
        "libx264",
        "-metadata",
        "title=secret",
        "-c:a",
        "aac",
        clip,
    )
    clean_still, kind = captures.clean(box.ffmpeg, box.ffprobe, still, tmp_path)
    assert (kind, clean_still.suffix) == ("image", ".png")
    assert b"secret" not in clean_still.read_bytes() and b"tEXt" not in clean_still.read_bytes()
    folder = tmp_path / "clip"
    folder.mkdir()
    clean_clip, kind = captures.clean(box.ffmpeg, box.ffprobe, clip, folder)
    assert (kind, clean_clip.suffix) == ("video", ".mp4")
    assert "secret" not in tags(box, clean_clip)
    streams = json.loads(
        subprocess.run(
            [str(box.ffprobe), "-v", "error", "-print_format", "json", "-show_streams", str(clean_clip)],
            capture_output=True,
            check=True,
        ).stdout
    )["streams"]
    assert [s["codec_type"] for s in streams] == ["video"]
    assert streams[0]["r_frame_rate"] == "30/1"


def test_a_clip_shorter_than_its_shot_holds_its_last_frame_to_the_exact_length(tools, tmp_path):
    box = tools("ffmpeg")
    clip = tmp_path / "court.mp4"
    ffmpeg(box, "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=0.5", "-c:v", "libx264", clip)
    output = tmp_path / "shot.mp4"
    compose.capture_clip(box.ffmpeg, clip, 40, output)
    from video_factory import media

    assert media.frame_count(box.ffprobe, output) == 40


def test_registering_an_absent_capture_file_is_refused(tmp_path):
    with pytest.raises(chain.StepError, match="introuvable"):
        chain.register_capture(None, "ligne", tmp_path / "absent.png")
