import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from demo_rca import load_demo, render


class SavedResultsDemoTests(unittest.TestCase):
    def make_fixture(self, root):
        candidate_dir = root / "candidate"
        evaluation_dir = root / "evaluation"
        candidate_dir.mkdir()
        evaluation_dir.mkdir()
        candidate = candidate_dir / "candidate_dataset.csv"
        candidate.write_text("fixture\n", encoding="utf-8")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        (candidate_dir / "provenance.json").write_text(json.dumps({
            "dataset_sha256": digest,
            "validation": "PASS",
            "included_logical_experiments": [1, 2],
            "run_23_rows": 10,
        }), encoding="utf-8")
        (evaluation_dir / "evaluation_provenance.json").write_text(json.dumps({
            "dataset_sha256": digest,
            "task": "Conditional localization; oracle fault phase",
            "split": {"train_logical_ids": [1], "test_logical_ids": [2]},
        }), encoding="utf-8")
        columns = ["record_type", "method", "experiment_id", "actual_link", "rank1_link",
                   "rank2_link", "rank3_link", "top1_hit", "top2_hit", "top3_hit"]
        with (evaluation_dir / "topology_link_rca_results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerow({"record_type": "experiment", "method": "rf_baseline",
                             "experiment_id": 2, "actual_link": "s1-s2", "rank1_link": "s1-s2",
                             "rank2_link": "s2-s3", "rank3_link": "s3-s4", "top1_hit": True,
                             "top2_hit": True, "top3_hit": True})
        return evaluation_dir, candidate

    def test_renders_saved_rankings_and_oracle_caveat(self):
        with tempfile.TemporaryDirectory() as temporary:
            evaluation, candidate = self.make_fixture(Path(temporary))
            output = render(evaluation, candidate)
            self.assertIn("Top-1 1/1, Top-2 1/1", output)
            self.assertIn("not online detection", output)
            self.assertIn("s1-s2 > s2-s3 > s3-s4", output)

    def test_rejects_candidate_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            evaluation, candidate = self.make_fixture(Path(temporary))
            candidate.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash does not match"):
                load_demo(evaluation, candidate)


if __name__ == "__main__":
    unittest.main()
