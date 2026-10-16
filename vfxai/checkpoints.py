"""Safe, local-only NumPy checkpoint persistence (no pickle/object arrays)."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .config import DEFAULT_HIDDEN_SIZE, DEFAULT_INIT_SEED
from .model import Adam, PARAMETER_NAMES, StructuredMLP
from .paths import CHECKPOINTS_DIR, ensure_state_dirs

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_checkpoint_id(checkpoint_id: str) -> str:
    if not isinstance(checkpoint_id, str) or not _ID_RE.fullmatch(checkpoint_id):
        raise ValueError("Checkpoint id contains unsupported characters.")
    return checkpoint_id


def checkpoint_paths(checkpoint_id: str) -> tuple[Path, Path]:
    checkpoint_id = validate_checkpoint_id(checkpoint_id)
    return CHECKPOINTS_DIR / f"{checkpoint_id}.npz", CHECKPOINTS_DIR / f"{checkpoint_id}.json"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def save_checkpoint(
    checkpoint_id: str,
    model: StructuredMLP,
    metadata: dict[str, Any],
    optimizer: Adam | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    ensure_state_dirs()
    checkpoint_id = validate_checkpoint_id(checkpoint_id)
    weights_path, metadata_path = checkpoint_paths(checkpoint_id)
    if not overwrite and (weights_path.exists() or metadata_path.exists()):
        raise FileExistsError(f"Checkpoint already exists: {checkpoint_id}")

    complete = {
        **metadata,
        "checkpoint_id": checkpoint_id,
        "created_at": utc_now(),
        "model": model.architecture,
        "model_seed": int(model.seed),
        "checkpoint_format": 1,
        "weights_file": weights_path.name,
    }
    arrays: dict[str, np.ndarray] = {
        f"param__{name}": np.asarray(model.params[name], dtype=np.float32) for name in PARAMETER_NAMES
    }
    if optimizer is not None:
        arrays.update(
            {
                f"adam_m__{name}": np.asarray(optimizer.m[name], dtype=np.float32)
                for name in PARAMETER_NAMES
            }
        )
        arrays.update(
            {
                f"adam_v__{name}": np.asarray(optimizer.v[name], dtype=np.float32)
                for name in PARAMETER_NAMES
            }
        )
        complete["optimizer"] = {
            "name": "Adam",
            "learning_rate": optimizer.learning_rate,
            "beta1": optimizer.beta1,
            "beta2": optimizer.beta2,
            "epsilon": optimizer.epsilon,
            "steps": optimizer.steps,
        }

    temporary_weights = weights_path.with_name(weights_path.name + f".{os.getpid()}.tmp")
    with temporary_weights.open("wb") as stream:
        np.savez_compressed(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_weights, weights_path)
    atomic_write_json(metadata_path, complete)
    return complete


def load_checkpoint(checkpoint_id: str) -> tuple[StructuredMLP, dict[str, Any], Adam | None]:
    weights_path, metadata_path = checkpoint_paths(checkpoint_id)
    if not weights_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found or incomplete: {checkpoint_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    architecture = metadata.get("model", {})
    if architecture.get("version") != "structured-mlp-v1":
        raise ValueError("Unsupported checkpoint architecture.")
    seed = int(metadata.get("model_seed", DEFAULT_INIT_SEED))
    hidden_size = int(architecture.get("hidden_size", DEFAULT_HIDDEN_SIZE))
    model = StructuredMLP(seed=seed, hidden_size=hidden_size)
    with np.load(weights_path, allow_pickle=False) as archive:
        expected_parameters = {f"param__{name}" for name in PARAMETER_NAMES}
        if not expected_parameters.issubset(set(archive.files)):
            raise ValueError("Checkpoint is missing model parameters.")
        model.load_parameters({name: archive[f"param__{name}"] for name in PARAMETER_NAMES})
        optimizer: Adam | None = None
        optimizer_meta = metadata.get("optimizer")
        m_keys = {f"adam_m__{name}" for name in PARAMETER_NAMES}
        v_keys = {f"adam_v__{name}" for name in PARAMETER_NAMES}
        if optimizer_meta and m_keys.issubset(set(archive.files)) and v_keys.issubset(set(archive.files)):
            optimizer = Adam(float(optimizer_meta["learning_rate"]))
            state = {
                "learning_rate": float(optimizer_meta["learning_rate"]),
                "beta1": float(optimizer_meta.get("beta1", 0.9)),
                "beta2": float(optimizer_meta.get("beta2", 0.999)),
                "epsilon": float(optimizer_meta.get("epsilon", 1e-8)),
                "steps": int(optimizer_meta.get("steps", 0)),
                "m": {name: archive[f"adam_m__{name}"] for name in PARAMETER_NAMES},
                "v": {name: archive[f"adam_v__{name}"] for name in PARAMETER_NAMES},
            }
            optimizer.load_state_dict(state, model.params)
    return model, metadata, optimizer


def ensure_random_checkpoint(seed: int = DEFAULT_INIT_SEED, hidden_size: int = DEFAULT_HIDDEN_SIZE) -> tuple[str, StructuredMLP, dict[str, Any]]:
    checkpoint_id = f"random-seed-{int(seed)}-h{int(hidden_size)}"
    weights_path, metadata_path = checkpoint_paths(checkpoint_id)
    if weights_path.is_file() and metadata_path.is_file():
        model, metadata, _ = load_checkpoint(checkpoint_id)
        if model.hidden_size != hidden_size or model.seed != seed or metadata.get("kind") != "untrained-random-initialization":
            raise ValueError(f"Existing baseline checkpoint does not match expected initialization: {checkpoint_id}")
        return checkpoint_id, model, metadata
    model = StructuredMLP(seed=seed, hidden_size=hidden_size)
    metadata = save_checkpoint(
        checkpoint_id,
        model,
        {
            "kind": "untrained-random-initialization",
            "trained": False,
            "dataset_version": None,
            "notes": "Random initialization only. No example, pretrained parameter, prompt rule, or deterministic fallback is used.",
        },
    )
    return checkpoint_id, model, metadata


def update_checkpoint_metadata(checkpoint_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    weights_path, metadata_path = checkpoint_paths(checkpoint_id)
    if not weights_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(updates)
    atomic_write_json(metadata_path, metadata)
    return metadata


def list_checkpoints() -> list[dict[str, Any]]:
    ensure_state_dirs()
    checkpoints: list[dict[str, Any]] = []
    for metadata_path in CHECKPOINTS_DIR.glob("*.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            weights_path = CHECKPOINTS_DIR / metadata.get("weights_file", "")
            if not weights_path.is_file():
                continue
            checkpoints.append(
                {
                    "checkpoint_id": metadata.get("checkpoint_id", metadata_path.stem),
                    "kind": metadata.get("kind", "unknown"),
                    "trained": bool(metadata.get("trained", metadata.get("kind") == "trained")),
                    "created_at": metadata.get("created_at"),
                    "model": metadata.get("model", {}),
                    "dataset_version": metadata.get("dataset_version"),
                    "run_id": metadata.get("run_id"),
                    "epoch": metadata.get("epoch"),
                    "validation": metadata.get("validation"),
                    "test": metadata.get("test"),
                    "path": str(weights_path),
                    "size_bytes": weights_path.stat().st_size,
                }
            )
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    checkpoints.sort(key=lambda item: (item.get("created_at") or "", item["checkpoint_id"]), reverse=True)
    return checkpoints
