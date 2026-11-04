"""The published schemas: valid Draft 2020-12 documents, and the bounds the contract sets."""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from video_factory import schemas
from video_factory.paths import LOCK_SCHEMA, SCRIPT_SCHEMA, STATE_SCHEMA

SCRIPT = {"id": "essai", "titre": "Un titre", "plateforme": "tiktok", "duree_visee": 63}


@pytest.mark.parametrize("path", [STATE_SCHEMA, SCRIPT_SCHEMA, LOCK_SCHEMA])
def test_each_schema_is_a_valid_draft_2020_12_document(path):
    Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize(("duration", "valid"), [(60, False), (61, True), (65, True), (66, False), (75, False)])
def test_the_target_duration_runs_from_61_to_65_seconds(duration, valid):
    assert (schemas.problems(SCRIPT | {"duree_visee": duration}, SCRIPT_SCHEMA) == []) is valid


def test_the_platform_is_tiktok_and_every_field_is_required():
    assert schemas.problems(SCRIPT | {"plateforme": "youtube"}, SCRIPT_SCHEMA) != []
    for field in SCRIPT:
        assert schemas.problems({key: value for key, value in SCRIPT.items() if key != field}, SCRIPT_SCHEMA) != []


def test_the_script_and_the_state_share_the_same_id_rule():
    state = json.loads(STATE_SCHEMA.read_text(encoding="utf-8"))["$defs"]["video_id"]
    script = json.loads(SCRIPT_SCHEMA.read_text(encoding="utf-8"))["properties"]["id"]
    assert (script["pattern"], script["maxLength"]) == (state["pattern"], state["maxLength"])


def test_a_state_of_another_schema_version_or_with_a_short_fingerprint_is_refused():
    state = {
        "schema_version": 3,
        "id": "essai",
        "created_at": "2026-11-04T14:00:00Z",
        "script": {"path": "script.md", "sha256": "ab" * 32},
        "takes": [],
        "captures": {},
        "steps": {},
    }
    assert schemas.problems(state, STATE_SCHEMA) == []
    assert schemas.problems(state | {"schema_version": 2}, STATE_SCHEMA) != []
    assert schemas.problems(state | {"schema_version": 4}, STATE_SCHEMA) != []
    assert schemas.problems(state | {"route": "quicklook-screen"}, STATE_SCHEMA) != []
    assert schemas.problems(state | {"steps": {"scan": {}}}, STATE_SCHEMA) != []
    assert schemas.problems(state | {"script": {"path": "script.md", "sha256": "ab"}}, STATE_SCHEMA) != []
    assert schemas.problems(state | {"created_at": "2026-11-04 14:00"}, STATE_SCHEMA) != []
