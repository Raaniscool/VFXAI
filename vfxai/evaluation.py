"""Held-out metrics for the structured neural outputs; no artistic-quality score."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from .config import CATEGORIES, COMPONENT_TYPES
from .contracts import analyze_plan, encode_plan_targets, make_candidate_plan
from .model import StructuredMLP
from .vectorizer import encode_prompts


def evaluate_model(
    model: StructuredMLP,
    records: list[dict[str, Any]],
    split: str,
    checkpoint_id: str,
    include_predictions: bool = False,
) -> dict[str, Any]:
    selected = [record for record in records if record.get("split") == split]
    if not selected:
        raise ValueError(f"No examples are assigned to the {split!r} split.")
    prompts = [record["prompt"] for record in selected]
    features = encode_prompts(prompts)
    targets = [encode_plan_targets(row["plan"], row["category"]) for row in selected]
    category_targets = np.asarray([item[0] for item in targets], dtype=np.int64)
    component_targets = np.stack([item[1] for item in targets]).astype(np.float32)
    numeric_targets = np.stack([item[2] for item in targets]).astype(np.float32)
    numeric_mask = np.stack([item[3] for item in targets]).astype(np.float32)

    losses = model.loss(features, category_targets, component_targets, numeric_targets, numeric_mask)
    output = model.predict(features)
    predicted_categories = output.category_probabilities.argmax(axis=1)
    predicted_components = (output.component_probabilities >= 0.5).astype(np.float32)
    category_correct = predicted_categories == category_targets
    component_exact = np.all(predicted_components == component_targets, axis=1)
    numeric_abs_error = np.abs(output.numeric_values - numeric_targets) * numeric_mask
    numeric_count = max(1.0, float(numeric_mask.sum()))
    numeric_mae_normalized = float(numeric_abs_error.sum() / numeric_count)

    true_positive = float((predicted_components * component_targets).sum())
    false_positive = float((predicted_components * (1.0 - component_targets)).sum())
    false_negative = float(((1.0 - predicted_components) * component_targets).sum())
    precision = true_positive / max(1.0, true_positive + false_positive)
    recall = true_positive / max(1.0, true_positive + false_negative)
    f1 = 2.0 * precision * recall / max(1e-12, precision + recall)

    valid_count = 0
    issue_counts: Counter[str] = Counter()
    prediction_rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        category_index = int(predicted_categories[index])
        seed = int(row.get("seed", index)) & 0xFFFFFFFF
        candidate = make_candidate_plan(
            category_index,
            output.component_probabilities[index],
            output.numeric_values[index],
            seed,
            checkpoint_id,
        )
        reason = analyze_plan(candidate)
        valid_count += int(reason["ok"])
        for issue in reason["issues"]:
            issue_counts[issue["code"]] += 1
        if include_predictions:
            prediction_rows.append(
                {
                    "record_id": row["id"],
                    "prompt": row["prompt"],
                    "expected_category": row["category"],
                    "predicted_category": CATEGORIES[category_index],
                    "category_probabilities": [float(value) for value in output.category_probabilities[index]],
                    "expected_components": [COMPONENT_TYPES[i] for i, value in enumerate(component_targets[index]) if value >= 0.5],
                    "component_probabilities": [float(value) for value in output.component_probabilities[index]],
                    "numeric_outputs_normalized": [float(value) for value in output.numeric_values[index]],
                    "candidate_plan": candidate,
                    "validation": reason,
                }
            )

    metrics: dict[str, Any] = {
        "split": split,
        "checkpoint_id": checkpoint_id,
        "example_count": len(selected),
        "loss": losses,
        "category_accuracy": float(category_correct.mean()),
        "component_exact_match": float(component_exact.mean()),
        "component_precision": float(precision),
        "component_recall": float(recall),
        "component_f1": float(f1),
        "numeric_mae_normalized": numeric_mae_normalized,
        "valid_plan_count": valid_count,
        "valid_plan_rate": valid_count / len(selected),
        "validation_issue_counts": dict(issue_counts),
        "quality_note": "These are schema/resource and target-agreement metrics on the named split. They do not measure visual appeal, Roblox Studio behavior, or artistic quality.",
    }
    if include_predictions:
        metrics["predictions"] = prediction_rows
    return metrics


def save_predictions(path: Path, predictions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in predictions:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)
