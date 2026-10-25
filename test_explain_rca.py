"""Tests for the XAI layer: attribution identities, occlusion shapes, report schema, and sanity checks."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import explain_rca as xai
import graph_temporal_topology as models
from evaluate_topology_loeo import evaluate as evaluate_rf_topology
from linear_topology import LinearTopology
from test_evaluate_topology_loeo import synthetic_candidate


REQUIRED_KEYS = {"method", "label", "explanation_method", "score_semantics", "ranking", "scores", "ground_truth",
                 "top1_correct", "rank_of_truth", "relevant_switches_ports", "validation", "limitations"}


def random_sequence(topology, steps=4, features=4, seed=0):
    rng = np.random.default_rng(seed)
    sequence = []
    edges = []
    nodes = list(topology.nodes)
    for a, b in topology.edges:
        edges.extend([[nodes.index(a), nodes.index(b)], [nodes.index(b), nodes.index(a)]])
    edge_index = torch.tensor(np.asarray(edges, dtype=np.int64).T)
    for _ in range(steps):
        x = np.zeros((len(nodes), features), dtype=np.float32)
        x[topology.switch_indices] = rng.normal(size=(len(topology.switch_indices), features))
        sequence.append({"x": torch.tensor(x), "edge_index": edge_index})
    return sequence


class ExplainabilityTests(unittest.TestCase):
    def test_integrated_gradients_satisfies_completeness_for_each_model(self):
        topology = LinearTopology(8)
        sequence = random_sequence(topology)
        for method in ("graph_only", "temporal_only", "graph_temporal"):
            seed_models = [models.build_model(method, 4, topology, seed) for seed in (1, 2)]
            for m in seed_models:
                m.eval()
            scorer = xai.EnsembleScorer(seed_models)
            attributions, f_x, f_b, total = xai.integrated_gradients(scorer, sequence, target=3, steps=128)
            self.assertEqual(len(attributions), len(sequence))
            self.assertEqual(tuple(attributions[0].shape), (len(topology.nodes), 4))
            self.assertLess(abs((f_x - f_b) - total), max(0.05 * abs(f_x - f_b), 2e-3), method)
            # Host rows carry zero input and therefore zero attribution.
            self.assertEqual(float(sum(a[0].abs().sum() + a[-1].abs().sum() for a in attributions)), 0.0)

    def test_occlusion_reports_every_switch_edge_and_timestep(self):
        topology = LinearTopology(12)
        sequence = random_sequence(topology, steps=5)
        model = models.build_model("graph_temporal", 4, topology, 3)
        model.eval()
        scorer = xai.EnsembleScorer([model])
        original, nodes, edges, times = xai.occlusion_tests(scorer, sequence, 0, topology, uses_edges=True)
        self.assertEqual(set(nodes), set(topology.switches))
        self.assertEqual(set(edges), set(topology.candidate_links))
        self.assertEqual(len(times), 5)
        self.assertTrue(0.0 <= original <= 1.0)
        _o, _n, no_edges, _t = xai.occlusion_tests(scorer, sequence, 0, topology, uses_edges=False)
        self.assertEqual(no_edges, {})

    def test_model_shapes_follow_topology_size(self):
        for count in (4, 8, 12):
            topology = LinearTopology(count)
            graph = models.build_model("graph_only", 3, topology, 0)
            self.assertEqual(graph.head.in_features, (count + 2) * models.EMBEDDING)
            self.assertEqual(graph.head.out_features, count - 1)
            temporal = models.build_model("temporal_only", 3, topology, 0)
            self.assertEqual(temporal.lstm.input_size, (count + 2) * 3)
            scores = temporal(random_sequence(topology, features=3))
            self.assertEqual(tuple(scores.shape), (count - 1,))

    def test_rf_and_ranker_explanations_have_schema_and_pass_identity_checks(self):
        topology = LinearTopology(8)
        experiments = [(101 + i, topology.candidate_links[i % 7]) for i in range(9)]
        frame = synthetic_candidate(topology, experiments)
        with tempfile.TemporaryDirectory() as directory:
            candidate_dir = Path(directory) / "candidate"
            candidate_dir.mkdir()
            frame.to_csv(candidate_dir / "candidate_dataset.csv", index=False)
            with (candidate_dir / "link_port_mapping.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=("link", "switch", "openflow_port", "interface_name"))
                writer.writeheader()
                for link in topology.candidate_links:
                    left, right = topology.link_endpoints(link)
                    writer.writerow({"link": link, "switch": left, "openflow_port": "2", "interface_name": left + "-eth2"})
                    writer.writerow({"link": link, "switch": right, "openflow_port": "1", "interface_name": right + "-eth1"})
            rf_dir = Path(directory) / "loeo"
            evaluate_rf_topology(candidate_dir, 8, rf_dir)
            output = Path(directory) / "xai"
            summary = xai.run(8, candidate_dir, None, rf_dir, None, output, experiments=[101, 104])
            self.assertEqual(summary["experiments_explained"], [101, 104])
            self.assertEqual(set(summary["methods"]), {"rf_baseline", "topology_link_ranker"})
            report = json.loads((output / "experiments" / "experiment_101.json").read_text(encoding="utf-8"))
            for method in ("rf_baseline", "topology_link_ranker"):
                self.assertTrue(REQUIRED_KEYS <= set(report[method]), method)
                self.assertEqual(len(report[method]["ranking"]), 7)
                self.assertEqual(report[method]["ground_truth"], "s1-s2")
            rf = report["rf_baseline"]
            self.assertTrue(rf["validation"]["additivity_pass"])
            self.assertEqual(len(rf["feature_values"]), 8 * 4)
            self.assertIn("top_features", rf["predicted_class_attribution"])
            ranker = report["topology_link_ranker"]
            self.assertTrue(ranker["validation"]["rank_score_recomputed_pass"])
            self.assertEqual(set(ranker["component_table"]), set(topology.candidate_links))
            self.assertEqual(set(ranker["component_sensitivity"]), {m for m, _ in xai.RANK_COMPONENTS})
            markdown = (output / "experiments" / "experiment_101.md").read_text(encoding="utf-8")
            self.assertIn("uncalibrated ranking scores", markdown)
            self.assertIn("Random Forest", markdown)
            self.assertIn("Topology ranker", markdown)
            self.assertIn("rf_mean_abs_shap_predicted_class", summary["global_feature_importance"])
            with self.assertRaises(FileExistsError):
                xai.run(8, candidate_dir, None, rf_dir, None, output, experiments=[101])


if __name__ == "__main__":
    unittest.main()
