"""qc: a master outside one of its bounds is refused, and the message names the bound."""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

from conftest import drawn_face, write_video
from video_factory import faces, qc, schemas
from video_factory.paths import SCRIPT_SCHEMA

GOOD = {
    "codec": "h264",
    "profile": "High",
    "width": 1440,
    "height": 2560,
    "frame_rate": Fraction(30),
    "constant": True,
    "color_primaries": "bt709",
    "color_transfer": "bt709",
    "color_space": "bt709",
    "color_range": "tv",
    "audio_codec": "aac",
    "sample_rate": 48000,
}


def facts(**changes) -> dict:
    found = {
        "duration": 63.0,
        "loudness": -14.1,
        "true_peak": -1.6,
        "master": GOOD,
        "tiktok": GOOD | {"width": 1080, "height": 1920},
        "text": [[0, 2249, 300, 1450, 1100, 1600]],
        "camera_frames": 1000,
        "frames": 2250,
        "faces": [],
    }
    return found | changes


def failed(found: dict) -> list[str]:
    return [check.message for check in qc.judge(found) if not check.ok]


def test_a_master_inside_every_bound_passes():
    assert failed(facts()) == []
    assert qc.report(qc.judge(facts()))["passed"] is True


@pytest.mark.acceptance("un master où un visage est détecté échoue, avec le numéro de l'image")
def test_a_master_where_a_face_is_detected_fails_with_the_frame_number(tools, tmp_path):
    box = tools("ffmpeg", "mediapipe-face-detector")
    rng = np.random.default_rng(4)
    background = [(rng.random((256, 144, 3)) * 60 + 20).astype(np.uint8) for _ in range(40)]
    frames = [drawn_face() if 20 <= index < 25 else picture for index, picture in enumerate(background)]
    master = write_video(box, frames, tmp_path / "master.mp4")
    detector = faces.Detector(box.model("mediapipe-face-detector"))
    found = qc.detected_faces(box.ffmpeg, master, detector)
    assert [face["frame"] for face in found] == [20, 21, 22, 23, 24]
    messages = failed(facts(faces=found))
    assert len(messages) == 1
    assert messages[0].startswith("visage détecté : image 20 (0,67 s), image 21 (0,70 s)")


@pytest.mark.acceptance("un texte hors de la zone sûre fait échouer le master")
def test_text_outside_the_safe_zone_fails_the_master():
    low = facts(text=[[0, 9, 300, 1450, 1100, 1600], [10, 20, 300, 1500, 1100, 1700]])
    assert failed(low) == [
        "texte hors de la zone sûre, 35 % en bas : image 10 (0,33 s), image 11 (0,37 s), "
        "image 12 (0,40 s), image 13 (0,43 s), image 14 (0,47 s), image 15 (0,50 s), image 16 "
        "(0,53 s), image 17 (0,57 s), image 18 (0,60 s), image 19 (0,63 s), … (11 images)"
    ]
    sides = {
        "15 % en haut": [0, 0, 300, 380, 1100, 500],
        "6 % à gauche": [0, 0, 80, 1450, 1100, 1600],
        "17,8 % à droite": [0, 0, 300, 1450, 1190, 1600],
    }
    for side, run in sides.items():
        assert f"{side} : image 0 (0,00 s)" in failed(facts(text=[run]))[0]
    # The bounds themselves are inside: 288, 672, 65 and 192 px in 1080x1920 scale to these in 1440x2560.
    assert failed(facts(text=[[0, 0, 87, 384, 1183, 1664]])) == []


# The issue named this test with 61 to 90 s; the owner narrowed the bounds to 61 to 65 s on 2026-11-04.
@pytest.mark.acceptance("une durée hors de 61 à 65 s fait échouer le master")
def test_a_duration_outside_61_to_65_seconds_fails_the_master():
    for seconds in (60.5, 65.04, 75.0):
        assert failed(facts(duration=seconds)) == [f"durée : {seconds:.2f} s, hors de 61 à 65 s".replace(".", ",")]
    for seconds in (61.0, 63.0, 65.0):
        assert failed(facts(duration=seconds)) == []


def test_qc_reads_its_duration_bounds_from_the_script_schema():
    assert qc.DURATION == schemas.duration_bounds(SCRIPT_SCHEMA) == (61, 65)


@pytest.mark.acceptance("des plans face caméra au-delà de la moitié de la durée font échouer le master")
def test_face_camera_shots_over_half_of_the_duration_fail_the_master():
    assert failed(facts(camera_frames=1126, frames=2250)) == [
        "plans face caméra : 50,0 % de la durée, plus de la moitié"
    ]
    assert failed(facts(camera_frames=1125, frames=2250)) == []


def test_loudness_off_target_and_a_true_peak_over_minus_one_fail():
    assert failed(facts(loudness=-15.2)) == ["sonie : -15,2 LUFS, hors de -14 LUFS à 1 LU près"]
    assert failed(facts(true_peak=-0.8)) == ["crête vraie : -0,8 dBTP, au-dessus de -1 dBTP"]
    assert failed(facts(loudness=-13.0, true_peak=-1.0)) == []


def test_a_wrong_codec_size_rate_or_colour_fails_and_is_named():
    wrong = GOOD | {"profile": "Main", "frame_rate": Fraction(60), "color_primaries": "bt2020"}
    message = failed(facts(master=wrong))[0]
    assert message.startswith("format du master : h264 Main au lieu de H.264 High")
    assert "60 images par seconde au lieu de 30" in message
    assert "au lieu de BT.709" in message
    assert failed(facts(tiktok=GOOD)) == ["format de l'export TikTok : 1440x2560 au lieu de 1080x1920"]
    variable = failed(facts(master=GOOD | {"constant": False}))
    assert variable == ["format du master : cadence variable au lieu de 30 images par seconde constantes"]
