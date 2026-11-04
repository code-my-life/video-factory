"""ingest: the working copy of a take is cropped and set right by its route, at 30 frames per second, in BT.709 SDR,
with the sound at 48 kHz, and without any metadata of the phone."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from conftest import ffmpeg
from video_factory import ingest, media, routes
from video_factory.paths import ROUTES_FILE

APPLE = [
    "-movflags",
    "use_metadata_tags",
    "-metadata",
    "com.apple.quicktime.make=Apple",
    "-metadata",
    "com.apple.quicktime.model=iPhone 16 Pro",
    "-metadata",
    "com.apple.quicktime.location.ISO6709=+48.8566+002.3522+035.000/",
    "-metadata",
    "com.apple.quicktime.creationdate=2026-11-04T10:00:00+0100",
    "-metadata",
    "com.apple.quicktime.software=26.0",
    "-metadata",
    "creation_time=2026-11-04T09:00:00Z",
    "-metadata:s:v",
    "creation_time=2026-11-04T09:00:00Z",
    "-metadata:s:a",
    "creation_time=2026-11-04T09:00:00Z",
]
SMALL_ROUTE = {
    "about": "test",
    "source": {"width": 108, "height": 240},
    "crop": {"x": 0, "y": 24, "width": 108, "height": 192},
    "mirrored": True,
}


def screen_recording(box, path: Path, width: int, height: int, top: int, extra: list[str] = ()) -> Path:
    """A recording like the iPhone's: interface bands (magenta) above and below a mirrored scene whose true left half is
    blue and right half red, at 60 frames per second, with sound and the phone's metadata."""
    middle = height - 2 * top
    scene = (
        f"color=c=red:s={width // 2}x{middle}:r=60:d=1[l];color=c=blue:s={width // 2}x{middle}:r=60:d=1[r];"
        f"[l][r]hstack[m];color=c=magenta:s={width}x{height}:r=60:d=1[ui];[ui][m]overlay=0:{top},format=yuv420p"
    )
    ffmpeg(
        box,
        "-f",
        "lavfi",
        "-i",
        scene,
        "-f",
        "lavfi",
        "-i",
        "sine=f=440:r=44100:d=1",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "10",
        "-c:a",
        "aac",
        "-ac",
        "2",
        *APPLE,
        *extra,
        path,
    )
    return path


def tags_of(box, path: Path) -> dict:
    done = subprocess.run(
        [
            str(box.ffprobe),
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return json.loads(done.stdout)


def mean_colour(box, path: Path, crop: str) -> np.ndarray:
    frame = next(media.frames(box.ffmpeg, path, 8, 8, f"{crop},scale=8:8:flags=area"))
    return frame.reshape(-1, 3).mean(axis=0)


@pytest.mark.acceptance("la copie de travail n'a plus aucune métadonnée de l'iPhone")
def test_the_working_copy_carries_no_metadata_of_the_iphone(tools, tmp_path):
    box = tools("ffmpeg")
    take = screen_recording(box, tmp_path / "IMG_0001.MOV", 108, 240, 24)
    before = json.dumps(tags_of(box, take))
    assert "iPhone 16 Pro" in before and "ISO6709" in before
    work = tmp_path / "work.mkv"
    ingest.make_working_copy(box.ffmpeg, box.ffprobe, [take], SMALL_ROUTE, work)
    probed = tags_of(box, work)
    tags = [probed["format"].get("tags", {}), *(stream.get("tags", {}) for stream in probed["streams"])]
    written = json.dumps(tags).lower()
    for trace in ("apple", "iphone", "iso6709", "location", "creation", "make", "model", "software", "2026"):
        assert trace not in written
    everything = json.dumps(probed).lower()
    for value in ("iphone 16 pro", "apple", "+48.8566+002.3522", "2026-11-04"):
        assert value not in everything
    assert [stream["codec_type"] for stream in probed["streams"]] == ["video", "audio"]
    assert probed["chapters"] == []
    # What is left are the muxer's own fields: its name and the length of each stream.
    assert set(probed["format"].get("tags", {})) <= {"encoder"}
    assert all(set(stream.get("tags", {})) <= {"DURATION"} for stream in probed["streams"])


@pytest.mark.acceptance("le recadrage d'une voie retire l'interface et remet l'image à l'endroit")
def test_the_route_crop_removes_the_interface_and_sets_the_image_right(tools, tmp_path):
    box = tools("ffmpeg")
    _name, route = routes.pick(routes.load(ROUTES_FILE), "quicklook-screen")
    source, crop = route["source"], route["crop"]
    take = screen_recording(box, tmp_path / "take.mov", source["width"], source["height"], crop["y"])
    work = tmp_path / "work.mkv"
    described = ingest.make_working_copy(box.ffmpeg, box.ffprobe, [take], route, work)
    out = described["work"]
    assert (out["width"], out["height"], out["frame_rate"]) == (crop["width"], crop["height"], "30")
    assert (out["color_primaries"], out["color_transfer"], out["color_space"]) == ("bt709", "bt709", "bt709")
    assert out["audio"] == {"codec": "pcm_s24le", "sample_rate": 48000}
    width, height = crop["width"], crop["height"]
    left = mean_colour(box, work, f"crop={width // 2 - 8}:{height}:0:0")
    right = mean_colour(box, work, f"crop={width // 2 - 8}:{height}:{width // 2 + 8}:0")
    assert left[2] > 200 and left[0] < 40  # the true left, blue, is on the left again
    assert right[0] > 200 and right[2] < 40
    for band in (f"crop={width}:8:0:0", f"crop={width}:8:0:{height - 8}"):
        top_or_bottom = mean_colour(box, work, band)
        assert not (top_or_bottom[0] > 150 and top_or_bottom[2] > 150), "interface band left in the frame"


def test_a_display_p3_take_and_an_hlg_take_come_out_in_bt709_sdr(tools, tmp_path):
    box = tools("ffmpeg")
    for name, tags, pix_fmt in (
        ("p3", "color_primaries=smpte432:color_trc=iec61966-2-1:colorspace=bt709", "yuv420p"),
        ("hlg", "color_primaries=bt2020:color_trc=arib-std-b67:colorspace=bt2020nc", "yuv420p10le"),
    ):
        take = tmp_path / f"{name}.mov"
        scene = f"color=c=0x30c060:s=108x240:r=60:d=1,format={pix_fmt},setparams={tags}:range=tv"
        ffmpeg(
            box,
            "-f",
            "lavfi",
            "-i",
            scene,
            "-f",
            "lavfi",
            "-i",
            "sine=d=1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            pix_fmt,
            "-c:a",
            "aac",
            take,
        )
        assert ingest.colour_filter(media.summary(media.probe(box.ffprobe, take))).startswith("zscale=")
        out = ingest.make_working_copy(box.ffmpeg, box.ffprobe, [take], SMALL_ROUTE, tmp_path / f"{name}.mkv")["work"]
        assert (out["pix_fmt"], out["color_primaries"], out["color_transfer"]) == ("yuv420p", "bt709", "bt709")


def test_a_take_of_another_size_or_without_sound_is_refused(tools, tmp_path):
    box = tools("ffmpeg")
    wrong = screen_recording(box, tmp_path / "wrong.mov", 120, 240, 24)
    with pytest.raises(ingest.IngestError, match="120x240 au lieu de 108x240"):
        ingest.make_working_copy(box.ffmpeg, box.ffprobe, [wrong], SMALL_ROUTE, tmp_path / "w.mkv")
    mute = tmp_path / "mute.mov"
    ffmpeg(box, "-f", "lavfi", "-i", "color=s=108x240:r=30:d=1", "-c:v", "libx264", mute)
    with pytest.raises(ingest.IngestError, match="aucune piste son"):
        ingest.make_working_copy(box.ffmpeg, box.ffprobe, [mute], SMALL_ROUTE, tmp_path / "m.mkv")


def test_the_routes_file_matches_its_schema_and_its_rules():
    loaded = routes.load(ROUTES_FILE)
    name, route = routes.pick(loaded, None)
    assert name == "quicklook-screen"
    assert route["source"] == {"width": 1206, "height": 2622}
    assert (route["crop"]["width"], route["crop"]["height"], route["mirrored"]) == (1206, 2144, True)
    assert "vérifier" in route["provisional"]


def test_a_route_whose_crop_leaves_its_source_or_is_not_9_16_is_refused():
    broken = {
        "routes_version": 1,
        "default": "a",
        "routes": {"a": SMALL_ROUTE | {"crop": {"x": 0, "y": 60, "width": 108, "height": 200}}},
    }
    assert routes.rule_problems(broken) == [
        "a : la zone utile dépasse l'image source",
        "a : la zone utile n'est pas en 9:16 (108x200)",
    ]
