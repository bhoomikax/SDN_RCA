"""Guard: the frozen four-switch datasets and results are byte-identical to their recorded hashes."""

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FROZEN = {
    "master_dataset.csv": "7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64",
    "run22_milestone_20261014T182846Z/inputs/candidate_master_dataset.csv": "e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2",
    "run22_milestone_20261014T182846Z/inputs/audit_manifest.csv": "80f12f94a7fb0dd6b648126d1021993e78616aad0daf2ab7f4c1d423c8e16d7c",
    "derived_datasets/balanced_recollection_20261015_v3/candidate_dataset.csv": "b63d04572b7b97b8451be33174c8813d76af53e3f49f40e5e41b682b1e19b29a",
    "derived_graphs/balanced_recollection_v3_portsum/graph_dataset.json": "5d639c219c80ed592e8f28eec4d5d0d207316e2a325b02007664055900f4bea9",
    "evaluations/balanced_recollection_v3_loeo_release/grouped_evaluation.csv": "b23812871743ec4745cec20861738827e60e697612f2d096ef7c17589d280be5",
    "evaluations/balanced_recollection_v3_loeo_release/evaluation_summary.json": "6913d7f140bc4652473329dba974279ce5dce9dd39d50752f50f6385faf152f3",
    "evaluations/graph_temporal_v3_grouped_loeo_verified/evaluation_summary.json": "cf0a6b893988ff7b632956c16f3eeebd0cab49c071ab439a29fa708d49f163bc",
    "evaluations/graph_temporal_v3_grouped_loeo_verified/mean_seed_ensemble_predictions.csv": "309ebbb7962dd05bdbe60213635104d6f6bba43eb2d0fa323daa3615f9bf4b70",
    "evaluations/graph_temporal_v3_grouped_loeo_verified/per_seed_predictions.csv": "f2fed3b81cae7b5491198e0c1c54f93a3d05f7e26068710a61b3f46e390e0e63",
}
FOUR_SWITCH_VERIFIED_METRICS = {
    "graph_only": (20, 23), "temporal_only": (18, 21), "graph_temporal": (23, 23),
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FrozenArtifactTests(unittest.TestCase):
    def test_frozen_four_switch_files_are_unchanged(self):
        for relative, expected in FROZEN.items():
            path = ROOT / relative
            if not path.is_file():
                self.skipTest("frozen artifact missing from this checkout: %s" % relative)
            self.assertEqual(sha256(path), expected, relative)

    def test_frozen_four_switch_metrics_are_as_published(self):
        summary_path = ROOT / "evaluations" / "graph_temporal_v3_grouped_loeo_verified" / "evaluation_summary.json"
        if not summary_path.is_file():
            self.skipTest("verified summary missing")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for method, (top1, top2) in FOUR_SWITCH_VERIFIED_METRICS.items():
            metrics = summary["methods"][method]["mean_score_ensemble_metrics"]
            self.assertEqual((metrics["top1_count"], metrics["top2_count"]), (top1, top2), method)
        reference = summary["same_fold_reference_baselines"]
        self.assertEqual((reference["rf_baseline"]["top1_count"], reference["rf_baseline"]["top2_count"]), (20, 22))
        self.assertEqual((reference["topology_link_ranker"]["top1_count"], reference["topology_link_ranker"]["top2_count"]), (13, 22))
        self.assertEqual(summary["experiment_count"], 25)

    def test_new_topology_outputs_live_outside_frozen_directories(self):
        from linear_topology import topology_run_registry
        for count in (8, 12):
            for entry in topology_run_registry(count).values():
                self.assertFalse((ROOT / "experiments" / ("telemetry_%d.csv" % entry["physical_run_id"])).exists())
                self.assertFalse((ROOT / "recollection_runs" / ("physical_%d_logical_%d" % (
                    entry["physical_run_id"], entry["logical_experiment_id"]))).exists())


if __name__ == "__main__":
    unittest.main()
