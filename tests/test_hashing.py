"""Fingerprints of a tree: content and names count, timestamps and modes do not, links are recorded, not followed."""

from __future__ import annotations

import os
from pathlib import Path

from video_factory.hashing import tree_sha256


def make_tree(root: Path) -> Path:
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "tool").write_bytes(b"binary")
    (root / "share" / "doc").mkdir(parents=True)
    (root / "share" / "doc" / "README").write_bytes(b"doc")
    return root


def test_the_same_files_give_the_same_fingerprint_whatever_their_dates_and_modes(tmp_path):
    first = make_tree(tmp_path / "a")
    second = make_tree(tmp_path / "b")
    os.utime(second / "bin" / "tool", (0, 0))
    (second / "bin" / "tool").chmod(0o700)
    assert tree_sha256(first) == tree_sha256(second)


def test_a_changed_byte_or_a_renamed_file_changes_the_fingerprint(tmp_path):
    root = make_tree(tmp_path / "a")
    before = tree_sha256(root)
    (root / "bin" / "tool").write_bytes(b"binarY")
    changed = tree_sha256(root)
    (root / "bin" / "tool").rename(root / "bin" / "tool2")
    assert len({before, changed, tree_sha256(root)}) == 3


def test_a_link_is_recorded_by_its_target_and_never_followed(tmp_path):
    root = make_tree(tmp_path / "a")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"secret")
    (root / "bin" / "npm").symlink_to("../share/doc/README")
    (root / "linked").symlink_to(outside)
    before = tree_sha256(root)
    (outside / "secret").write_bytes(b"changed")
    assert tree_sha256(root) == before


def test_stamp_files_can_be_left_out(tmp_path):
    root = make_tree(tmp_path / "a")
    before = tree_sha256(root)
    (root / ".vf-build.json").write_text("{}")
    assert tree_sha256(root, frozenset({".vf-build.json"})) == before
    assert tree_sha256(root) != before
