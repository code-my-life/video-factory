"""vf doctor --install: nothing reaches the tools directory before its SHA-256 (and, for sources, its commit) is
verified; a tool already in place is skipped; what a tool requires is installed first."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from conftest import tar_bytes
from video_factory import install
from video_factory.hashing import npm_integrity, sha256_bytes, tree_sha256
from video_factory.paths import Places


def serve(files: dict[str, bytes]):
    """An opener that answers each URL with its bytes, like a download."""

    def opener(url: str):
        if url not in files:
            raise OSError(f"404 {url}")
        return io.BytesIO(files[url])

    return opener


def places(tmp_path: Path) -> Places:
    return Places(content=tmp_path / "content", media=tmp_path / "media", tools=tmp_path / "tools")


def test_a_download_with_another_sha256_is_refused_and_leaves_nothing(tmp_path):
    target = tmp_path / "dl" / "file"
    with pytest.raises(install.InstallError, match="empreinte"):
        install.download("https://example.invalid/f", "00" * 32, target, serve({"https://example.invalid/f": b"x"}))
    assert not target.exists()
    assert not list((tmp_path / "dl").iterdir())


def test_a_verified_download_is_kept(tmp_path):
    target = tmp_path / "file"
    data = b"pinned bytes"
    install.download(
        "https://example.invalid/f", sha256_bytes(data), target, serve({"https://example.invalid/f": data})
    )
    assert target.read_bytes() == data


def test_an_archive_is_extracted_without_its_top_folder_and_checked_before_it_is_put_in_place(tmp_path):
    archive = tar_bytes({"bin/tool": b"#!/bin/sh\necho 1\n", "doc/README": b"doc"})
    expected_tree = tmp_path / "expected"
    expected_tree.mkdir()
    (tmp_path / "a.tgz").write_bytes(archive)
    install.extract(tmp_path / "a.tgz", expected_tree, 1)
    tool = {
        "name": "tool",
        "kind": "archive",
        "version": "1.0",
        "url": "https://example.invalid/a.tgz",
        "sha256": sha256_bytes(archive),
        "strip_components": 1,
        "tree_sha256": tree_sha256(expected_tree),
    }
    where = places(tmp_path)
    install.install_tool(tool, {"tools": [tool]}, where, tmp_path, serve({tool["url"]: archive}))
    final = where.tools / "tool" / "1.0"
    assert (final / "bin" / "tool").read_bytes().startswith(b"#!/bin/sh")
    assert not (final / "pkg-1.0").exists()
    assert [path.name for path in where.tools.iterdir()] == ["tool"]


def test_an_archive_whose_content_differs_from_the_lock_is_refused(tmp_path):
    archive = tar_bytes({"bin/tool": b"other"})
    tool = {
        "name": "tool",
        "kind": "archive",
        "version": "1.0",
        "url": "https://example.invalid/a.tgz",
        "sha256": sha256_bytes(archive),
        "strip_components": 1,
        "tree_sha256": "00" * 32,
    }
    where = places(tmp_path)
    with pytest.raises(install.InstallError, match="contenu extrait"):
        install.install_tool(tool, {"tools": [tool]}, where, tmp_path, serve({tool["url"]: archive}))
    assert not (where.tools / "tool").exists()


def test_an_archive_member_that_escapes_its_folder_is_refused(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo("pkg/../../escape")
        info.size = 1
        tar.addfile(info, io.BytesIO(b"x"))
    (tmp_path / "evil.tgz").write_bytes(buffer.getvalue())
    with pytest.raises(install.InstallError, match="archive refusée"):
        install.extract(tmp_path / "evil.tgz", tmp_path / "out", 1)
    assert not (tmp_path / "escape").exists()


def test_a_source_archive_without_the_pinned_commit_is_refused(tmp_path):
    archive = tar_bytes({"CMakeLists.txt": b"project(x)"}, pax={"comment": "11" * 20})
    tool = {
        "name": "whisper.cpp",
        "kind": "source-build",
        "version": "v1",
        "url": "https://example.invalid/src.tgz",
        "sha256": sha256_bytes(archive),
        "commit": "22" * 20,
        "requires": ["cmake"],
        "cmake_args": [],
        "target": "whisper-cli",
        "binary": "bin/whisper-cli",
    }
    lock = {"tools": [{"name": "cmake", "version": "4"}, tool]}
    with pytest.raises(install.InstallError, match="commit"):
        install.install_tool(tool, lock, places(tmp_path), tmp_path, serve({tool["url"]: archive}))


def test_an_npm_lockfile_that_does_not_pin_the_verified_tarball_is_refused(tmp_path):
    tarball = b"package tarball"
    repo = tmp_path / "repo"
    (repo / "toolchain").mkdir(parents=True)
    lockfile = repo / "toolchain" / "package-lock.json"
    lockfile.write_text(json.dumps({"packages": {"node_modules/hyperframes": {"integrity": "sha512-other"}}}))
    (repo / "toolchain" / "package.json").write_text("{}")
    tool = {
        "name": "hyperframes",
        "kind": "npm",
        "version": "0.9.12",
        "url": "https://example.invalid/hf.tgz",
        "sha256": sha256_bytes(tarball),
        "package": "hyperframes",
        "lockfile": "toolchain/package-lock.json",
        "requires": ["node"],
    }
    lock = {"tools": [{"name": "node", "version": "v22"}, tool]}
    with pytest.raises(install.InstallError, match="ne fige pas l'archive vérifiée"):
        install.install_tool(tool, lock, places(tmp_path), repo, serve({tool["url"]: tarball}))


def test_npm_integrity_is_the_sha512_npm_writes(tmp_path):
    path = tmp_path / "t.tgz"
    path.write_bytes(b"abc")
    assert npm_integrity(path) == (
        "sha512-3a81oZNherrMQXNJriBBMRLm+k6JqX6iCp7u5ktV05ohkpkqJ0/BqDa6PCOj/uu9RU1EI2Q86A4qmslPpUyknw=="
    )


def test_install_skips_tools_in_place_and_installs_requirements_first(tmp_path):
    data = b"model"
    model = {
        "name": "model",
        "kind": "file",
        "version": "r1",
        "url": "https://example.invalid/m",
        "sha256": sha256_bytes(data),
        "file": "m.bin",
    }
    user = {
        "name": "user",
        "kind": "file",
        "version": "r1",
        "url": "https://example.invalid/u",
        "sha256": sha256_bytes(b"u"),
        "file": "u.bin",
        "requires": ["model"],
    }
    other = dict(model, name="other", url="https://example.invalid/o")
    lock = {"tools": [other, model, user]}
    where = places(tmp_path)
    opener = serve({"https://example.invalid/m": data, "https://example.invalid/u": b"u"})

    def check(tool):
        return [] if tool["name"] == "other" or (where.tools / tool["name"] / "r1" / tool["file"]).exists() else ["x"]

    done = install.install(lock, ["user", "other"], where, tmp_path, check, opener)
    assert done == ["model", "user"]
    assert (where.tools / "model" / "r1" / "m.bin").read_bytes() == data
    assert install.install(lock, ["user"], where, tmp_path, check, opener) == []


def test_swap_in_replaces_a_previous_version_in_one_rename(tmp_path):
    final = tmp_path / "tool" / "1"
    final.mkdir(parents=True)
    (final / "old").write_text("old")
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "new").write_text("new")
    install.swap_in(staged, final)
    assert sorted(path.name for path in final.iterdir()) == ["new"]
    assert not (tmp_path / "tool" / "1.old").exists()
