"""Tests for the independent methodology audit."""

import json
import unittest
from pathlib import Path

import audit_topology_results as audit


ROOT = Path(__file__).resolve().parent


class AuditTests(unittest.TestCase):
    def test_exact_sign_test(self):
        self.assertEqual(audit.sign_test_p(0, 0), 1.0)
        self.assertAlmostEqual(audit.sign_test_p(5, 0), 2 * (1 / 32))
        self.assertAlmostEqual(audit.sign_test_p(3, 3), 1.0)
        self.assertAlmostEqual(audit.sign_test_p(8, 1), 2 * (1 + 9) / 512)
        self.assertLessEqual(audit.sign_test_p(20, 1), 1.0)

    def test_audit_passes_on_eight_switch_artifacts_when_present(self):
        rf_dir = ROOT / "results" / "topology_8_switches" / "loeo_rf_topology"
        neural_dir = ROOT / "results" / "topology_8_switches" / "loeo_neural"
        candidate = ROOT / "results" / "topology_8_switches" / "candidate" / "candidate_dataset.csv"
        if not (candidate.is_file() and (rf_dir / "grouped_evaluation.csv").is_file() and (neural_dir / "evaluation_summary.json").is_file()):
            self.skipTest("8-switch artifacts not present")
        result = audit.audit_topology("8", 8, candidate, rf_dir, neural_dir, ROOT / "results" / "xai" / "topology_8_switches", False)
        self.assertEqual(result["problems"], [])
        self.assertEqual(result["candidate_links"], 7)
        self.assertEqual(result["experiments"], 24)
        self.assertEqual(len(result["paired_top1_comparisons"]), 10)
        for pair in result["paired_top1_comparisons"]:
            total = pair["a_correct_b_wrong"] + pair["b_correct_a_wrong"] + pair["both_correct"] + pair["both_wrong"]
            self.assertEqual(total, 24)

    def test_audit_detects_a_leaky_split(self):
        """A tampered copy with the held-out ID inside its training list must fail."""
        import csv
        import shutil
        import tempfile
        rf_dir = ROOT / "results" / "topology_12_switches" / "loeo_rf_topology"
        neural_dir = ROOT / "results" / "topology_12_switches" / "loeo_neural"
        candidate = ROOT / "results" / "topology_12_switches" / "candidate" / "candidate_dataset.csv"
        if not (candidate.is_file() and (rf_dir / "grouped_evaluation.csv").is_file() and (neural_dir / "evaluation_summary.json").is_file()):
            self.skipTest("12-switch artifacts not present")
        with tempfile.TemporaryDirectory() as directory:
            tampered = Path(directory) / "rf"
            shutil.copytree(rf_dir, tampered)
            path = tampered / "grouped_evaluation.csv"
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["train_experiment_ids"] = rows[0]["train_experiment_ids"] + ";" + rows[0]["experiment_id"]
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = audit.audit_topology("12", 12, candidate, tampered, neural_dir, None, False)
        self.assertTrue(any("never in training" in p or "training size" in p for p in result["problems"]), result["problems"])


if __name__ == "__main__":
    unittest.main()
