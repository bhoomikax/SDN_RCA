import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "grouped_rca_generalized_test", ROOT / "evaluate_grouped_rca_generalized.py"
)
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)
DATASET = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3" / "candidate_dataset.csv"


class GeneralizedGroupedEvaluatorTests(unittest.TestCase):
    def test_requested_candidate_is_loaded_and_all_groups_are_split(self):
        frame, labels = EVALUATOR.load_candidate(DATASET)
        ids = sorted(labels)
        self.assertEqual(len(ids), 25)
        self.assertEqual(set(frame["experiment_id"].unique()), set(ids))
        folds = list(EVALUATOR.ordered_grouped_splits(ids))
        self.assertEqual(len(folds), 25)
        for held_out, train_ids in folds:
            self.assertNotIn(held_out, train_ids)
            self.assertEqual(len(train_ids), 24)
            self.assertEqual(set(train_ids) | {held_out}, set(ids))


if __name__ == "__main__":
    unittest.main()
