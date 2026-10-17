import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from demo_rca_v3 import fresh_inference, replay


class CandidateV3DemoTests(unittest.TestCase):
    def test_replays_saved_heldout_prediction_and_window(self):
        result = replay(20)
        self.assertEqual(result["mode"], "saved-results replay; no training or inference")
        self.assertEqual(result["experiment_id"], 20)
        self.assertEqual(len(result["ranking"]), 3)
        self.assertGreater(result["telemetry_rows"], 0)
        self.assertEqual(result["actual_link_retrospective_only"], "s1-s2")

    def test_fresh_inference_refits_fold_and_reports_measurement_evidence(self):
        result = fresh_inference(20)
        self.assertIn("fresh LOEO inference", result["mode"])
        self.assertEqual(result["training_experiment_count"], 24)
        self.assertNotIn(20, result["training_experiment_ids"])
        self.assertEqual(len(result["ranking"]), 3)
        self.assertEqual(set(result["topology_neighbors"]), set(result["ranking"]))
        self.assertIn("s2", result["measurement_evidence"]["switch_evidence"])
        self.assertIn("not model feature attributions", result["explanation_boundary"])
        saved = replay(20)
        self.assertEqual(result["ranking"], saved["ranking"])

    def test_fresh_inference_rejects_candidate_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "candidate_dataset.csv"
            dataset.write_text("not a candidate\n", encoding="utf-8")
            (root / "provenance.json").write_text(json.dumps({
                "dataset_sha256": hashlib.sha256(b"different").hexdigest(),
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                fresh_inference(20, dataset=dataset)


if __name__ == "__main__":
    unittest.main()
