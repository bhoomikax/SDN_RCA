import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import evaluate_graph_temporal_link_rca as models
from evaluate_graph_temporal_grouped_loeo import (
    _read_reference,
    _write_ensemble_predictions,
    ordered_loo_splits,
)


class GroupedGraphTemporalTests(unittest.TestCase):
    def test_leave_one_experiment_out_never_splits_or_leaks_groups(self):
        splits = list(ordered_loo_splits([3, 1, 2]))
        self.assertEqual([held_out for held_out, _ in splits], [1, 2, 3])
        for held_out, train_ids in splits:
            self.assertNotIn(held_out, train_ids)
            self.assertEqual(set(train_ids) | {held_out}, {1, 2, 3})

    def test_feature_policy_excludes_held_out_experiment_values(self):
        examples = {}
        for experiment_id, value in ((1, 2.0), (2, 4.0), (3, 1000.0)):
            features = np.zeros((6, 4), dtype=np.float32)
            features[1:5] = value
            examples[experiment_id] = {
                "sequence": [{"x": features, "edge_index": np.zeros((2, 0), dtype=np.int64)}],
                "label": 0,
            }
        active, means, stds = models.fit_feature_policy(examples, [1, 2])
        self.assertEqual(active, [0, 1, 2, 3])
        np.testing.assert_allclose(means, [3.0, 3.0, 3.0, 3.0])
        self.assertTrue(np.all(stds > 0))

    def test_metric_summary_uses_independent_experiment_support(self):
        from evaluate_graph_temporal_grouped_loeo import _metrics

        rows = [
            {"actual_link": "s1-s2", "rank1_link": "s1-s2", "rank": 1},
            {"actual_link": "s2-s3", "rank1_link": "s3-s4", "rank": 3},
            {"actual_link": "s3-s4", "rank1_link": "s3-s4", "rank": 1},
        ]
        summary = _metrics(rows)
        self.assertEqual(summary["support"], 3)
        self.assertEqual(summary["top1_count"], 2)
        self.assertEqual(summary["top2_count"], 2)
        self.assertAlmostEqual(summary["mean_reciprocal_rank"], (1 + 1 / 3 + 1) / 3)

    def test_ensemble_writer_includes_method_and_scores(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "ensemble.csv"
            _write_ensemble_predictions(output, {
                "graph_only": [{
                    "experiment_id": 7,
                    "actual_link": "s1-s2",
                    "rank1_link": "s1-s2",
                    "rank2_link": "s2-s3",
                    "rank3_link": "s3-s4",
                    "rank": 1,
                    "top1_hit": True,
                    "top2_hit": True,
                    "mean_seed_scores": [0.8, 0.1, 0.1],
                }],
            })
            with output.open(newline="", encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
        self.assertEqual(row["method"], "graph_only")
        self.assertEqual(row["experiment_id"], "7")
        self.assertEqual(json.loads(row["mean_seed_scores_json"]), [0.8, 0.1, 0.1])

    def test_reference_requires_matching_candidate_and_training_groups(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provenance = {
                "dataset_sha256": "candidate-hash",
                "protocol": "leave-one-logical-experiment-out (2 folds), grouped",
            }
            (root / "evaluation_provenance.json").write_text(json.dumps(provenance))
            reference = root / "grouped_evaluation.csv"
            fields = [
                "experiment_id", "method", "rank1_link", "rank2_link",
                "train_experiment_ids",
            ]
            records = []
            for experiment_id, train_ids in ((1, "2"), (2, "1")):
                for method in ("rf_baseline", "topology_link_ranker"):
                    records.append({
                        "experiment_id": experiment_id,
                        "method": method,
                        "rank1_link": "s1-s2",
                        "rank2_link": "s2-s3",
                        "train_experiment_ids": train_ids,
                    })
            with reference.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(records)
            self.assertEqual(
                set(_read_reference(reference, (1, 2), "candidate-hash")),
                {"rf_baseline", "topology_link_ranker"},
            )
            with self.assertRaisesRegex(ValueError, "candidate dataset"):
                _read_reference(reference, (1, 2), "different-hash")
            records[0]["train_experiment_ids"] = "1"
            with reference.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(records)
            with self.assertRaisesRegex(ValueError, "training split"):
                _read_reference(reference, (1, 2), "candidate-hash")


if __name__ == "__main__":
    unittest.main()
