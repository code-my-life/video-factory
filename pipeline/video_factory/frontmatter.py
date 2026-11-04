"""The front matter of script.md: a strict subset of YAML, read and written without a YAML library.

The block opens the file with a line « --- » and closes with the next one. Each line is « key: value »: a double-quoted
JSON string, a whole number, or a bare word. Anything else is an error that names its line, so a script is always read
the same way.
"""

from __future__ import annotations

import json
import re

FENCE = "---"
LINE = re.compile(r"^(?P<key>[a-z_][a-z0-9_]*):[ \t]*(?P<value>.*?)[ \t]*$")
INTEGER = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
# A bare word starts with a letter; a value that starts with a digit is a whole number or goes between quotes, so a
# float, a date or an octal never reads differently here and in YAML.
BARE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
# Bare words YAML reads as booleans or null rather than strings.
KEYWORD = re.compile(r"^(?:true|false|yes|no|on|off|y|n|null)$", re.IGNORECASE)


class FrontMatterError(ValueError):
    """The front matter is missing or breaks the subset."""


def parse_value(raw: str, number: int) -> str | int:
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise FrontMatterError(f"ligne {number} : chaîne entre guillemets mal formée") from exc
        if not isinstance(value, str):
            raise FrontMatterError(f"ligne {number} : chaîne entre guillemets mal formée")
        return value
    if INTEGER.match(raw):
        return int(raw)
    if KEYWORD.match(raw):
        raise FrontMatterError(f"ligne {number} : valeur « {raw} » ambiguë, à mettre entre guillemets")
    if BARE.match(raw):
        return raw
    raise FrontMatterError(f"ligne {number} : valeur « {raw} » : mot simple, nombre entier ou texte entre guillemets")


def split(text: str) -> tuple[dict[str, str | int], str]:
    """(fields, body) of a script.md text."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != FENCE:
        raise FrontMatterError("ligne 1 : l'en-tête commence par « --- »")
    fields: dict[str, str | int] = {}
    for index, line in enumerate(lines[1:], start=2):
        line = line.rstrip("\r")
        if line == FENCE:
            return fields, "\n".join(lines[index:])
        if not line.strip():
            continue
        match = LINE.match(line)
        if not match:
            raise FrontMatterError(f"ligne {index} : « clé: valeur » attendu")
        key = match.group("key")
        if key in fields:
            raise FrontMatterError(f"ligne {index} : « {key} » en double")
        fields[key] = parse_value(match.group("value"), index)
    raise FrontMatterError("en-tête sans « --- » de fin")


def render_value(value: str | int) -> str:
    if isinstance(value, int):
        return str(value)
    bare = BARE.match(value) and not KEYWORD.match(value)
    return value if bare else json.dumps(value, ensure_ascii=False)


def render(fields: dict[str, str | int]) -> str:
    """The front matter block for fields, which split reads back to the same values."""
    return "\n".join([FENCE, *(f"{key}: {render_value(value)}" for key, value in fields.items()), FENCE]) + "\n"
