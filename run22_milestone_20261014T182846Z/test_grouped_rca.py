"""Small offline regression checks for the new grouped evaluation helpers."""

import unittest
from pathlib import Path
import sys
import json

import numpy as np
import pandas as pd

import evaluate_grouped_rca as evaluation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_candidate


class GroupedRcaTests(unittest.TestCase):
    def test_leave_one_experiment_out_has_no_group_overlap(self):
        ids = list(range(1, 19))
        splits = list(evaluation.ordered_grouped_splits(ids))
        self.assertEqual(len(splits), 18)
        for held_out, train in splits:
            self.assertNotIn(held_out, train)
            self.assertEqual(set(train) | {held_out}, set(ids))
            self.assertEqual(len(train), 17)

    def test_duplicate_experiment_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            list(evaluation.ordered_grouped_splits([1, 1, 2]))

    def test_predictors_exclude_labels_and_grouping_fields(self):
        self.assertFalse(evaluation.FORBIDDEN_PREDICTORS & set(evaluation.METRICS))
        self.assertFalse(evaluation.FORBIDDEN_PREDICTORS & set(evaluation.RF_STAT_NAMES))
        self.assertTrue({"phase", "fault_location", "fault_type", "experiment_id"} <= evaluation.FORBIDDEN_PREDICTORS)

    def test_equal_rf_probabilities_have_deterministic_lexical_tie_order(self):
        class DummyModel:
            classes_ = np.array(["s3-s4", "s1-s2", "s2-s3"])

            def predict_proba(self, _):
                return np.array([[1 / 3, 1 / 3, 1 / 3]])

        ranking, scores = evaluation._stable_rf_ranking(DummyModel(), np.zeros(1))
        self.assertEqual(ranking, ["s1-s2", "s2-s3", "s3-s4"])
        self.assertEqual(len(set(scores.values())), 1)

    def test_candidate_loads_expected_logical_experiments(self):
        frame, labels = evaluation.load_candidate()
        self.assertEqual(len(frame), 12276)
        self.assertEqual(set(labels), set(range(1, 20)) - {10})
        self.assertEqual(labels[3], "s3-s4")

    def test_candidate_builder_refuses_existing_outputs(self):
        with self.assertRaisesRegex(FileExistsError, "overwrite"):
            build_candidate.build_candidate()

    def test_saved_evaluation_covers_each_holdout_for_both_methods(self):
        root = Path(__file__).resolve().parent
        results = pd.read_csv(root / "grouped_evaluation.csv")
        self.assertEqual(len(results), 36)
        self.assertEqual(set(results["method"]), {"rf_baseline", "topology_link_ranker"})
        for method in results["method"].unique():
            subset = results[results["method"] == method]
            self.assertEqual(set(subset["experiment_id"].astype(int)), set(range(1, 20)) - {10})
            self.assertEqual(subset["experiment_id"].nunique(), 18)
            self.assertTrue(subset["top3_hit"].all())
        summary = json.loads((root / "evaluation_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["methods"]["rf_baseline"]["support"], 18)
        self.assertEqual(summary["methods"]["topology_link_ranker"]["support"], 18)


if __name__ == "__main__":
    unittest.main()
