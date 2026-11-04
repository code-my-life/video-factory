"""The media store: files and folders named by their fingerprint, read-only, stored once."""

from __future__ import annotations

from video_factory import store
from video_factory.hashing import sha256_bytes, tree_sha256


def test_a_file_is_stored_under_its_sha256_read_only_and_only_once(tmp_path):
    root = tmp_path / "media"
    first = tmp_path / "a.txt"
    first.write_bytes(b"prise")
    media = store.put(root, first, "mov", keep_source=True)
    assert media == {"sha256": sha256_bytes(b"prise"), "file": f"{sha256_bytes(b'prise')}.mov"}
    assert first.exists()
    assert store.path(root, media).stat().st_mode & 0o222 == 0
    again = tmp_path / "b.txt"
    again.write_bytes(b"prise")
    assert store.put(root, again, "mov") == media
    assert not again.exists()
    assert store.problem(root, media, deep=True) is None


def test_a_folder_is_stored_under_its_tree_fingerprint_and_a_missing_one_is_named(tmp_path):
    root = tmp_path / "media"
    folder = tmp_path / "frames"
    folder.mkdir()
    (folder / "frame_000001.png").write_bytes(b"png")
    digest = tree_sha256(folder)
    media = store.put_tree(root, folder, "frames")
    assert media == {"sha256": digest, "file": f"{digest}.frames"}
    assert store.problem(root, media, deep=True) is None
    assert (
        store.problem(root, {"sha256": "ab" * 32, "file": f"{'ab' * 32}.json"}) == f"{'ab' * 32}.json absent du magasin"
    )
