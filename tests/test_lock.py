"""The toolchain lock: every tool pinned by version and SHA-256, with its download URL and its install command."""

from __future__ import annotations

import copy
import json

import pytest

from video_factory import lock
from video_factory.paths import LOCK_FILE, REPO_ROOT

PINNED = lock.load(LOCK_FILE)
TOOLS = lock.by_name(PINNED)


def test_the_lock_matches_its_schema_and_its_rules():
    assert lock.rule_problems(PINNED) == []


def test_each_tool_has_its_url_its_sha256_and_the_command_that_installs_it():
    for name, tool in TOOLS.items():
        assert tool["install"] == f"uv run vf doctor --install {name}"
        assert len(tool["sha256"]) == 64
        if tool["kind"] != "docker-image":
            assert tool["url"].startswith("https://")


def test_the_lock_pins_the_tools_of_the_chain():
    assert {
        "ffmpeg",
        "whisper.cpp",
        "whisper-large-v3-turbo",
        "hyperframes",
        "hyperframes-render-base",
        "mediapipe-face-detector",
        "mediapipe-selfie-segmenter",
    } <= set(TOOLS)


def test_whisper_cpp_is_pinned_by_its_tag_and_its_commit():
    tool = TOOLS["whisper.cpp"]
    assert tool["url"].endswith(f"/refs/tags/{tool['version']}.tar.gz")
    assert len(tool["commit"]) == 40
    assert "-DGGML_NATIVE=OFF" in tool["cmake_args"]


def test_hyperframes_runs_without_telemetry_update_checks_or_installs_on_demand():
    env = TOOLS["hyperframes"]["env"]
    for name in (
        "HYPERFRAMES_NO_TELEMETRY",
        "DO_NOT_TRACK",
        "HYPERFRAMES_NO_UPDATE_CHECK",
        "HYPERFRAMES_NO_AUTO_INSTALL",
    ):
        assert env[name] == "1"
    assert TOOLS["hyperframes"]["config_expect"]["values"] == {"telemetryEnabled": False}


def test_the_npm_lockfile_pins_the_same_hyperframes_tarball():
    tool = TOOLS["hyperframes"]
    npm_lock = json.loads((REPO_ROOT / tool["lockfile"]).read_text(encoding="utf-8"))
    entry = npm_lock["packages"][f"node_modules/{tool['package']}"]
    assert (entry["version"], entry["resolved"]) == (tool["version"], tool["url"])
    assert all(meta.get("integrity", "").startswith("sha512-") for path, meta in npm_lock["packages"].items() if path)


def test_the_render_base_is_the_image_hyperframes_builds_from():
    assert TOOLS["hyperframes-render-base"]["image"] == "node:22.23.4-bookworm-slim"


def test_a_duplicate_name_a_late_requirement_and_a_wrong_install_command_are_refused():
    broken = copy.deepcopy(PINNED)
    first = broken["tools"][0]
    broken["tools"].append(copy.deepcopy(first))
    broken["tools"][0]["requires"] = ["node"]
    broken["tools"][1]["install"] = "curl | sh"
    found = lock.rule_problems(broken)
    assert any("nom en double" in line for line in found)
    assert any("doit être déclaré avant lui" in line for line in found)
    assert any("la commande d'installation" in line for line in found)


def test_an_unknown_tool_name_is_refused():
    with pytest.raises(lock.LockError, match="outil inconnu"):
        lock.requirement_order(PINNED, ["ffmpeg", "absent"])


def test_requirements_come_first_in_lock_order():
    assert lock.requirement_order(PINNED, ["hyperframes", "whisper.cpp"]) == [
        "cmake",
        "whisper.cpp",
        "node",
        "hyperframes",
    ]
