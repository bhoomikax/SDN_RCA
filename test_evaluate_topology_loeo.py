"""Tests for the generalized LOEO evaluators: K candidates, leakage, metrics, and the frozen-data regression."""

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import evaluate_topology_loeo as evaluator
from evaluate_grouped_rca_generalized import LINK_PORTS as HISTORICAL_LINK_PORTS
from linear_topology import LinearTopology


ROOT = Path(__file__).resolve().parent
BASE = datetime(2026, 1, 1)


def synthetic_candidate(topology, experiments, seed=7):
    """Rows for several experiments; the faulty link's endpoint ports lose traffic during the fault."""
    rng = np.random.default_rng(seed)
    rows = []
    for exp_id, link in experiments:
        left, right = topology.link_endpoints(link)
        for second in range(30):
            phase = "normal" if second < 10 else "fault" if second < 20 else "recovery"
            stamp = (BASE + timedelta(seconds=second)).isoformat()
            for index, switch in enumerate(topology.switches):
                for port in ("LOCAL", "1", "2"):
                    base = 0.0 if port == "LOCAL" else 100.0
                    noise = rng.normal(0, 2.0) if port != "LOCAL" else 0.0
                    endpoint = (switch == left and port == "2") or (switch == right and port == "1")
                    downstream = index > topology.switches.index(left)
                    value = base + noise
                    if phase == "fault" and port != "LOCAL" and (endpoint or downstream):
                        value = max(0.0, 5.0 + noise)
                    rows.append({"timestamp": stamp, "switch": switch, "port": port, "experiment_id": exp_id,
                                 "phase": phase, "fault_type": "none" if phase == "normal" else "link_failure",
                                 "fault_location": "none" if phase == "normal" else link,
                                 "rx_packet_rate": value, "tx_packet_rate": value * 0.9,
                                 "rx_throughput_mbps": value / 50.0, "tx_throughput_mbps": value / 55.0,
                                 "rx_packets": 0, "rx_bytes": 0, "rx_dropped": 0, "tx_packets": 0, "tx_bytes": 0, "tx_dropped": 0})
    return pd.DataFrame(rows)


class GeneralizedEvaluatorTests(unittest.TestCase):
    def test_static_four_switch_mapping_matches_historical_ports(self):
        self.assertEqual(evaluator.static_link_ports(LinearTopology(4)), HISTORICAL_LINK_PORTS)

    def test_link_ports_from_runtime_mapping_orders_endpoints_left_to_right(self):
        topology = LinearTopology(12)
        rows = []
        for link in topology.candidate_links:
            left, right = topology.link_endpoints(link)
            rows.append({"link": link, "switch": right, "openflow_port": "1", "interface_name": right + "-eth1"})
            rows.append({"link": link, "switch": left, "openflow_port": "2", "interface_name": left + "-eth2"})
        ports = evaluator.link_ports_from_mapping(rows, topology)
        self.assertEqual(ports["s9-s10"], (("s9", "2"), ("s10", "1")))
        self.assertEqual(len(ports), 11)
        with self.assertRaisesRegex(ValueError, "lacks both endpoints"):
            evaluator.link_ports_from_mapping(rows[:-1], topology)

    def test_summarize_handles_arbitrary_candidate_counts(self):
        links = tuple("s%d-s%d" % (i, i + 1) for i in range(1, 8))
        rows = [
            {"experiment_id": 1, "actual_link": "s1-s2", "rank1_link": "s1-s2", "rank": 1},
            {"experiment_id": 2, "actual_link": "s4-s5", "rank1_link": "s3-s4", "rank": 2},
            {"experiment_id": 3, "actual_link": "s7-s8", "rank1_link": "s1-s2", "rank": 7},
            {"experiment_id": 4, "actual_link": "s2-s3", "rank1_link": "s2-s3", "rank": 1},
        ]
        summary = evaluator.summarize(rows, links)
        self.assertEqual(summary["candidate_count"], 7)
        self.assertEqual((summary["top1_count"], summary["top2_count"], summary["top3_count"]), (2, 3, 3))
        self.assertAlmostEqual(summary["mean_reciprocal_rank"], (1 + 0.5 + 1 / 7 + 1) / 4)
        self.assertAlmostEqual(summary["chance_level"]["uniform_top1"], 1 / 7)
        self.assertAlmostEqual(summary["chance_level"]["uniform_top2"], 2 / 7)
        self.assertAlmostEqual(summary["chance_level"]["uniform_mrr"], sum(1 / r for r in range(1, 8)) / 7)
        self.assertEqual(len(summary["confusion_matrix_rows_actual_cols_rank1"]), 7)
        self.assertEqual(summary["per_class"]["s7-s8"]["top1_recall"], 0.0)
        self.assertEqual(len(summary["top1_errors"]), 2)
        self.assertEqual(summary["adjacent_link_error_fraction"], 0.5)
        with self.assertRaises(ValueError):
            evaluator.summarize([], links)

    def test_grouped_splits_never_leak_the_held_out_experiment(self):
        ids = [101, 105, 103]
        for held_out, train in evaluator.ordered_grouped_splits(ids):
            self.assertNotIn(held_out, train)
            self.assertEqual(set(train) | {held_out}, set(ids))

    def test_evaluation_on_eight_switch_synthetic_data_ranks_all_seven_candidates(self):
        topology = LinearTopology(8)
        experiments = [(101 + i, topology.candidate_links[i % 7]) for i in range(10)]
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
            output = Path(directory) / "loeo"
            summary = evaluator.evaluate(candidate_dir, 8, output)
            self.assertEqual(summary["candidate_count"], 7)
            self.assertEqual(summary["independent_test_experiments"], 10)
            with (output / "grouped_evaluation.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 20)
            for row in rows:
                ranking = json.loads(row["ranking_json"])
                self.assertEqual(set(ranking), set(topology.candidate_links))
                self.assertEqual(len(ranking), 7)
                self.assertNotIn(row["experiment_id"], row["train_experiment_ids"].split(";"))
                self.assertEqual(len(row["train_experiment_ids"].split(";")), 9)
                self.assertEqual(int(row["rank"]), ranking.index(row["actual_link"]) + 1)
            self.assertEqual(len(summary["predictors"]["rf_features"]), 8 * 4)
            for method in ("rf_baseline", "topology_link_ranker"):
                metrics = summary["methods"][method]
                self.assertEqual(metrics["support"], 10)
                self.assertGreaterEqual(metrics["top1_count"], 0)
                self.assertLessEqual(metrics["top1_count"], 10)
            components = pd.read_csv(output / "topology_ranker_components.csv")
            self.assertEqual(len(components), 70)
            self.assertTrue((components.groupby("experiment_id")["position"].max() == 7).all())
            with self.assertRaises(FileExistsError):
                evaluator.evaluate(candidate_dir, 8, output)

    def test_frozen_four_switch_regression_reproduces_release_rankings(self):
        """The generalized evaluator must reproduce the frozen v3 release on the four-switch data."""
        candidate_dir = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3"
        release = ROOT / "evaluations" / "balanced_recollection_v3_loeo_release" / "grouped_evaluation.csv"
        if not (candidate_dir / "candidate_dataset.csv").is_file() or not release.is_file():
            self.skipTest("frozen v3 artifacts are not present")
        with tempfile.TemporaryDirectory() as directory:
            summary = evaluator.evaluate(candidate_dir, 4, Path(directory) / "loeo", static_mapping=True)
            new = pd.read_csv(Path(directory) / "loeo" / "grouped_evaluation.csv")
        ref = pd.read_csv(release)
        merged = new.merge(ref, on=["experiment_id", "method"], suffixes=("_new", "_ref"))
        self.assertEqual(len(merged), 50)
        for column in ("rank1_link", "rank2_link", "rank3_link"):
            self.assertTrue((merged[column + "_new"] == merged[column + "_ref"]).all(), column)
        self.assertEqual(summary["methods"]["rf_baseline"]["top1_count"], 20)
        self.assertEqual(summary["methods"]["rf_baseline"]["top2_count"], 22)
        self.assertEqual(summary["methods"]["topology_link_ranker"]["top1_count"], 13)
        self.assertEqual(summary["methods"]["topology_link_ranker"]["top2_count"], 22)
        self.assertAlmostEqual(summary["methods"]["rf_baseline"]["mean_reciprocal_rank"], 0.88)
        self.assertAlmostEqual(summary["methods"]["topology_link_ranker"]["mean_reciprocal_rank"], 0.74)


if __name__ == "__main__":
    unittest.main()
