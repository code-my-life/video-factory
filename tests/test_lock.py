"""The toolchain lock: every tool pinned by version and SHA-256, with its download URL and its install command."""

from __future__ import annotations

import copy
import json

import pytest

from video_factory import lock
from video_factory.hashing import tree_sha256
from video_factory.paths import LOCK_FILE, REPO_ROOT

PINNED = lock.load(LOCK_FILE)
TOOLS = lock.by_name(PINNED)


def test_the_lock_matches_its_schema_and_its_rules():
    assert lock.rule_problems(PINNED) == []


def test_each_tool_has_its_url_its_sha256_and_the_command_that_installs_it():
    for name, tool in TOOLS.items():
        assert tool["install"] == f"uv run vf doctor --install {name}"
        assert len(tool["sha256"]) == 64
        if tool["kind"] not in ("docker-image", "docker-build"):
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


def test_gsap_is_the_copy_hyperframes_ships_taken_from_the_pinned_hyperframes_archive():
    gsap, cli = TOOLS["gsap"], TOOLS["hyperframes"]
    assert gsap["kind"] == "library"
    assert (gsap["url"], gsap["sha256"]) == (cli["url"], cli["sha256"])
    assert set(gsap["files"]) == {"gsap.min.js", "CustomEase.min.js", "MotionPathPlugin.min.js"}
    for name, pinned in gsap["files"].items():
        assert pinned["path"] == f"package/dist/vendor/npm/gsap@{gsap['version']}/dist/{name}"


def test_each_library_a_scene_may_load_is_pinned_file_by_file():
    libraries = {name: tool for name, tool in TOOLS.items() if tool["kind"] == "library"}
    assert set(libraries) == {"gsap", "lottie-web", "dotlottie-web", "animejs", "three"}
    assert TOOLS["animejs"]["version"].startswith("4.")
    for tool in libraries.values():
        assert tool["url"].startswith("https://registry.npmjs.org/")
        assert all(len(pinned["sha256"]) == 64 for pinned in tool["files"].values())


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


def test_the_render_image_is_built_from_the_pinned_folder_on_the_pinned_base():
    tool = TOOLS["hyperframes-render"]
    assert tool["kind"] == "docker-build"
    assert tool["context_sha256"] == tree_sha256(REPO_ROOT / tool["context"])
    base = TOOLS["hyperframes-render-base"]
    assert tool["build_args"]["BASE_IMAGE"] == f"{base['image']}@sha256:{base['sha256']}"
    assert tool["requires"] == ["hyperframes-render-base"]
    dockerfile = (REPO_ROOT / tool["dockerfile"]).read_text(encoding="utf-8")
    for name in tool["build_args"]:
        assert f"ARG {name}\n" in dockerfile, f"{name} has no default in the Dockerfile: the lock gives it"
    assert "hyperframes@" not in dockerfile  # HyperFrames comes from the npm lockfile, never from a tag


def test_the_render_image_runs_the_chrome_hyperframes_manages():
    tool = TOOLS["hyperframes-render"]
    assert tool["build_args"]["CHROME_VERSION"] == "152.0.7977.30"
    assert tool["version"].startswith(TOOLS["hyperframes"]["version"])
