"""Command-line entry points used by the Windows batch launchers and local server."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .checkpoints import list_checkpoints, load_checkpoint
from .config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_DATASET_COUNT,
    DEFAULT_DATASET_SEED,
    DEFAULT_EPOCHS,
    DEFAULT_HIDDEN_SIZE,
    DEFAULT_INIT_SEED,
    DEFAULT_LEARNING_RATE,
    DEFAULT_TRAIN_SEED,
)
from .dataset import (
    generate_dataset,
    get_active_dataset_path,
    load_dataset,
    set_active_dataset,
)
from .evaluation import evaluate_model, save_predictions
from .paths import EXPERIMENTS_DIR, ensure_state_dirs
from .server import serve
from .setup import initialize_project
from .training import train_experiment


def _json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VFXAI local neural VFX plan lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Generate local synthetic data and the untrained baseline")
    init.add_argument("--dataset-count", type=int, default=DEFAULT_DATASET_COUNT)
    init.add_argument("--dataset-seed", type=int, default=DEFAULT_DATASET_SEED)
    init.add_argument("--init-seed", type=int, default=DEFAULT_INIT_SEED)
    init.add_argument("--hidden-size", type=int, default=DEFAULT_HIDDEN_SIZE)

    generate = subparsers.add_parser("generate-dataset", help="Generate a versioned local prompt/plan dataset")
    generate.add_argument("--count", type=int, default=DEFAULT_DATASET_COUNT)
    generate.add_argument("--seed", type=int, default=DEFAULT_DATASET_SEED)
    generate.add_argument("--output", type=Path)
    generate.add_argument("--activate", action=argparse.BooleanOptionalAction, default=True)

    train = subparsers.add_parser("train", help="Train the random-initialized MLP locally")
    train.add_argument("--dataset", type=Path)
    train.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    train.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    train.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    train.add_argument("--seed", type=int, default=DEFAULT_TRAIN_SEED)
    train.add_argument("--hidden-size", type=int, default=DEFAULT_HIDDEN_SIZE)
    train.add_argument("--include-feedback", action="store_true")
    train.add_argument("--resume")
    train.add_argument("--status-path", type=Path)
    train.add_argument("--control-path", type=Path)
    train.add_argument("--run-id")

    test = subparsers.add_parser("test", help="Evaluate a checkpoint on held-out prompts")
    test.add_argument("--checkpoint")
    test.add_argument("--dataset", type=Path)
    test.add_argument("--compare")
    test.add_argument("--split", choices=("validation", "test"), default="test")

    subparsers.add_parser("checkpoints", help="List local checkpoints")

    web = subparsers.add_parser("serve", help="Serve the built UI and same-origin local API")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--no-browser", action="store_true")

    return parser


def _run_test(args: argparse.Namespace) -> dict[str, Any]:
    dataset_path = args.dataset or get_active_dataset_path()
    if dataset_path is None:
        raise FileNotFoundError("No dataset is active. Run START_VFXAI.bat first or generate a dataset.")
    records = load_dataset(Path(dataset_path))
    checkpoint_id = args.checkpoint
    if checkpoint_id is None:
        candidates = [item for item in list_checkpoints() if item.get("trained")]
        checkpoint_id = candidates[0]["checkpoint_id"] if candidates else f"random-seed-{DEFAULT_INIT_SEED}-h{DEFAULT_HIDDEN_SIZE}"
    model, metadata, _ = load_checkpoint(checkpoint_id)
    report = evaluate_model(model, records, args.split, checkpoint_id, include_predictions=True)
    evaluation_id = f"evaluation-{checkpoint_id}-{args.split}-{metadata.get('created_at', 'latest').replace(':', '').replace('-', '')[:14]}"
    output_dir = EXPERIMENTS_DIR / evaluation_id
    save_predictions(output_dir / "predictions.jsonl", report.pop("predictions"))
    report["dataset_file"] = Path(dataset_path).name
    report["dataset_version"] = metadata.get("dataset_version")
    report["output_directory"] = str(output_dir)
    if args.compare:
        compare_model, _, _ = load_checkpoint(args.compare)
        comparison = evaluate_model(compare_model, records, args.split, args.compare)
        report["comparison"] = {
            "checkpoint_id": args.compare,
            "same_split": True,
            "same_prompt_count": report["example_count"] == comparison["example_count"],
            "metrics": {
                key: {
                    "selected": report[key] if key in report else report["loss"].get("total"),
                    "compared": comparison[key] if key in comparison else comparison["loss"].get("total"),
                }
                for key in ("category_accuracy", "component_exact_match", "numeric_mae_normalized", "valid_plan_rate")
            },
            "loss_total": {"selected": report["loss"]["total"], "compared": comparison["loss"]["total"]},
        }
    ensure_state_dirs()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize_project(args.dataset_count, args.dataset_seed, args.init_seed, args.hidden_size)
        elif args.command == "generate-dataset":
            path, manifest = generate_dataset(args.count, args.seed, args.output)
            if args.activate:
                set_active_dataset(path)
            result = {"path": str(path), "manifest": manifest, "activated": args.activate}
        elif args.command == "train":
            result = train_experiment(
                dataset_path=args.dataset,
                epochs=args.epochs,
                batch_size=args.batch_size,
                learning_rate=args.learning_rate,
                seed=args.seed,
                hidden_size=args.hidden_size,
                include_feedback=args.include_feedback,
                resume_checkpoint=args.resume,
                status_path=args.status_path,
                control_path=args.control_path,
                run_id=args.run_id,
            )
        elif args.command == "test":
            result = _run_test(args)
        elif args.command == "checkpoints":
            result = {"checkpoints": list_checkpoints()}
        elif args.command == "serve":
            serve(host=args.host, port=args.port, open_browser=not args.no_browser)
            return 0
        else:
            parser.error("Unknown command")
            return 2
        _json(result)
        return 0
    except Exception as error:
        print(f"VFXAI error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
