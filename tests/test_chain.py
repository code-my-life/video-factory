"""The chain: a take delivered clean and framed goes from ingest to qc with no face detection, crop or blur."""

from __future__ import annotations

import json

import pytest

from video_factory import chain, lock
from video_factory.paths import LOCK_FILE, STATE_SCHEMA


def step_names() -> list[str]:
    """The step names a state.json may record."""
    return json.loads(STATE_SCHEMA.read_text(encoding="utf-8"))["properties"]["steps"]["propertyNames"]["enum"]


@pytest.mark.acceptance("la chaîne n'a pas d'étape scan")
def test_the_chain_has_no_scan_step():
    names = [step.name for step in chain.STEPS]
    assert names == ["ingest", "transcribe", "align", "cut", "voice", "compose", "master", "qc"]
    assert "scan" not in step_names()


def test_the_chain_has_no_blur_step_and_compose_reads_the_take_as_ingested():
    assert "blur" not in chain.BY_NAME
    assert "blur" not in step_names()
    assert chain.BY_NAME["compose"].after == ("ingest", "cut")


def test_no_step_needs_a_face_detector_or_a_segmenter():
    used = {tool for step in chain.STEPS for tool in step.tools}
    names = {tool["name"] for tool in lock.load(LOCK_FILE)["tools"]}
    assert not {name for name in used | names if name.startswith("mediapipe")}
