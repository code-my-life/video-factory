"""The outside places: the content clone, the media store and the tools, set by VF_CONTENT, VF_MEDIA and VF_TOOLS."""

from __future__ import annotations

from pathlib import Path

from video_factory.paths import places

HOME = Path("/home/someone")


def test_defaults_sit_under_the_home_directory():
    found = places({}, HOME)
    assert found.content == HOME / "perso" / "video-content"
    assert found.media == HOME / "studio" / "media"
    assert found.tools == HOME / ".local" / "share" / "video-factory" / "tools"


def test_each_variable_overrides_its_place_and_a_leading_tilde_means_home():
    found = places({"VF_CONTENT": "/srv/content", "VF_MEDIA": "~/autre/media", "VF_TOOLS": " "}, HOME)
    assert found.content == Path("/srv/content")
    assert found.media == HOME / "autre" / "media"
    assert found.tools == HOME / ".local" / "share" / "video-factory" / "tools"
