"""Neural inference and durable, local generation history."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .checkpoints import load_checkpoint
from .config import CATEGORIES, COMPONENT_TYPES, DEFAULT_INIT_SEED, INPUT_SIZE
from .contracts import make_candidate_plan, analyze_plan
from .paths import GENERATIONS_DIR, ensure_state_dirs
from .vectorizer import encode_prompt


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_number(value: float) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def generate_prediction(
    prompt: str,
    checkpoint_id: str,
    generation_seed: int | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Enter a non-empty prompt.")
    prompt = prompt.strip()
    if len(prompt) > 1000:
        raise ValueError("Prompt is limited to 1,000 characters.")
    generation_seed = int(generation_seed if generation_seed is not None else DEFAULT_INIT_SEED) & 0xFFFFFFFF
    model, metadata, _ = load_checkpoint(checkpoint_id)
    output = model.predict(encode_prompt(prompt))
    category_probabilities = output.category_probabilities[0]
    component_probabilities = output.component_probabilities[0]
    numeric_outputs = output.numeric_values[0]
    category_index = int(category_probabilities.argmax())
    candidate = make_candidate_plan(category_index, component_probabilities, numeric_outputs, generation_seed, checkpoint_id)
    validation = analyze_plan(candidate)
    category_confidences = [
        {"category": category, "probability": _safe_number(category_probabilities[index])}
        for index, category in enumerate(CATEGORIES)
    ]
    component_confidences = [
        {
            "component": component,
            "probability": _safe_number(component_probabilities[index]),
            "selected": bool(component_probabilities[index] >= 0.5),
        }
        for index, component in enumerate(COMPONENT_TYPES)
    ]
    raw_numeric = [_safe_number(value) for value in numeric_outputs]
    record = {
        "id": f"gen-{uuid.uuid4().hex[:16]}",
        "created_at": _utc_now(),
        "prompt": prompt,
        "checkpoint_id": checkpoint_id,
        "checkpoint_kind": metadata.get("kind", "unknown"),
        "model_trained": bool(metadata.get("trained", metadata.get("kind") == "trained")),
        "model_version": metadata.get("model", {}).get("version"),
        "feature_size": INPUT_SIZE,
        "generation_seed": generation_seed,
        "category": CATEGORIES[category_index],
        "confidence": category_confidences[category_index]["probability"],
        "category_probabilities": category_confidences,
        "component_probabilities": component_confidences,
        "numeric_outputs_normalized": raw_numeric,
        "candidate_plan": candidate,
        "validation": validation,
        "provenance": {
            "source": "neural-structured-prediction",
            "decoder": "deterministic adapter to plan-v1; it does not inspect prompt keywords or select stored examples",
            "random_initialization": not bool(metadata.get("trained", metadata.get("kind") == "trained")),
            "uses_procedural_fallback": False,
            "executes_generated_code": False,
        },
    }
    if persist:
        ensure_state_dirs()
        path = GENERATIONS_DIR / f"{record['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    return record


def generation_history(limit: int = 40) -> list[dict[str, Any]]:
    ensure_state_dirs()
    rows: list[dict[str, Any]] = []
    for path in GENERATIONS_DIR.glob("gen-*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            rows.append(row)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    rows.sort(key=lambda row: (row.get("created_at", ""), row.get("id", "")), reverse=True)
    return rows[: max(1, min(int(limit), 200))]


def get_generation(generation_id: str) -> dict[str, Any] | None:
    if not isinstance(generation_id, str) or not generation_id.startswith("gen-") or len(generation_id) != 20:
        return None
    path = GENERATIONS_DIR / f"{generation_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def compare_checkpoints(prompt: str, checkpoint_a: str, checkpoint_b: str, seed: int | None = None) -> dict[str, Any]:
    generation_seed = int(seed if seed is not None else DEFAULT_INIT_SEED) & 0xFFFFFFFF
    first = generate_prediction(prompt, checkpoint_a, generation_seed, persist=True)
    second = generate_prediction(prompt, checkpoint_b, generation_seed, persist=True)
    return {
        "prompt": prompt,
        "generation_seed": generation_seed,
        "checkpoint_a": first,
        "checkpoint_b": second,
        "same_seed": first["generation_seed"] == second["generation_seed"],
        "note": "Same prompt and seed; each checkpoint's raw heads and validity are shown separately. Invalid candidates are retained, not replaced.",
    }
