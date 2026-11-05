"""A capture plan and the pinned source of its app: read, checked against their schemas and the rules a schema cannot
say, with every default filled in. A refused plan names the field at fault."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator

from video_factory import schemas
from video_factory.paths import CAPTURE_PLAN_SCHEMA, CAPTURE_SOURCE_SCHEMA, VITRINE_DIR

IPHONE = {"width": 390, "height": 844}
SCENE_FPS = 30
DEFAULTS = {"scale": 3, "fps": 30, "view": "", "actions": [], "texts": True}
CAMERA_DEFAULTS = {
    "move": 0.5,
    "anchor": {"x": 0.5, "y": 0.42},
    "dead_zone": 24,
    "blur": {"copies": 6, "shutter": 0.5},
    "labels": {},
    "cuts": [],
}
PHONE_KEY = {"scale": 2.6, "rx": 0.0, "ry": 0.0, "rz": 0.0, "y": 0.0}


class PlanError(Exception):
    """The plan or its source is unreadable or invalid; the message names each field at fault."""


@dataclass(frozen=True)
class Source:
    """The pinned source of an app (vitrine/<app>/source.json) and the folder that holds it and its variant."""

    folder: Path
    doc: dict

    @property
    def patch(self) -> Path:
        return self.folder / str(self.doc["patch"])


def field_name(error) -> str:
    """The dotted path of the field an error is about; for a missing property, that property's own path."""
    parts = [str(part) for part in error.absolute_path]
    if error.validator == "required":
        missing = [name for name in error.validator_value if name not in error.instance]
        parts += missing[:1]
    if error.validator == "additionalProperties":
        extra = sorted(set(error.instance) - set(error.schema.get("properties", {})))
        parts += extra[:1]
    return ".".join(parts) or "(racine)"


def field_problems(instance: object, schema_path: Path) -> list[str]:
    """Every violation, as « champ « a.b » : message », one per field, sorted by field."""
    validator: Draft202012Validator = schemas.validator(schema_path)
    found: dict[str, str] = {}
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(map(str, item.absolute_path))):
        # A oneOf (the actions) reports its own branch errors only as context: take the deepest one of the branch the
        # action names (the others fail on their « do »).
        branch = [item for item in error.context if list(item.absolute_path)[-1:] != ["do"]] or error.context
        deepest = max(branch, key=lambda item: len(item.absolute_path), default=error) if error.context else error
        name = field_name(deepest)
        found.setdefault(name, f"champ « {name} » : {deepest.message}")
    return [found[name] for name in sorted(found)]


def rule_problems(plan: dict) -> list[str]:
    """The rules beyond the schema, for a plan that already matches it."""
    found = []
    scenario = plan["scenario"]
    if scenario["end"] <= scenario["start"]:
        found.append("champ « scenario.end » : la fin doit venir après le début")
    if plan["device"] == "iphone" and plan["window"] != IPHONE:
        found.append("champ « window » : l'iPhone se filme en 390x844")
    times = [action["at"] for action in plan["actions"]]
    if times != sorted(times):
        found.append("champ « actions » : les gestes doivent suivre l'ordre du temps")
    late = [index for index, at in enumerate(times) if at >= scenario["end"]]
    if late:
        found.append(f"champ « actions.{late[0]}.at » : un geste après la fin de la plage filmée")
    camera = plan.get("camera")
    if camera and plan["fps"] != SCENE_FPS:
        found.append(f"champ « fps » : une caméra se rend à {SCENE_FPS} images par seconde")
    if camera and camera["follow"] not in plan["track"]:
        found.append(f"champ « camera.follow » : « {camera['follow']} » n'est pas un élément de track")
    if camera and camera.get("arriving"):
        flags = plan["track"].get(camera["follow"], {}).get("flags", [])
        if camera["arriving"] not in flags:
            found.append("champ « camera.arriving » : ce drapeau doit être relevé (track.<suivi>.flags)")
    if camera:
        cuts = [cut["at"] for cut in camera.get("cuts", [])]
        if cuts != sorted(cuts):
            found.append("champ « camera.cuts » : les coupes doivent suivre l'ordre du temps")
        for index, cut in enumerate(camera.get("cuts", [])):
            if cut.get("follow") and cut["follow"] not in plan["track"]:
                name = f"camera.cuts.{index}.follow"
                found.append(f"champ « {name} » : « {cut['follow']} » n'est pas un élément de track")
    phone = plan.get("phone")
    if phone and plan["device"] != "iphone":
        found.append("champ « phone » : la scène téléphone se tourne à l'iPhone")
    if phone and camera:
        found.append("champ « phone » : un plan a une caméra ou un téléphone, pas les deux")
    if phone and plan["fps"] != SCENE_FPS:
        found.append(f"champ « fps » : une scène se rend à {SCENE_FPS} images par seconde")
    if phone:
        keys = [key["t"] for key in phone["keys"]]
        if keys != sorted(keys):
            found.append("champ « phone.keys » : les poses doivent suivre l'ordre du temps")
    return found


def with_defaults(plan: dict) -> dict:
    done = DEFAULTS | plan
    if "camera" in plan:
        done["camera"] = CAMERA_DEFAULTS | plan["camera"]
    if "phone" in plan:
        phone = dict(plan["phone"])
        keys, last = [], PHONE_KEY
        for key in phone["keys"]:
            last = last | key
            keys.append(dict(last))
        phone["keys"] = keys
        if "notification" in phone:
            phone["notification"] = {"app": "factory-live"} | phone["notification"]
        done["phone"] = phone
    return done


def check(plan: object) -> dict:
    """The plan with its defaults, or PlanError naming every field at fault."""
    found = field_problems(plan, CAPTURE_PLAN_SCHEMA)
    if found:
        raise PlanError("plan de capture invalide :\n" + "\n".join(f"- {line}" for line in found))
    full = with_defaults(dict(plan))
    found = rule_problems(full)
    if found:
        raise PlanError("plan de capture invalide :\n" + "\n".join(f"- {line}" for line in found))
    return full


def read_json(path: Path, what: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError(f"{what} illisible ({path}) : {exc}") from exc


def load(path: Path) -> dict:
    return check(read_json(path, "plan de capture"))


def load_source(app: str, vitrine: Path = VITRINE_DIR) -> Source:
    folder = vitrine / app
    doc = read_json(folder / "source.json", f"source de {app}")
    found = field_problems(doc, CAPTURE_SOURCE_SCHEMA)
    if found:
        raise PlanError(f"{folder / 'source.json'} invalide :\n" + "\n".join(f"- {line}" for line in found))
    source = Source(folder, doc)
    if not source.patch.is_file():
        raise PlanError(f"variante de scénario absente : {source.patch}")
    return source
