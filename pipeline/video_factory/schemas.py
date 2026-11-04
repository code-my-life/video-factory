"""JSON Schema validation (Draft 2020-12) of the files vf reads and writes: lock, script front matter, state."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator


@cache
def validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def problems(instance: object, schema_path: Path) -> list[str]:
    """Every violation of the schema, as « where: what », sorted; an empty list means the instance is valid."""
    found = []
    for error in validator(schema_path).iter_errors(instance):
        where = "/".join(str(part) for part in error.absolute_path) or "(racine)"
        found.append(f"{where} : {error.message}")
    return sorted(found)


@cache
def duration_bounds(schema_path: Path) -> tuple[int, int]:
    """The bounds of a video's duration in seconds, as the script schema publishes them for « duree_visee »: the one
    place they are written, read by qc for the master."""
    field = json.loads(schema_path.read_text(encoding="utf-8"))["properties"]["duree_visee"]
    return field["minimum"], field["maximum"]


@cache
def def_validator(schema_path: Path, name: str) -> Draft202012Validator:
    """A validator for one entry of the schema's $defs, with the other definitions still reachable."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator({"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{name}"})


def def_problems(instance: object, schema_path: Path, name: str) -> list[str]:
    return sorted(error.message for error in def_validator(schema_path, name).iter_errors(instance))
