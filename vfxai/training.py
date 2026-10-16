"""Local training loop, checkpoint comparison, and resumable experiment records."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from .checkpoints import (
    atomic_write_json,
    ensure_random_checkpoint,
    load_checkpoint,
    save_checkpoint,
    update_checkpoint_metadata,
    utc_now,
)
from .config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_EPOCHS,
    DEFAULT_HIDDEN_SIZE,
    DEFAULT_LEARNING_RATE,
    DEFAULT_TRAIN_SEED,
)
from .contracts import encode_plan_targets
from .dataset import get_active_dataset_path, load_dataset, load_manifest
from .evaluation import evaluate_model, save_predictions
from .feedback import approved_training_records
from .model import Adam, StructuredMLP
from .paths import EXPERIMENTS_DIR, LOGS_DIR, RUNTIME_DIR, ensure_state_dirs
from .vectorizer import encode_prompts


def _as_json_float(value: Any) -> float:
    number = float(value)
    if not np.isfinite(number):
        raise ValueError("Refusing to write a non-finite metric.")
    return number


def _dataset_version(base_path: Path, feedback_records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    digest.update(base_path.read_bytes())
    for record in sorted(feedback_records, key=lambda item: item["id"]):
        digest.update(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return digest.hexdigest()


def _status_write(status_path: Path, status: dict[str, Any]) -> None:
    ensure_state_dirs()
    atomic_write_json(status_path, status)


def _read_control(control_path: Path) -> str:
    try:
        value = json.loads(control_path.read_text(encoding="utf-8")).get("action", "run")
        return value if value in {"run", "pause", "stop"} else "run"
    except (OSError, ValueError, json.JSONDecodeError):
        return "run"


def _write_control(control_path: Path, action: str) -> None:
    atomic_write_json(control_path, {"action": action, "updated_at": utc_now()})


def _make_training_arrays(records: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not records:
        raise ValueError("Training split is empty.")
    features = encode_prompts([row["prompt"] for row in records])
    targets = [encode_plan_targets(row["plan"], row["category"]) for row in records]
    return (
        features,
        np.asarray([item[0] for item in targets], dtype=np.int64),
        np.stack([item[1] for item in targets]).astype(np.float32),
        np.stack([item[2] for item in targets]).astype(np.float32),
        np.stack([item[3] for item in targets]).astype(np.float32),
    )


def _loss_average(losses: list[dict[str, float]], sizes: list[int]) -> dict[str, float]:
    count = max(1, sum(sizes))
    return {
        key: _as_json_float(sum(loss[key] * size for loss, size in zip(losses, sizes)) / count)
        for key in ("category", "components", "numeric", "total")
    }


def _weight_delta(before: dict[str, np.ndarray], after: dict[str, np.ndarray]) -> float:
    total = 0.0
    for name in before:
        difference = np.asarray(after[name], dtype=np.float64) - np.asarray(before[name], dtype=np.float64)
        total += float(np.square(difference).sum())
    return float(np.sqrt(total))


def _new_run_id() -> str:
    return time.strftime("run-%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:6]


def train_experiment(
    dataset_path: Path | None = None,
    epochs: int = DEFAULT_EPOCHS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    seed: int = DEFAULT_TRAIN_SEED,
    hidden_size: int = DEFAULT_HIDDEN_SIZE,
    include_feedback: bool = False,
    resume_checkpoint: str | None = None,
    status_path: Path | None = None,
    control_path: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    if not 1 <= int(epochs) <= 1000:
        raise ValueError("epochs must be between 1 and 1,000.")
    if not 1 <= int(batch_size) <= 128:
        raise ValueError("batch_size must be between 1 and 128.")
    if not 1e-5 <= float(learning_rate) <= 0.1:
        raise ValueError("learning_rate must be between 0.00001 and 0.1.")
    ensure_state_dirs()
    dataset_path = Path(dataset_path) if dataset_path else get_active_dataset_path()
    if dataset_path is None:
        raise FileNotFoundError("No dataset is active. Generate the synthetic dataset first.")
    dataset_path = dataset_path.resolve()
    status_path = Path(status_path) if status_path else RUNTIME_DIR / "training.json"
    control_path = Path(control_path) if control_path else RUNTIME_DIR / "training-control.json"
    run_id = run_id or _new_run_id()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", run_id):
        raise ValueError("run_id may contain only letters, numbers, underscores, and hyphens.")
    experiment_path = EXPERIMENTS_DIR / f"{run_id}.json"
    experiment_dir = EXPERIMENTS_DIR / run_id
    experiment_dir.mkdir(parents=True, exist_ok=True)

    base_records = load_dataset(dataset_path)
    feedback_records, skipped_feedback = approved_training_records(base_records) if include_feedback else ([], [])
    dataset_version = _dataset_version(dataset_path, feedback_records)
    all_records = sorted(base_records + feedback_records, key=lambda item: item["id"])
    train_records = [row for row in all_records if row["split"] == "train"]
    validation_records = [row for row in base_records if row["split"] == "validation"]
    test_records = [row for row in base_records if row["split"] == "test"]
    features, category_targets, component_targets, numeric_targets, numeric_mask = _make_training_arrays(train_records)

    status: dict[str, Any] = {
        "run_id": run_id,
        "pid": os.getpid(),
        "status": "starting",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "dataset_file": dataset_path.name,
        "dataset_version": dataset_version,
        "train_examples": len(train_records),
        "validation_examples": len(validation_records),
        "test_examples": len(test_records),
        "feedback_examples": len(feedback_records),
        "skipped_feedback": skipped_feedback,
        "epoch": 0,
        "target_epochs": int(epochs),
        "batch": 0,
        "batches_in_epoch": int(np.ceil(len(train_records) / batch_size)),
        "progress": 0.0,
        "last_loss": None,
        "message": "Preparing model and held-out evaluation.",
    }
    _status_write(status_path, status)
    _write_control(control_path, "run")

    started_clock = time.monotonic()
    epoch_history: list[dict[str, Any]] = []
    baseline_checkpoint: str | None = None
    best_checkpoint: str | None = None
    best_validation_loss = float("inf")
    start_epoch = 0
    start_batch = 0
    shuffle_seed = int(seed)
    initial_params: dict[str, np.ndarray]
    resumed_metadata: dict[str, Any] | None = None

    try:
        if resume_checkpoint:
            model, resumed_metadata, optimizer = load_checkpoint(resume_checkpoint)
            if resumed_metadata.get("kind") != "trained" or optimizer is None:
                raise ValueError("Only a trained checkpoint containing optimizer state can be resumed.")
            if resumed_metadata.get("dataset_version") != dataset_version:
                raise ValueError("This checkpoint was trained on a different dataset version. Start a new experiment to preserve reproducibility.")
            if model.hidden_size != int(resumed_metadata.get("model", {}).get("hidden_size", -1)):
                raise ValueError("Checkpoint hidden size is inconsistent.")
            optimizer.learning_rate = float(learning_rate)
            start_epoch = int(resumed_metadata.get("resume_epoch", resumed_metadata.get("epoch", 0)))
            start_batch = int(resumed_metadata.get("resume_batch", 0))
            shuffle_seed = int(resumed_metadata.get("training_seed", seed))
            baseline_checkpoint = resumed_metadata.get("baseline_checkpoint")
            best_checkpoint = resumed_metadata.get("best_checkpoint") or resume_checkpoint
            if best_checkpoint:
                try:
                    _, best_metadata, _ = load_checkpoint(best_checkpoint)
                    best_validation_loss = float(best_metadata.get("validation", {}).get("loss", {}).get("total", float("inf")))
                except (OSError, ValueError, KeyError):
                    best_validation_loss = float("inf")
            old_run_id = resumed_metadata.get("run_id")
            if old_run_id:
                old_experiment = EXPERIMENTS_DIR / f"{old_run_id}.json"
                try:
                    old_data = json.loads(old_experiment.read_text(encoding="utf-8"))
                    epoch_history = list(old_data.get("epoch_history", []))
                except (OSError, ValueError, json.JSONDecodeError):
                    pass
            initial_params = {name: value.copy() for name, value in model.params.items()}
            status["resumed_from"] = resume_checkpoint
            status["message"] = "Resuming from the selected trained checkpoint."
        else:
            if not 16 <= int(hidden_size) <= 128:
                raise ValueError("hidden_size must be between 16 and 128.")
            baseline_checkpoint, model, _ = ensure_random_checkpoint(seed=seed, hidden_size=hidden_size)
            initial_params = {name: value.copy() for name, value in model.params.items()}
            optimizer = Adam(learning_rate)
            optimizer.initialize_shapes(model.params)
            baseline_test = evaluate_model(model, base_records, "test", baseline_checkpoint, include_predictions=True)
            baseline_validation = evaluate_model(model, base_records, "validation", baseline_checkpoint)
            update_checkpoint_metadata(
                baseline_checkpoint,
                {
                    "validation": baseline_validation,
                    "test": {key: value for key, value in baseline_test.items() if key != "predictions"},
                    "evaluation_dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
                    "dataset_file": dataset_path.name,
                },
            )
            save_predictions(experiment_dir / "untrained-test-predictions.jsonl", baseline_test["predictions"])
            status["baseline_checkpoint"] = baseline_checkpoint
            status["baseline_test"] = {key: value for key, value in baseline_test.items() if key != "predictions"}

        status.update(
            {
                "status": "running",
                "updated_at": utc_now(),
                "message": "Training the randomly initialized MLP with backpropagation and Adam.",
                "checkpoint": resume_checkpoint,
                "baseline_checkpoint": baseline_checkpoint,
            }
        )
        _status_write(status_path, status)

        batches = int(np.ceil(len(train_records) / batch_size))
        stopped = False
        for epoch_index in range(start_epoch, int(epochs)):
            permutation = np.random.default_rng((shuffle_seed + epoch_index * 1009) & 0xFFFFFFFF).permutation(len(train_records))
            batch_losses: list[dict[str, float]] = []
            batch_sizes: list[int] = []
            first_batch = start_batch if epoch_index == start_epoch else 0
            for batch_index in range(first_batch, batches):
                action = _read_control(control_path)
                while action == "pause":
                    status.update(
                        {
                            "status": "paused",
                            "updated_at": utc_now(),
                            "epoch": epoch_index + 1,
                            "batch": batch_index,
                            "progress": min(1.0, (epoch_index + batch_index / batches) / max(1, epochs)),
                            "message": "Paused by user; model and optimizer are unchanged until resumed.",
                        }
                    )
                    _status_write(status_path, status)
                    time.sleep(0.25)
                    action = _read_control(control_path)
                if action == "stop":
                    stopped = True
                    break

                indices = permutation[batch_index * batch_size : min((batch_index + 1) * batch_size, len(train_records))]
                batch_loss = model.train_batch(
                    features[indices],
                    category_targets[indices],
                    component_targets[indices],
                    numeric_targets[indices],
                    numeric_mask[indices],
                    optimizer,
                )
                size = int(len(indices))
                batch_losses.append(batch_loss)
                batch_sizes.append(size)
                elapsed = time.monotonic() - started_clock
                status.update(
                    {
                        "status": "running",
                        "updated_at": utc_now(),
                        "epoch": epoch_index + 1,
                        "target_epochs": int(epochs),
                        "batch": batch_index + 1,
                        "batches_in_epoch": batches,
                        "progress": min(1.0, ((epoch_index + (batch_index + 1) / batches) / max(1, epochs))),
                        "elapsed_seconds": round(elapsed, 2),
                        "last_loss": {key: _as_json_float(value) for key, value in batch_loss.items()},
                        "message": f"Epoch {epoch_index + 1}/{epochs}, batch {batch_index + 1}/{batches}.",
                    }
                )
                _status_write(status_path, status)

            if stopped:
                checkpoint_id = f"{run_id}-stopped-e{epoch_index + 1:03d}-b{max(first_batch, batch_index):03d}"
                checkpoint_meta = save_checkpoint(
                    checkpoint_id,
                    model,
                    {
                        "kind": "trained",
                        "trained": True,
                        "run_id": run_id,
                        "dataset_version": dataset_version,
                        "dataset_file": dataset_path.name,
                        "baseline_checkpoint": baseline_checkpoint,
                        "best_checkpoint": best_checkpoint,
                        "epoch": epoch_index + 1,
                        "resume_epoch": epoch_index,
                        "resume_batch": min(batches, max(first_batch, batch_index)),
                        "target_epochs": int(epochs),
                        "training_seed": shuffle_seed,
                        "train_examples": len(train_records),
                        "validation_examples": len(validation_records),
                        "test_examples": len(test_records),
                        "include_feedback": bool(include_feedback),
                        "optimizer_note": "Optimizer moments are saved so a user can explicitly resume this run.",
                    },
                    optimizer,
                )
                if batch_losses:
                    partial_loss = _loss_average(batch_losses, batch_sizes)
                else:
                    partial_loss = None
                status.update(
                    {
                        "status": "stopped",
                        "updated_at": utc_now(),
                        "checkpoint": checkpoint_id,
                        "checkpoint_metadata": checkpoint_meta,
                        "progress": min(1.0, ((epoch_index + min(batches, max(first_batch, batch_index)) / batches) / max(1, epochs))),
                        "message": "Stopped by user. The partial checkpoint and optimizer state were preserved.",
                        "last_epoch_partial_loss": partial_loss,
                    }
                )
                _status_write(status_path, status)
                break

            train_loss = _loss_average(batch_losses, batch_sizes)
            validation = evaluate_model(model, base_records, "validation", f"{run_id}-epoch-{epoch_index + 1:03d}")
            checkpoint_id = f"{run_id}-epoch-{epoch_index + 1:03d}"
            improved = float(validation["loss"]["total"]) < best_validation_loss
            checkpoint_meta = save_checkpoint(
                checkpoint_id,
                model,
                {
                    "kind": "trained",
                    "trained": True,
                    "run_id": run_id,
                    "dataset_version": dataset_version,
                    "dataset_file": dataset_path.name,
                    "baseline_checkpoint": baseline_checkpoint,
                    "best_checkpoint": checkpoint_id if improved else best_checkpoint,
                    "epoch": epoch_index + 1,
                    "resume_epoch": epoch_index + 1,
                    "resume_batch": 0,
                    "target_epochs": int(epochs),
                    "training_seed": shuffle_seed,
                    "validation": validation,
                    "train_loss": train_loss,
                    "train_examples": len(train_records),
                    "validation_examples": len(validation_records),
                    "test_examples": len(test_records),
                    "include_feedback": bool(include_feedback),
                    "feedback_examples": len(feedback_records),
                },
                optimizer,
            )
            if improved:
                best_validation_loss = float(validation["loss"]["total"])
                best_checkpoint = checkpoint_id
            epoch_report = {
                "epoch": epoch_index + 1,
                "train_loss": train_loss,
                "validation": validation,
                "checkpoint": checkpoint_id,
                "best_checkpoint": best_checkpoint,
                "new_best": improved,
                "elapsed_seconds": round(time.monotonic() - started_clock, 2),
            }
            epoch_history.append(epoch_report)
            status.update(
                {
                    "status": "running",
                    "updated_at": utc_now(),
                    "epoch": epoch_index + 1,
                    "batch": batches,
                    "progress": min(1.0, (epoch_index + 1) / max(1, epochs)),
                    "checkpoint": checkpoint_id,
                    "best_checkpoint": best_checkpoint,
                    "last_loss": train_loss,
                    "validation": validation,
                    "message": f"Finished epoch {epoch_index + 1}/{epochs}; checkpoint saved.",
                }
            )
            _status_write(status_path, status)
            _write_experiment(
                experiment_path,
                {
                    "run_id": run_id,
                    "status": "running",
                    "started_at": status["started_at"],
                    "updated_at": utc_now(),
                    "dataset_file": dataset_path.name,
                    "dataset_version": dataset_version,
                    "baseline_checkpoint": baseline_checkpoint,
                    "best_checkpoint": best_checkpoint,
                    "target_epochs": int(epochs),
                    "epochs_completed": epoch_index + 1,
                    "train_examples": len(train_records),
                    "validation_examples": len(validation_records),
                    "test_examples": len(test_records),
                    "feedback_examples": len(feedback_records),
                    "skipped_feedback": skipped_feedback,
                    "epoch_history": epoch_history,
                    "checkpoint": checkpoint_id,
                },
            )
            start_batch = 0

        final_checkpoint = status.get("checkpoint") or best_checkpoint
        if not final_checkpoint:
            raise RuntimeError("Training ended without a saved checkpoint.")
        if best_checkpoint:
            best_model, best_metadata, _ = load_checkpoint(best_checkpoint)
        else:
            best_model, best_metadata, _ = load_checkpoint(final_checkpoint)
            best_checkpoint = final_checkpoint
        baseline_metrics: dict[str, Any] | None = None
        if baseline_checkpoint:
            baseline_model, _, _ = load_checkpoint(baseline_checkpoint)
            baseline_metrics_full = evaluate_model(baseline_model, base_records, "test", baseline_checkpoint, include_predictions=True)
            baseline_metrics = {key: value for key, value in baseline_metrics_full.items() if key != "predictions"}
            save_predictions(experiment_dir / "untrained-test-predictions.jsonl", baseline_metrics_full["predictions"])
        trained_metrics_full = evaluate_model(best_model, base_records, "test", best_checkpoint, include_predictions=True)
        trained_metrics = {key: value for key, value in trained_metrics_full.items() if key != "predictions"}
        save_predictions(experiment_dir / "trained-test-predictions.jsonl", trained_metrics_full["predictions"])

        comparison = _compare_metrics(baseline_metrics, trained_metrics)
        delta = _weight_delta(initial_params, best_model.params)
        run_status = "stopped" if status.get("status") == "stopped" else "completed"
        result = {
            "run_id": run_id,
            "status": run_status,
            "started_at": status["started_at"],
            "finished_at": utc_now(),
            "elapsed_seconds": round(time.monotonic() - started_clock, 2),
            "dataset_file": dataset_path.name,
            "dataset_version": dataset_version,
            "dataset_manifest": load_manifest(dataset_path),
            "model": best_model.architecture,
            "initialization_seed": int(seed) if not resume_checkpoint else int(resumed_metadata.get("model_seed", seed)),
            "training_config": {
                "target_epochs": int(epochs),
                "epochs_completed": int(status.get("epoch", 0)),
                "batch_size": int(batch_size),
                "learning_rate": float(learning_rate),
                "seed": int(shuffle_seed),
                "hidden_size": best_model.hidden_size,
                "include_feedback": bool(include_feedback),
            },
            "train_examples": len(train_records),
            "validation_examples": len(validation_records),
            "test_examples": len(test_records),
            "feedback_examples": len(feedback_records),
            "skipped_feedback": skipped_feedback,
            "baseline_checkpoint": baseline_checkpoint,
            "best_checkpoint": best_checkpoint,
            "final_checkpoint": final_checkpoint,
            "weight_delta_l2_from_run_start": delta,
            "epoch_history": epoch_history,
            "baseline_test": baseline_metrics,
            "trained_test": trained_metrics,
            "test_comparison": comparison,
            "artistic_quality_evaluated": False,
            "prediction_files": [
                "untrained-test-predictions.jsonl",
                "trained-test-predictions.jsonl",
            ],
            "notes": [
                "The baseline and trained checkpoint are evaluated against the same held-out test prompts.",
                "Test metrics are descriptive and are not used for gradient updates.",
                "Loss, category/component agreement, and plan validity do not measure visual appeal or Roblox Studio behavior.",
                "Failed and successful test candidates are both preserved in the prediction JSONL files.",
            ],
        }
        _write_experiment(experiment_path, result)
        if best_checkpoint:
            update_checkpoint_metadata(
                best_checkpoint,
                {
                    "test": trained_metrics,
                    "test_comparison": comparison,
                    "baseline_checkpoint": baseline_checkpoint,
                    "best_checkpoint": best_checkpoint,
                    "weight_delta_l2_from_run_start": delta,
                },
            )
        status.update(
            {
                "status": run_status,
                "updated_at": utc_now(),
                "progress": 1.0 if run_status == "completed" else status.get("progress", 0.0),
                "checkpoint": final_checkpoint,
                "best_checkpoint": best_checkpoint,
                "baseline_checkpoint": baseline_checkpoint,
                "trained_test": trained_metrics,
                "test_comparison": comparison,
                "experiment_file": str(experiment_path),
                "message": "Training completed; trained and untrained checkpoints were evaluated on the same held-out test prompts." if run_status == "completed" else "Training stopped; checkpoint saved and evaluated.",
            }
        )
        _status_write(status_path, status)
        return result
    except Exception as error:
        failed = {
            **status,
            "status": "failed",
            "updated_at": utc_now(),
            "message": f"Training failed: {type(error).__name__}: {error}",
        }
        _status_write(status_path, failed)
        _write_experiment(
            experiment_path,
            {
                "run_id": run_id,
                "status": "failed",
                "started_at": status.get("started_at"),
                "finished_at": utc_now(),
                "dataset_file": dataset_path.name,
                "dataset_version": dataset_version,
                "error": failed["message"],
                "epoch_history": epoch_history,
                "baseline_checkpoint": baseline_checkpoint,
                "best_checkpoint": best_checkpoint,
                "resumed_from": resume_checkpoint,
            },
        )
        raise


def _compare_metrics(baseline: dict[str, Any] | None, trained: dict[str, Any]) -> dict[str, Any]:
    if baseline is None:
        return {"available": False, "reason": "No matching random-initialization baseline checkpoint was supplied."}
    comparisons: dict[str, Any] = {}
    for key in ("category_accuracy", "component_exact_match", "component_f1", "numeric_mae_normalized", "valid_plan_rate"):
        before = float(baseline[key])
        after = float(trained[key])
        comparisons[key] = {"untrained": before, "trained": after, "delta_trained_minus_untrained": after - before}
    before_loss = float(baseline["loss"]["total"])
    after_loss = float(trained["loss"]["total"])
    comparisons["loss_total"] = {
        "untrained": before_loss,
        "trained": after_loss,
        "delta_trained_minus_untrained": after_loss - before_loss,
    }
    return {
        "available": True,
        "same_held_out_prompts": baseline["example_count"] == trained["example_count"],
        "baseline_checkpoint": baseline["checkpoint_id"],
        "trained_checkpoint": trained["checkpoint_id"],
        "metrics": comparisons,
        "interpretation": "These numeric differences describe held-out target agreement and validity only; no result is an artistic-quality judgment.",
    }


def _write_experiment(path: Path, payload: dict[str, Any]) -> None:
    ensure_state_dirs()
    atomic_write_json(path, payload)


def list_experiments(limit: int = 30) -> list[dict[str, Any]]:
    ensure_state_dirs()
    result: list[dict[str, Any]] = []
    for path in EXPERIMENTS_DIR.glob("run-*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result.append(
                {
                    "run_id": data.get("run_id", path.stem),
                    "status": data.get("status"),
                    "started_at": data.get("started_at"),
                    "finished_at": data.get("finished_at"),
                    "dataset_file": data.get("dataset_file"),
                    "dataset_version": data.get("dataset_version"),
                    "best_checkpoint": data.get("best_checkpoint"),
                    "baseline_checkpoint": data.get("baseline_checkpoint"),
                    "training_config": data.get("training_config"),
                    "baseline_test": data.get("baseline_test"),
                    "trained_test": data.get("trained_test"),
                    "test_comparison": data.get("test_comparison"),
                    "error": data.get("error"),
                    "path": str(path),
                }
            )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    result.sort(key=lambda item: (item.get("started_at") or "", item["run_id"]), reverse=True)
    return result[: max(1, min(int(limit), 100))]


def read_training_status(status_path: Path | None = None) -> dict[str, Any]:
    path = Path(status_path) if status_path else RUNTIME_DIR / "training.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "idle", "message": "No training run is active."}


def list_prediction_files() -> list[str]:
    files: list[str] = []
    if EXPERIMENTS_DIR.exists():
        for path in EXPERIMENTS_DIR.glob("run-*/**/*.jsonl"):
            try:
                files.append(str(path.relative_to(EXPERIMENTS_DIR)))
            except ValueError:
                continue
    return sorted(files, reverse=True)
