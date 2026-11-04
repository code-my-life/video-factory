"""The « no content » check: git tracks no video content, and it names every file it refuses."""

from __future__ import annotations

from pathlib import Path

import check_no_content as check

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(repository: Path, capsys) -> tuple[int, str]:
    status = check.main([str(repository)])
    return status, capsys.readouterr().out


def test_a_script_under_videos_fails_and_names_the_file(make_repo, capsys):
    repository = make_repo({"README.md": b"socle\n", "videos/essai/script.md": b"---\nid: essai\n---\n"})
    status, out = run(repository, capsys)
    assert status == 1
    assert "videos/essai/script.md" in out
    assert "file=videos/essai/script.md" in out


def test_a_state_under_a_nested_videos_folder_fails(make_repo, capsys):
    repository = make_repo({"docs/videos/essai/state.json": b"{}\n"})
    status, out = run(repository, capsys)
    assert status == 1
    assert "docs/videos/essai/state.json" in out


def test_a_take_outside_the_fixtures_fails_whatever_the_case_of_its_extension(make_repo, capsys):
    repository = make_repo({"IMG_0001.MOV": b"\x00" * 10, "voix/prise.m4a": b"\x00", "photo.HEIC": b"\x00"})
    status, out = run(repository, capsys)
    assert status == 1
    for name in ("IMG_0001.MOV", "voix/prise.m4a", "photo.HEIC"):
        assert f"- {name} : " in out


def test_an_image_passes_only_under_design_or_the_fixtures(make_repo, capsys):
    repository = make_repo(
        {"design/robot.png": b"\x89PNG", "tests/fixtures/mire.jpg": b"\xff\xd8", "docs/capture.png": b"\x89PNG"}
    )
    status, out = run(repository, capsys)
    assert status == 1
    assert "- docs/capture.png : " in out
    assert "design/robot.png" not in out
    assert "tests/fixtures/mire.jpg" not in out


def test_a_small_synthetic_fixture_passes_and_an_oversized_one_fails(make_repo, capsys):
    small = b"\x00" * 1024
    big = b"\x00" * (check.FIXTURE_CAP + 1)
    repository = make_repo({"tests/fixtures/mire.mp4": small, "tests/fixtures/prise.wav": big})
    status, out = run(repository, capsys)
    assert status == 1
    assert "- tests/fixtures/prise.wav : fixture de" in out
    assert "tests/fixtures/mire.mp4" not in out


def test_a_module_named_videos_is_not_a_videos_folder(make_repo, capsys):
    repository = make_repo({"pipeline/video_factory/videos.py": b"pass\n", "README.md": b"x\n"})
    status, out = run(repository, capsys)
    assert status == 0
    assert "aucun contenu de vidéo" in out


def test_an_annotation_escapes_what_github_reads_as_syntax():
    line = check.annotation("a,b:c.mov", "50% : refusé")
    assert line.startswith("::error file=a%2Cb%3Ac.mov,title=Aucun contenu::")
    assert line.endswith("a,b:c.mov : 50%25 : refusé")


def test_this_repository_tracks_no_video_content(capsys):
    status, out = run(REPO_ROOT, capsys)
    assert status == 0, out
