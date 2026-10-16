"""Python boundary for the existing plan-v1 JSON schema and safe preview limits.

The schema file is the source of truth. This module adds the same timeline,
resource, and geometry-consistency checks used by the existing JS Reasoner.
The first neural model deliberately supports at most one component of each of
plan-v1's four component types; plans outside that learned subset remain valid
manual plans but cannot be used as this model's supervised target.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft7Validator

from .config import CATEGORIES, COMPONENT_TYPES, DEFAULT_CONSTRAINTS, HARD_LIMITS
from .paths import SCHEMA_PATH


@dataclass(frozen=True)
class NumericField:
    key: str
    component: str | None
    minimum: float
    maximum: float
    integer: bool = False


FIELDS: tuple[NumericField, ...] = (
    NumericField("effect.duration", None, 0.1, 10.0),
    NumericField("core.start_fraction", "core", 0.0, 1.0),
    NumericField("core.duration_fraction", "core", 0.05, 1.0),
    NumericField("core.position.x", "core", -20.0, 20.0),
    NumericField("core.position.y", "core", -20.0, 20.0),
    NumericField("core.position.z", "core", -20.0, 20.0),
    NumericField("core.radius", "core", 0.05, 5.0),
    NumericField("core.color.r", "core", 0.0, 1.0),
    NumericField("core.color.g", "core", 0.0, 1.0),
    NumericField("core.color.b", "core", 0.0, 1.0),
    NumericField("ring.start_fraction", "ring", 0.0, 1.0),
    NumericField("ring.duration_fraction", "ring", 0.05, 1.0),
    NumericField("ring.position.x", "ring", -20.0, 20.0),
    NumericField("ring.position.y", "ring", -20.0, 20.0),
    NumericField("ring.position.z", "ring", -20.0, 20.0),
    NumericField("ring.radius", "ring", 0.1, 10.0),
    NumericField("ring.endRadius", "ring", 0.1, 20.0),
    NumericField("ring.thickness", "ring", 0.01, 0.5),
    NumericField("ring.color.r", "ring", 0.0, 1.0),
    NumericField("ring.color.g", "ring", 0.0, 1.0),
    NumericField("ring.color.b", "ring", 0.0, 1.0),
    NumericField("lightning.start_fraction", "lightning", 0.0, 1.0),
    NumericField("lightning.duration_fraction", "lightning", 0.05, 1.0),
    NumericField("lightning.position.x", "lightning", -20.0, 20.0),
    NumericField("lightning.position.y", "lightning", -20.0, 20.0),
    NumericField("lightning.position.z", "lightning", -20.0, 20.0),
    NumericField("lightning.count", "lightning", 1.0, 32.0, integer=True),
    NumericField("lightning.length", "lightning", 0.1, 20.0),
    NumericField("lightning.segments", "lightning", 2.0, 32.0, integer=True),
    NumericField("lightning.jitter", "lightning", 0.0, 1.0),
    NumericField("lightning.color.r", "lightning", 0.0, 1.0),
    NumericField("lightning.color.g", "lightning", 0.0, 1.0),
    NumericField("lightning.color.b", "lightning", 0.0, 1.0),
    NumericField("particles.start_fraction", "particles", 0.0, 1.0),
    NumericField("particles.duration_fraction", "particles", 0.05, 1.0),
    NumericField("particles.position.x", "particles", -20.0, 20.0),
    NumericField("particles.position.y", "particles", -20.0, 20.0),
    NumericField("particles.position.z", "particles", -20.0, 20.0),
    NumericField("particles.count", "particles", 1.0, 512.0, integer=True),
    NumericField("particles.speed", "particles", 0.0, 20.0),
    NumericField("particles.size", "particles", 0.01, 0.5),
    NumericField("particles.gravity", "particles", -20.0, 20.0),
    NumericField("particles.color.r", "particles", 0.0, 1.0),
    NumericField("particles.color.g", "particles", 0.0, 1.0),
    NumericField("particles.color.b", "particles", 0.0, 1.0),
)
FIELD_INDEX = {field.key: index for index, field in enumerate(FIELDS)}
COMPONENT_INDEX = {name: index for index, name in enumerate(COMPONENT_TYPES)}
CATEGORY_INDEX = {name: index for index, name in enumerate(CATEGORIES)}

_SCHEMA: dict[str, Any] | None = None
_VALIDATOR: Draft7Validator | None = None


def get_validator() -> Draft7Validator:
    global _SCHEMA, _VALIDATOR
    if _VALIDATOR is None:
        with SCHEMA_PATH.open("r", encoding="utf-8") as stream:
            _SCHEMA = json.load(stream)
        Draft7Validator.check_schema(_SCHEMA)
        _VALIDATOR = Draft7Validator(_SCHEMA)
    return _VALIDATOR


def schema_issues(plan: Any) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def finite_paths(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, float) and not math.isfinite(value):
            pointer = "/" + "/".join(path) if path else "/"
            issues.append(_issue("SCHEMA", pointer, "JSON numbers must be finite.", "Replace NaN or Infinity with a finite number."))
        elif isinstance(value, dict):
            for key, child in value.items():
                finite_paths(child, (*path, str(key)))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                finite_paths(child, (*path, str(index)))

    finite_paths(plan)
    errors = sorted(
        get_validator().iter_errors(plan),
        key=lambda error: (list(map(str, error.absolute_path)), error.message),
    )
    for error in errors:
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        if path == "/":
            path = "/"
        issues.append(
            {
                "code": "SCHEMA",
                "path": path,
                "message": error.message,
                "correction": f"Fix {path} to match the checked-in plan 1.0 schema.",
            }
        )
    return issues


def analyze_plan(plan: Any) -> dict[str, Any]:
    """Validate plan-v1 plus safe resource/timing constraints without mutation."""
    issues = schema_issues(plan)
    if issues:
        return {"ok": False, "schemaVersion": "1.0", "stats": None, "issues": issues}

    ids: set[str] = set()
    objects = particles = vertices = 0
    for index, component in enumerate(plan["components"]):
        path = f"/components/{index}"
        component_id = component["id"]
        if component_id in ids:
            issues.append(
                _issue("DUPLICATE_ID", f"{path}/id", f"Duplicate id: {component_id}", "Assign a unique component id.")
            )
        ids.add(component_id)
        if component["start"] + component["duration"] > plan["duration"] + 1e-9:
            issues.append(
                _issue("TIMELINE_OVERFLOW", path, "Component ends after the effect.", "Reduce start or duration to fit the effect timeline.")
            )
        properties = component["properties"]
        kind = component["type"]
        if kind == "ring":
            if properties["endRadius"] < properties["radius"]:
                issues.append(
                    _issue("RING_CONTRACTS", f"{path}/properties/endRadius", "A shockwave must expand.", "Set endRadius >= radius.")
                )
            if properties["thickness"] >= properties["radius"]:
                issues.append(
                    _issue("RING_THICKNESS", f"{path}/properties/thickness", "Ring thickness consumes the central opening.", "Set thickness < radius.")
                )
        if kind == "core":
            objects += 2
            vertices += 542
        elif kind == "ring":
            objects += 1
            vertices += 585
        elif kind == "lightning":
            objects += properties["count"]
            vertices += properties["count"] * (properties["segments"] + 1)
        elif kind == "particles":
            objects += 1
            particles += properties["count"]
            vertices += properties["count"]

    if objects > plan["constraints"]["maxObjects"]:
        issues.append(
            _issue("OBJECT_BUDGET", "/constraints/maxObjects", f"{objects} render objects exceed the budget.", "Reduce component counts or raise maxObjects within the hard limit.")
        )
    if particles > plan["constraints"]["maxParticles"]:
        issues.append(
            _issue("PARTICLE_BUDGET", "/constraints/maxParticles", f"{particles} particles exceed the budget.", "Reduce particle counts or raise maxParticles within the hard limit.")
        )
    if objects > HARD_LIMITS["objects"]:
        issues.append(
            _issue("HARD_OBJECT_LIMIT", "/components", f"{objects} render objects exceed the hard limit {HARD_LIMITS['objects']}.", "Reduce component counts.")
        )
    if particles > HARD_LIMITS["particles"]:
        issues.append(
            _issue("HARD_PARTICLE_LIMIT", "/components", f"{particles} particles exceed the hard limit {HARD_LIMITS['particles']}.", "Reduce particle counts.")
        )
    if vertices > HARD_LIMITS["vertices"]:
        issues.append(
            _issue("VERTEX_BUDGET", "/components", f"{vertices} vertices exceed {HARD_LIMITS['vertices']}.", "Reduce component counts or lightning segments.")
        )

    return {
        "ok": not issues,
        "schemaVersion": "1.0",
        "issues": issues,
        "stats": {"components": len(ids), "objects": objects, "particles": particles, "vertices": vertices},
    }


def _issue(code: str, path: str, message: str, correction: str) -> dict[str, str]:
    return {"code": code, "path": path, "message": message, "correction": correction}


def model_subset_issues(plan: Any) -> list[dict[str, str]]:
    """Explain why a valid plan cannot be encoded by this first model version."""
    issues: list[dict[str, str]] = []
    if not isinstance(plan, dict) or not isinstance(plan.get("components"), list):
        return [_issue("MODEL_SUBSET", "/components", "A valid plan object is required.", "Load a plan 1.0 document.")]
    seen: set[str] = set()
    for index, component in enumerate(plan["components"]):
        kind = component.get("type") if isinstance(component, dict) else None
        if kind not in COMPONENT_INDEX:
            issues.append(_issue("MODEL_SUBSET", f"/components/{index}/type", "This model only learns the four plan-v1 component types.", "Use core, ring, lightning, or particles."))
        elif kind in seen:
            issues.append(_issue("MODEL_SUBSET", f"/components/{index}/type", "The first model supports at most one of each component type.", "Keep one component of each type in a supervised example."))
        seen.add(kind)
    return issues


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    return tuple(int(value[offset : offset + 2], 16) / 255.0 for offset in (1, 3, 5))  # type: ignore[return-value]


def encode_plan_targets(plan: dict[str, Any], category: str) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
    """Encode a validated subset plan into category, component, and numeric targets."""
    if category not in CATEGORY_INDEX:
        raise ValueError(f"Unknown training category: {category}")
    reason = analyze_plan(plan)
    if not reason["ok"]:
        raise ValueError("Cannot train on an invalid plan: " + "; ".join(issue["message"] for issue in reason["issues"][:3]))
    subset = model_subset_issues(plan)
    if subset:
        raise ValueError("Plan is valid but outside the first model subset: " + "; ".join(issue["message"] for issue in subset))

    numeric = np.zeros(len(FIELDS), dtype=np.float32)
    numeric_mask = np.zeros(len(FIELDS), dtype=np.float32)
    presence = np.zeros(len(COMPONENT_TYPES), dtype=np.float32)
    by_type = {component["type"]: component for component in plan["components"]}
    for component_type, component in by_type.items():
        presence[COMPONENT_INDEX[component_type]] = 1.0

    _put_normalized(numeric, numeric_mask, "effect.duration", plan["duration"])
    for component_type, component in by_type.items():
        prefix = component_type
        duration = float(plan["duration"])
        _put_normalized(numeric, numeric_mask, f"{prefix}.start_fraction", component["start"] / duration)
        _put_normalized(numeric, numeric_mask, f"{prefix}.duration_fraction", component["duration"] / duration)
        for axis, value in zip("xyz", component["position"]):
            _put_normalized(numeric, numeric_mask, f"{prefix}.position.{axis}", value)
        for key, value in component["properties"].items():
            if key in {"radius", "endRadius", "thickness", "count", "length", "segments", "jitter", "speed", "size", "gravity"}:
                _put_normalized(numeric, numeric_mask, f"{prefix}.{key}", value)
        red, green, blue = _hex_to_rgb(component["color"])
        for channel, value in zip(("r", "g", "b"), (red, green, blue)):
            _put_normalized(numeric, numeric_mask, f"{prefix}.color.{channel}", value)

    return CATEGORY_INDEX[category], presence, numeric, numeric_mask


def _put_normalized(values: np.ndarray, mask: np.ndarray, key: str, raw_value: float) -> None:
    field = FIELDS[FIELD_INDEX[key]]
    scaled = (float(raw_value) - field.minimum) / (field.maximum - field.minimum)
    values[FIELD_INDEX[key]] = np.float32(scaled)
    mask[FIELD_INDEX[key]] = 1.0


def decode_numeric(key: str, normalized: float) -> float | int | None:
    """Invert the target scaling without clipping; the Reasoner rejects bad values."""
    number = float(normalized)
    if not math.isfinite(number):
        return None
    field = FIELDS[FIELD_INDEX[key]]
    value = field.minimum + number * (field.maximum - field.minimum)
    if field.integer:
        return int(round(value))
    return float(value)


def make_candidate_plan(
    category_index: int,
    component_probabilities: np.ndarray,
    numeric_outputs: np.ndarray,
    generation_seed: int,
    model_label: str,
) -> dict[str, Any]:
    """Decode neural heads to a plan-v1 candidate. No clamping or fallback occurs."""
    if not 0 <= int(category_index) < len(CATEGORIES):
        raise ValueError("Category head returned an invalid index.")
    category = CATEGORIES[int(category_index)]
    duration = decode_numeric("effect.duration", float(numeric_outputs[FIELD_INDEX["effect.duration"]]))
    if duration is None:
        duration = None

    components: list[dict[str, Any]] = []
    property_keys = {
        "core": ("radius",),
        "ring": ("radius", "endRadius", "thickness"),
        "lightning": ("count", "length", "segments", "jitter"),
        "particles": ("count", "speed", "size", "gravity"),
    }
    for component_type in COMPONENT_TYPES:
        if float(component_probabilities[COMPONENT_INDEX[component_type]]) < 0.5:
            continue
        start_fraction = decode_numeric(f"{component_type}.start_fraction", float(numeric_outputs[FIELD_INDEX[f"{component_type}.start_fraction"]]))
        duration_fraction = decode_numeric(f"{component_type}.duration_fraction", float(numeric_outputs[FIELD_INDEX[f"{component_type}.duration_fraction"]]))
        position = [decode_numeric(f"{component_type}.position.{axis}", float(numeric_outputs[FIELD_INDEX[f"{component_type}.position.{axis}"]])) for axis in "xyz"]
        properties: dict[str, Any] = {}
        for key in property_keys[component_type]:
            properties[key] = decode_numeric(f"{component_type}.{key}", float(numeric_outputs[FIELD_INDEX[f"{component_type}.{key}"]]))
        channels = [float(numeric_outputs[FIELD_INDEX[f"{component_type}.color.{channel}"]]) for channel in ("r", "g", "b")]
        color = "#" + "".join(_raw_hex_channel(channel) for channel in channels)
        try:
            start = None if start_fraction is None or duration is None else float(start_fraction) * float(duration)
            component_duration = None if duration_fraction is None or duration is None else float(duration_fraction) * float(duration)
        except (TypeError, ValueError, OverflowError):
            start = component_duration = None
        components.append(
            {
                "id": component_type,
                "type": component_type,
                "color": color,
                "position": position,
                "start": start,
                "duration": component_duration,
                "properties": properties,
            }
        )

    return {
        "schemaVersion": "1.0",
        "name": f"Neural {category} · {model_label[:24]}",
        "effectType": "radial-burst",
        "duration": duration,
        "seed": int(generation_seed) & 0xFFFFFFFF,
        "constraints": dict(DEFAULT_CONSTRAINTS),
        "components": components,
    }


def _raw_hex_channel(normalized: float) -> str:
    if not math.isfinite(normalized):
        return "NaN"
    value = int(round(normalized * 255.0))
    if value < 0:
        return f"-{abs(value):02x}"
    return f"{value:02x}"


def parse_json_document(text: str) -> tuple[Any | None, str | None]:
    if len(text.encode("utf-8")) > 64 * 1024:
        return None, "Plan exceeds the 64 KiB input limit."
    try:
        return json.loads(text), None
    except (json.JSONDecodeError, UnicodeError) as error:
        return None, f"Invalid JSON: {error}"


def extract_category_from_effect(plan: dict[str, Any]) -> str:
    """A conservative default for human feedback; the user can override it."""
    component_types = {item.get("type") for item in plan.get("components", []) if isinstance(item, dict)}
    if "lightning" in component_types and "particles" in component_types and "ring" in component_types:
        return "layered-effect"
    if "lightning" in component_types:
        return "lightning"
    if "ring" in component_types and "particles" in component_types:
        return "shockwave"
    if "ring" in component_types:
        return "magical-aura"
    if "particles" in component_types:
        return "particle-burst"
    return "explosion"
