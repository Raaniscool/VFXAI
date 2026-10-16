import copy
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from vfxai import checkpoints
from vfxai.config import CATEGORIES, COMPONENT_TYPES
from vfxai.contracts import FIELDS, analyze_plan, encode_plan_targets, model_subset_issues
from vfxai.dataset import generate_records, write_dataset
from vfxai.evaluation import evaluate_model
from vfxai.model import Adam, StructuredMLP
from vfxai.training import _make_training_arrays, train_experiment
from vfxai.vectorizer import encode_prompt, encode_prompts


ROOT = Path(__file__).resolve().parents[1]


class ModelPipelineTests(unittest.TestCase):
    def test_existing_example_matches_python_schema_and_resource_estimator(self):
        import json

        example = json.loads((ROOT / "examples" / "lightning-burst.vfx.json").read_text(encoding="utf-8"))
        before = copy.deepcopy(example)
        report = analyze_plan(example)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["stats"], {"components": 5, "objects": 13, "particles": 96, "vertices": 1912})
        self.assertEqual(example, before)
        self.assertTrue(model_subset_issues(example))  # two rings exceed the model's one-per-type target subset

    def test_reasoner_rejects_schema_timeline_and_resource_failures_without_mutation(self):
        import json

        plan = json.loads((ROOT / "examples" / "lightning-burst.vfx.json").read_text(encoding="utf-8"))
        plan["components"] = [item for item in plan["components"] if item["id"] != "shockwave-b"]
        plan["components"][1]["start"] = 1.0
        plan["components"][1]["duration"] = 1.0
        before = copy.deepcopy(plan)
        report = analyze_plan(plan)
        self.assertFalse(report["ok"])
        self.assertIn("TIMELINE_OVERFLOW", {issue["code"] for issue in report["issues"]})
        self.assertEqual(plan, before)

        invalid = copy.deepcopy(plan)
        invalid["duration"] = float("nan")
        self.assertFalse(analyze_plan(invalid)["ok"])

    def test_dataset_generation_is_reproducible_valid_and_family_disjoint(self):
        first, manifest = generate_records(200, 77)
        second, _ = generate_records(200, 77)
        self.assertEqual(first, second)
        self.assertEqual(manifest["split_counts"], {"train": 160, "validation": 20, "test": 20})
        self.assertEqual(manifest["unique_prompt_count"], 200)
        self.assertEqual(manifest["exact_duplicate_prompts"], 0)
        self.assertEqual(manifest["validation_failures"], 0)
        group_splits = {}
        for row in first:
            self.assertTrue(analyze_plan(row["plan"])["ok"], row["id"])
            group_splits.setdefault(row["group_id"], set()).add(row["split"])
        self.assertTrue(all(len(splits) == 1 for splits in group_splits.values()))
        self.assertEqual(set(manifest["category_counts"]), set(CATEGORIES))
        self.assertEqual(set(COMPONENT_TYPES), {component["type"] for row in first for component in row["plan"]["components"]})

    def test_vectorizer_is_local_deterministic_and_prompt_sensitive(self):
        one = encode_prompt("cyan lightning with particles")
        again = encode_prompt("cyan lightning with particles")
        other = encode_prompt("slow golden shockwave ring")
        self.assertEqual(one.shape, (512,))
        self.assertTrue(np.array_equal(one, again))
        self.assertFalse(np.array_equal(one, other))
        self.assertAlmostEqual(float(np.linalg.norm(one)), 1.0, places=5)
        with self.assertRaises(ValueError):
            encode_prompt("x" * 1001)

    def test_real_forward_backprop_and_adam_update_reduce_training_loss(self):
        records, _ = generate_records(200, 2026)
        train_rows = [row for row in records if row["split"] == "train"]
        features, categories, components, numbers, mask = _make_training_arrays(train_rows)
        model = StructuredMLP(seed=1337, hidden_size=16)
        optimizer = Adam(0.003)
        optimizer.initialize_shapes(model.params)
        before = {name: array.copy() for name, array in model.params.items()}
        initial = model.loss(features, categories, components, numbers, mask)
        for epoch in range(3):
            permutation = np.random.default_rng(1337 + epoch).permutation(len(train_rows))
            for start in range(0, len(train_rows), 16):
                indices = permutation[start : start + 16]
                model.train_batch(features[indices], categories[indices], components[indices], numbers[indices], mask[indices], optimizer)
        final = model.loss(features, categories, components, numbers, mask)
        self.assertEqual(optimizer.steps, 30)
        self.assertLess(final["numeric"], initial["numeric"] * 0.4)
        self.assertLess(final["total"], initial["total"])
        self.assertGreater(sum(float(np.square(model.params[key] - before[key]).sum()) for key in before), 0.0)
        output = model.predict(encode_prompt("a bright blue energy burst"))
        self.assertEqual(output.category_probabilities.shape, (1, len(CATEGORIES)))
        self.assertEqual(output.component_probabilities.shape, (1, len(COMPONENT_TYPES)))
        self.assertEqual(output.numeric_values.shape, (1, len(FIELDS)))

    def test_checkpoint_round_trip_preserves_weights_and_adam_state(self):
        with TemporaryDirectory() as temporary:
            target = Path(temporary)
            with patch.object(checkpoints, "CHECKPOINTS_DIR", target), patch.object(checkpoints, "ensure_state_dirs", lambda: target.mkdir(parents=True, exist_ok=True)):
                model = StructuredMLP(51, 16)
                optimizer = Adam(0.002)
                optimizer.initialize_shapes(model.params)
                x = encode_prompts(["cyan lightning", "gold shockwave"])
                categories = np.array([0, 3], dtype=np.int64)
                components = np.array([[1, 1, 1, 1], [0, 1, 0, 1]], dtype=np.float32)
                numbers = np.full((2, len(FIELDS)), 0.4, dtype=np.float32)
                mask = np.ones_like(numbers)
                model.train_batch(x, categories, components, numbers, mask, optimizer)
                save_meta = checkpoints.save_checkpoint("unit-checkpoint", model, {"kind": "trained", "trained": True}, optimizer)
                loaded, metadata, loaded_optimizer = checkpoints.load_checkpoint("unit-checkpoint")
                self.assertEqual(metadata["checkpoint_id"], "unit-checkpoint")
                self.assertEqual(save_meta["model"]["parameter_count"], loaded.parameter_count)
                self.assertIsNotNone(loaded_optimizer)
                self.assertEqual(optimizer.steps, loaded_optimizer.steps)
                for name in model.params:
                    np.testing.assert_array_equal(model.params[name], loaded.params[name])
                    np.testing.assert_array_equal(optimizer.m[name], loaded_optimizer.m[name])

    def test_end_to_end_training_saves_comparable_checkpoints_and_raw_predictions(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset_path = root / "synthetic.jsonl"
            records, manifest = generate_records(200, 991)
            with patch("vfxai.dataset.ensure_state_dirs", lambda: None):
                write_dataset(dataset_path, records, manifest)
            checkpoints_dir = root / "checkpoints"
            experiments_dir = root / "experiments"
            runtime_dir = root / "runtime"

            def ensure_temp_dirs():
                for directory in (checkpoints_dir, experiments_dir, runtime_dir):
                    directory.mkdir(parents=True, exist_ok=True)

            with (
                patch.object(checkpoints, "CHECKPOINTS_DIR", checkpoints_dir),
                patch.object(checkpoints, "ensure_state_dirs", ensure_temp_dirs),
                patch("vfxai.training.EXPERIMENTS_DIR", experiments_dir),
                patch("vfxai.training.ensure_state_dirs", ensure_temp_dirs),
                patch("vfxai.training.RUNTIME_DIR", runtime_dir),
            ):
                report = train_experiment(
                    dataset_path=dataset_path,
                    epochs=2,
                    batch_size=32,
                    learning_rate=0.003,
                    seed=1337,
                    hidden_size=16,
                    status_path=runtime_dir / "training.json",
                    control_path=runtime_dir / "control.json",
                    run_id="unit-run",
                )
                self.assertEqual(report["status"], "completed")
                self.assertEqual(report["test_comparison"]["same_held_out_prompts"], True)
                self.assertEqual(report["test_comparison"]["metrics"]["category_accuracy"]["untrained"], report["baseline_test"]["category_accuracy"])
                self.assertEqual(report["trained_test"]["example_count"], report["baseline_test"]["example_count"])
                self.assertGreater(report["weight_delta_l2_from_run_start"], 0.0)
                self.assertTrue((experiments_dir / "unit-run" / "untrained-test-predictions.jsonl").is_file())
                self.assertTrue((experiments_dir / "unit-run" / "trained-test-predictions.jsonl").is_file())
                self.assertTrue((checkpoints_dir / f"{report['best_checkpoint']}.npz").is_file())
                latest = json_read(runtime_dir / "training.json")
                self.assertEqual(latest["status"], "completed")

                resumed = train_experiment(
                    dataset_path=dataset_path,
                    epochs=3,
                    batch_size=32,
                    learning_rate=0.002,
                    seed=9999,
                    hidden_size=64,
                    resume_checkpoint=report["best_checkpoint"],
                    status_path=runtime_dir / "resume-status.json",
                    control_path=runtime_dir / "resume-control.json",
                    run_id="unit-resume",
                )
                self.assertEqual(resumed["status"], "completed")
                self.assertEqual(resumed["dataset_version"], report["dataset_version"])
                self.assertEqual(resumed["training_config"]["seed"], 1337)
                self.assertEqual(resumed["test_comparison"]["same_held_out_prompts"], True)


def json_read(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
