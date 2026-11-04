"""vf doctor: a tool passes only when present, at its version and its fingerprint; otherwise the report names the
tool, the gap and the command that installs it, and the exit code is 1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from video_factory import doctor
from video_factory.hashing import sha256_bytes, sha256_file, tree_sha256
from video_factory.paths import Places

MODEL = b"model weights"
DIGEST = "ab" * 32


def answers(outputs: dict[str, doctor.Completed]):
    """A runner that answers by the name of the command, and records what was run."""
    calls = []

    def run(argv, env):
        calls.append((argv, env))
        return outputs.get(Path(argv[0]).name, doctor.Completed(127, f"{argv[0]} introuvable"))

    run.calls = calls
    return run


@pytest.fixture
def setup(tmp_path: Path):
    """A tools directory with an archive tool, a model, a source build and an npm tool, all in place."""
    tools = tmp_path / "tools"
    archive_dir = tools / "ffmpeg" / "n9"
    (archive_dir / "bin").mkdir(parents=True)
    (archive_dir / "bin" / "ffmpeg").write_bytes(b"ffmpeg binary")
    model_dir = tools / "model" / "rev1"
    model_dir.mkdir(parents=True)
    (model_dir / "model.bin").write_bytes(MODEL)
    build_dir = tools / "whisper.cpp" / "v1"
    (build_dir / "bin").mkdir(parents=True)
    (build_dir / "bin" / "whisper-cli").write_bytes(b"whisper binary")
    npm_dir = tools / "hyperframes" / "0.9.12"
    package = npm_dir / "node_modules" / "hyperframes"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": "hyperframes", "version": "0.9.12"}))
    repo = tmp_path / "repo"
    (repo / "toolchain").mkdir(parents=True)
    (repo / "toolchain" / "package-lock.json").write_text("{}")
    user_home = tmp_path / "home"
    (user_home / ".hyperframes").mkdir(parents=True)
    (user_home / ".hyperframes" / "config.json").write_text(json.dumps({"telemetryEnabled": False}))
    source_build = {
        "name": "whisper.cpp",
        "kind": "source-build",
        "version": "v1",
        "sha256": "cd" * 32,
        "commit": "ef" * 20,
        "cmake_args": ["-DGGML_NATIVE=OFF"],
        "binary": "bin/whisper-cli",
        "install": "uv run vf doctor --install whisper.cpp",
        "version_check": {"command": ["bin/whisper-cli", "--version"], "expect": "whisper.cpp version: 1\n"},
    }
    stamp = doctor.build_stamp(source_build) | {"binary_sha256": sha256_file(build_dir / "bin" / "whisper-cli")}
    (build_dir / doctor.BUILD_STAMP).write_text(json.dumps(stamp))
    (npm_dir / doctor.INSTALL_STAMP).write_text(
        json.dumps({"lockfile_sha256": sha256_file(repo / "toolchain" / "package-lock.json")})
    )
    lock = {
        "tools": [
            {
                "name": "ffmpeg",
                "kind": "archive",
                "version": "n9",
                "install": "uv run vf doctor --install ffmpeg",
                "tree_sha256": tree_sha256(archive_dir),
                "version_check": {"command": ["bin/ffmpeg", "-version"], "expect": "ffmpeg version n9"},
            },
            {
                "name": "model",
                "kind": "file",
                "version": "rev1",
                "install": "uv run vf doctor --install model",
                "sha256": sha256_bytes(MODEL),
                "file": "model.bin",
            },
            source_build,
            {
                "name": "hyperframes",
                "kind": "npm",
                "version": "0.9.12",
                "install": "uv run vf doctor --install hyperframes",
                "package": "hyperframes",
                "lockfile": "toolchain/package-lock.json",
                "tree_sha256": tree_sha256(package),
                "env": {"HYPERFRAMES_NO_TELEMETRY": "1"},
                "version_check": {"command": ["node_modules/.bin/hyperframes", "--version"], "expect": "0.9.12"},
                "config_expect": {"path": "~/.hyperframes/config.json", "values": {"telemetryEnabled": False}},
            },
            {
                "name": "render-base",
                "kind": "docker-image",
                "version": "22",
                "install": "uv run vf doctor --install render-base",
                "sha256": DIGEST,
                "image": "node:22-slim",
            },
        ]
    }
    content = tmp_path / "content"
    (content / ".git").mkdir(parents=True)
    media = tmp_path / "media"
    media.mkdir()
    places = Places(content=content, media=media, tools=tools)
    outputs = {
        "ffmpeg": doctor.Completed(0, "ffmpeg version n9-20261104 Copyright"),
        "whisper-cli": doctor.Completed(0, "whisper.cpp version: 1\n"),
        "hyperframes": doctor.Completed(0, "0.9.12\n"),
        "docker": doctor.Completed(0, f'["node@sha256:{DIGEST}"]'),
    }
    return {"lock": lock, "places": places, "repo": repo, "home": user_home, "outputs": outputs, "tools": tools}


def diagnose(setup, outputs=None):
    run = answers(outputs or setup["outputs"])
    results = doctor.diagnose(setup["lock"], setup["places"], run, {"PATH": "/usr/bin"}, setup["repo"], setup["home"])
    text, status = doctor.report(results, Path("tools.lock.json"), setup["tools"])
    return text, status, run


def test_doctor_passes_when_every_tool_is_present_at_its_version_and_fingerprint(setup):
    text, status, _run = diagnose(setup)
    assert status == 0, text
    assert "vf doctor : tout est en place." in text
    assert "écart" not in text


def test_a_missing_tool_is_named_with_the_gap_and_the_command_that_installs_it(setup):
    (setup["tools"] / "model" / "rev1" / "model.bin").unlink()
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "écart  model : model.bin absent" in text
    assert "répare : uv run vf doctor --install model" in text
    assert "vf doctor : 1 problème." in text


def test_a_model_with_another_fingerprint_is_a_gap(setup):
    (setup["tools"] / "model" / "rev1" / "model.bin").write_bytes(b"other weights")
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "model : model.bin : empreinte" in text


def test_an_archive_tool_with_a_changed_file_is_a_gap(setup):
    (setup["tools"] / "ffmpeg" / "n9" / "bin" / "ffmpeg").write_bytes(b"patched")
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "ffmpeg : dossier : empreinte" in text
    assert "répare : uv run vf doctor --install ffmpeg" in text


def test_a_tool_that_answers_another_version_is_a_gap(setup):
    outputs = setup["outputs"] | {"ffmpeg": doctor.Completed(0, "ffmpeg version n8.1 Copyright")}
    text, status, _run = diagnose(setup, outputs)
    assert status == 1
    assert "ffmpeg : version : « ffmpeg version n9 » attendue, « ffmpeg -version » répond « ffmpeg version n8.1" in text


def test_a_source_build_from_other_options_is_a_gap(setup):
    stamp_path = setup["tools"] / "whisper.cpp" / "v1" / doctor.BUILD_STAMP
    stamp = json.loads(stamp_path.read_text())
    stamp_path.write_text(json.dumps(stamp | {"cmake_args": ["-DGGML_NATIVE=ON"]}))
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "whisper.cpp : construit depuis une autre source ou d'autres options" in text


def test_a_source_build_binary_changed_after_its_build_is_a_gap(setup):
    (setup["tools"] / "whisper.cpp" / "v1" / "bin" / "whisper-cli").write_bytes(b"swapped")
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "whisper.cpp : bin/whisper-cli modifié depuis sa construction" in text


def test_a_dev_build_version_is_not_the_pinned_release(setup):
    outputs = setup["outputs"] | {"whisper-cli": doctor.Completed(0, "whisper.cpp version: 1-dev\n")}
    text, status, _run = diagnose(setup, outputs)
    assert status == 1
    assert "whisper.cpp : version" in text


def test_an_npm_package_at_another_version_is_a_gap(setup):
    manifest = setup["tools"] / "hyperframes" / "0.9.12" / "node_modules" / "hyperframes" / "package.json"
    manifest.write_text(json.dumps({"name": "hyperframes", "version": "0.9.13"}))
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "hyperframes : version 0.9.13 installée au lieu de 0.9.12" in text


def test_hyperframes_with_telemetry_enabled_in_its_config_is_a_gap(setup):
    (setup["home"] / ".hyperframes" / "config.json").write_text(json.dumps({"telemetryEnabled": True}))
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "telemetryEnabled = false" in text


def test_hyperframes_runs_with_its_opt_out_environment(setup):
    _text, _status, run = diagnose(setup)
    envs = [env for argv, env in run.calls if Path(argv[0]).name == "hyperframes"]
    assert envs and all(env["HYPERFRAMES_NO_TELEMETRY"] == "1" for env in envs)


def test_an_npm_install_from_another_lockfile_is_a_gap(setup):
    (setup["repo"] / "toolchain" / "package-lock.json").write_text('{"changed": true}')
    text, status, _run = diagnose(setup)
    assert status == 1
    assert "hyperframes : installé depuis un autre toolchain/package-lock.json" in text


def test_a_docker_tag_on_another_digest_is_a_gap(setup):
    outputs = setup["outputs"] | {"docker": doctor.Completed(0, f'["node@sha256:{"00" * 32}"]')}
    text, status, _run = diagnose(setup, outputs)
    assert status == 1
    assert "render-base : node:22-slim n'est pas l'image figée" in text


def test_a_missing_docker_image_names_the_pull_command(setup):
    outputs = setup["outputs"] | {"docker": doctor.Completed(1, "Error response from daemon: No such image: node:22")}
    text, status, _run = diagnose(setup, outputs)
    assert status == 1
    assert "render-base : image node:22-slim absente" in text
    assert "répare : uv run vf doctor --install render-base" in text


def test_missing_places_are_gaps_with_their_fix(setup, tmp_path):
    places = Places(content=tmp_path / "nowhere", media=tmp_path / "no-media", tools=setup["tools"])
    results = doctor.check_places(places)
    lines = [problem for _label, problems in results for problem in problems]
    assert [problem.subject for problem in lines] == ["dépôt de contenu", "magasin des médias"]
    assert lines[0].fix == f"git clone https://github.com/code-my-life/video-content.git {tmp_path / 'nowhere'}"
    assert lines[1].fix == f"mkdir -p {tmp_path / 'no-media'}"


def test_a_media_store_on_a_windows_drive_is_a_gap(setup):
    places = Places(content=setup["places"].content, media=Path("/mnt/c/studio/media"), tools=setup["tools"])
    problems = [problem for _label, found in doctor.check_places(places) for problem in found]
    assert len(problems) == 1
    assert "disque Windows" in problems[0].gap


def test_image_repository_drops_the_tag_but_keeps_the_registry():
    assert doctor.image_repository("node:22.23.4-bookworm-slim") == "node"
    assert doctor.image_repository("ghcr.io/org/app:1.0") == "ghcr.io/org/app"
    assert doctor.image_repository("localhost:5000/app:1") == "localhost:5000/app"


def test_run_command_reports_a_missing_program_without_raising(tmp_path):
    done = doctor.run_command([str(tmp_path / "absent")])
    assert done.returncode == 127


@pytest.fixture
def built(tmp_path: Path):
    """A docker-build entry whose build folder is in place."""
    repo = tmp_path / "repo"
    context = repo / "toolchain" / "render"
    context.mkdir(parents=True)
    (context / "Dockerfile.render").write_text("FROM scratch\n")
    tool = {
        "name": "render",
        "kind": "docker-build",
        "version": "1",
        "install": "uv run vf doctor --install render",
        "sha256": "aa" * 32,
        "config_sha256": "bb" * 32,
        "image": "vf-render:1",
        "context": "toolchain/render",
        "context_sha256": tree_sha256(context),
    }
    return tool, repo


def test_a_built_image_with_the_pinned_id_passes(built):
    tool, repo = built
    for found in ("aa" * 32, "bb" * 32):
        assert (
            doctor.check_docker_build(tool, answers({"docker": doctor.Completed(0, f"sha256:{found}\n")}), repo) == []
        )


def test_a_built_image_with_another_id_or_absent_is_a_gap(built):
    tool, repo = built
    other = doctor.check_docker_build(tool, answers({"docker": doctor.Completed(0, "sha256:" + "cc" * 32)}), repo)
    assert other[0].gap.startswith("vf-render:1 n'est pas l'image figée")
    absent = doctor.check_docker_build(tool, answers({"docker": doctor.Completed(1, "Error: No such image")}), repo)
    assert absent[0].gap == "image vf-render:1 absente"
    assert absent[0].fix == "uv run vf doctor --install render"


def test_a_changed_build_folder_is_a_gap_that_asks_for_a_new_lock_entry(built):
    tool, repo = built
    (repo / "toolchain" / "render" / "Dockerfile.render").write_text("FROM scratch\nRUN true\n")
    found = doctor.check_docker_build(tool, answers({"docker": doctor.Completed(0, f"sha256:{'aa' * 32}")}), repo)
    assert "ne correspond pas au lock" in found[0].gap
    assert "reporter context_sha256" in found[0].fix


def test_after_installing_named_tools_only_those_are_reported(setup):
    run = answers(setup["outputs"])
    results = doctor.diagnose(
        setup["lock"], setup["places"], run, {"PATH": "/usr/bin"}, setup["repo"], setup["home"], only=["model"]
    )
    assert [label for label, _problems in results] == ["model rev1"]
