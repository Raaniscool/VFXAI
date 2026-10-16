"""First-run preparation for local data and an inspectable random baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .checkpoints import ensure_random_checkpoint, update_checkpoint_metadata
from .config import (
    DEFAULT_DATASET_COUNT,
    DEFAULT_DATASET_SEED,
    DEFAULT_HIDDEN_SIZE,
    DEFAULT_INIT_SEED,
)
from .dataset import generate_dataset, get_active_dataset_path, load_dataset, set_active_dataset
from .evaluation import evaluate_model, save_predictions
from .paths import DATASETS_DIR, EXPERIMENTS_DIR, ensure_state_dirs


def initialize_project(
    dataset_count: int = DEFAULT_DATASET_COUNT,
    dataset_seed: int = DEFAULT_DATASET_SEED,
    init_seed: int = DEFAULT_INIT_SEED,
    hidden_size: int = DEFAULT_HIDDEN_SIZE,
) -> dict[str, Any]:
    ensure_state_dirs()
    dataset_path = get_active_dataset_path()
    if dataset_path is None:
        default_path = DATASETS_DIR / f"synthetic-v1-seed-{int(dataset_seed) & 0xFFFFFFFF}.jsonl"
        if default_path.exists():
            dataset_path = default_path
        else:
            dataset_path, _ = generate_dataset(dataset_count, dataset_seed, default_path)
        set_active_dataset(dataset_path)
    records = load_dataset(dataset_path)

    checkpoint_id, model, metadata = ensure_random_checkpoint(init_seed, hidden_size)
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    if not metadata.get("test") or metadata.get("evaluation_dataset_sha256") != dataset_hash:
        baseline_test = evaluate_model(model, records, "test", checkpoint_id, include_predictions=True)
        baseline_validation = evaluate_model(model, records, "validation", checkpoint_id)
        update_checkpoint_metadata(
            checkpoint_id,
            {
                "validation": baseline_validation,
                "test": {key: value for key, value in baseline_test.items() if key != "predictions"},
                "dataset_file": dataset_path.name,
                "evaluation_dataset_sha256": dataset_hash,
                "dataset_seed": metadata.get("dataset_seed", dataset_seed),
                "dataset_version": None,
            },
        )
        prediction_dir = EXPERIMENTS_DIR / f"baseline-{checkpoint_id}"
        save_predictions(prediction_dir / "untrained-test-predictions.jsonl", baseline_test["predictions"])
        (prediction_dir / "evaluation.json").write_text(
            json.dumps({key: value for key, value in baseline_test.items() if key != "predictions"}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {
        "dataset": {
            "path": str(dataset_path),
            "count": len(records),
            "split_counts": {split: sum(row["split"] == split for row in records) for split in ("train", "validation", "test")},
        },
        "baseline_checkpoint": checkpoint_id,
        "model": model.architecture,
        "trained": bool(metadata.get("trained", False)),
        "state_directory": str(dataset_path.parent.parent),
        "message": "Local data and a seeded random-weight baseline are ready. The baseline has not been trained.",
    }
