import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from vfxai import feedback as feedback_module
from vfxai import dataset as dataset_module
from vfxai.dataset import generate_records, write_dataset
from vfxai.feedback import approved_training_records, approve_feedback, create_feedback


class FeedbackReviewTests(unittest.TestCase):
    def test_ratings_do_not_train_until_valid_example_is_explicitly_approved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            feedback_dir = root / "feedback"
            dataset_path = root / "base.jsonl"
            rows, manifest = generate_records(200, 51)
            with patch.object(dataset_module, "ensure_state_dirs", lambda: None):
                write_dataset(dataset_path, rows, manifest)
            generation = {
                "id": "gen-0123456789abcdef",
                "prompt": "Create a blue radial pulse with a crisp edge and long fade.",
                "category": rows[0]["category"],
                "candidate_plan": rows[0]["plan"],
            }
            with patch.object(feedback_module, "FEEDBACK_DIR", feedback_dir), patch.object(
                feedback_module, "ensure_state_dirs", lambda: feedback_dir.mkdir(parents=True, exist_ok=True)
            ):
                pending = create_feedback(generation, "good", notes="Useful first draft.")
                self.assertTrue(pending["training_eligible"])
                self.assertEqual(pending["approval_status"], "pending")
                trained, skipped = approved_training_records(rows)
                self.assertEqual(trained, [])
                self.assertEqual(skipped, [])

                approved = approve_feedback(pending["id"], dataset_path)
                self.assertEqual(approved["approval_status"], "approved")
                trained, skipped = approved_training_records(rows)
                self.assertEqual(len(trained), 1)
                self.assertEqual(trained[0]["source"], "human-approved-feedback")
                self.assertEqual(trained[0]["split"], "train")
                self.assertEqual(skipped, [])

    def test_invalid_correction_is_saved_but_cannot_be_approved(self):
        with TemporaryDirectory() as temporary:
            feedback_dir = Path(temporary) / "feedback"
            generation = {
                "id": "gen-0123456789abcdef",
                "prompt": "A test prompt.",
                "category": "explosion",
                "candidate_plan": {},
            }
            with patch.object(feedback_module, "FEEDBACK_DIR", feedback_dir), patch.object(
                feedback_module, "ensure_state_dirs", lambda: feedback_dir.mkdir(parents=True, exist_ok=True)
            ):
                record = create_feedback(
                    generation,
                    "invalid",
                    corrected_plan_text="{ not-json",
                )
                self.assertFalse(record["training_eligible"])
                self.assertEqual(record["raw_plan"], "{ not-json")
                with self.assertRaises(ValueError):
                    approve_feedback(record["id"])


if __name__ == "__main__":
    unittest.main()
