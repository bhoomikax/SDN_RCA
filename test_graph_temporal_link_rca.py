import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from evaluate_graph_temporal_link_rca import prepare_examples, score_ranking, wilson_interval


def graph_snapshot(timestamp, phase="fault", label="s1-s2", value=1.0):
    nodes = ["h1", "s1", "s2", "s3", "s4", "h2"]
    edges = [["h1", "s1"], ["s1", "s2"], ["s2", "s3"], ["s3", "s4"], ["s4", "h2"]]
    return {"experiment_id": 1, "timestamp": timestamp, "nodes": nodes, "edges": edges,
            "node_features": {node: ([0.0, value, value * 2, value * 3] if node.startswith("s") else [0.0] * 4)
                              for node in nodes},
            "phase": phase, "fault_type": "link_failure", "fault_location": label}


class GraphTemporalRcaTests(unittest.TestCase):
    def load(self, snapshots):
        payload = {"schema_version": 2,
                   "port_aggregation": "sum over all numbered non-LOCAL ports per switch and timestamp",
                   "feature_names": ["rx", "tx", "rx_mbps", "tx_mbps"],
                   "snapshots": snapshots}
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "graph.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return prepare_examples(path)[0]

    def test_labels_are_targets_not_feature_tensors(self):
        examples = self.load([graph_snapshot("2026-01-01T00:00:00")])
        self.assertEqual(examples[1]["label"], 0)
        self.assertEqual(set(examples[1]["sequence"][0]), {"x", "edge_index"})
        self.assertTrue(np.isfinite(examples[1]["sequence"][0]["x"]).all())

    def test_window_uses_only_annotated_fault_samples_first_ten_seconds(self):
        examples = self.load([
            graph_snapshot("2026-01-01T00:00:00", phase="normal", label="none"),
            graph_snapshot("2026-01-01T00:00:10", phase="fault", value=1),
            graph_snapshot("2026-01-01T00:00:18", phase="fault", value=2),
            graph_snapshot("2026-01-01T00:00:21", phase="fault", value=100),
            graph_snapshot("2026-01-01T00:00:22", phase="recovery", label="s1-s2"),
        ])
        self.assertEqual(len(examples[1]["sequence"]), 2)
        self.assertEqual(examples[1]["sequence"][-1]["x"][1, 1], 2)

    def test_rank_order_has_deterministic_lexical_tie_break(self):
        ranked, rank = score_ranking([0.5, 0.5, 0.1], actual=1)
        self.assertEqual(ranked, [0, 1, 2])
        self.assertEqual(rank, 2)

    def test_wilson_interval_uses_experiment_support(self):
        lower, upper = wilson_interval(4, 6)
        self.assertAlmostEqual(lower, 0.29999, places=4)
        self.assertAlmostEqual(upper, 0.90323, places=4)


if __name__ == "__main__":
    unittest.main()
