"""The face detector (BlazeFace short range through LiteRT) and the scan report built on it."""

from __future__ import annotations

import numpy as np
import pytest

from conftest import drawn_face, write_video
from video_factory import faces, scan


def test_the_anchors_are_the_896_of_blazeface_short_range():
    found = faces.anchors()
    assert found.shape == (896, 2)
    assert found[0].tolist() == pytest.approx([1 / 32, 1 / 32])
    assert found[511].tolist() == pytest.approx([31 / 32, 31 / 32])
    assert found[512].tolist() == pytest.approx([1 / 16, 1 / 16])


def test_the_three_windows_cover_the_whole_frame():
    frame = np.zeros((256, 144, 3), np.uint8)
    found = faces.windows(frame)
    assert [picture.shape for picture, _covered in found] == [(128, 128, 3)] * 3
    assert found[0][1] == pytest.approx((56 / 256, 200 / 256))


def test_a_drawn_face_is_found_and_a_frame_without_one_is_not(tools):
    box = tools("mediapipe-face-detector")
    detector = faces.Detector(box.model("mediapipe-face-detector"))
    assert detector.score(drawn_face()) >= faces.THRESHOLD
    rng = np.random.default_rng(2)
    assert detector.score((rng.random((256, 144, 3)) * 255).astype(np.uint8)) < faces.THRESHOLD
    assert detector.score(drawn_face()) == detector.score(drawn_face())


def test_the_scan_report_names_frames_and_widens_ranges(tools, tmp_path):
    box = tools("ffmpeg", "mediapipe-face-detector")
    blank = np.full((256, 144, 3), 90, np.uint8)
    frames = [drawn_face() if index in (10, 11, 30) else blank for index in range(40)]
    video = write_video(box, frames, tmp_path / "work.mp4")
    report = scan.report(scan.frame_scores(box.ffmpeg, video, faces.Detector(box.model("mediapipe-face-detector"))))
    assert [face["frame"] for face in report["faces"]] == [10, 11, 30]
    assert report["faces"][0]["time"] == pytest.approx(10 / 30, abs=1e-3)
    assert [(r["first_frame"], r["last_frame"]) for r in report["ranges"]] == [(7, 14), (27, 33)]
    assert report["ranges"][0]["start"] == pytest.approx(7 / 30)
    assert report["ranges"][0]["end"] == pytest.approx(15 / 30)


def test_ranges_merge_when_they_touch_and_stay_in_the_video():
    assert scan.ranges([0, 1, 9, 15], 17, margin=3) == [(0, 4), (6, 16)]
    assert scan.ranges([0, 7], 17, margin=3) == [(0, 10)]  # 0-3 and 4-10 touch
    assert scan.ranges([0, 8], 17, margin=3) == [(0, 3), (5, 11)]  # frame 4 is between them
