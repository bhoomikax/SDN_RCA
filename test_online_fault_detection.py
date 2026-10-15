import unittest

import pandas as pd

from evaluate_online_fault_detection import METRICS, fit_training_normal, score_online_rows


class OnlineFaultDetectionTests(unittest.TestCase):
    def test_future_sample_changes_do_not_change_earlier_scores(self):
        rows = pd.DataFrame([
            {"experiment_id": 1, "timestamp": pd.Timestamp("2026-01-01T00:00:00"), "phase": "normal", "port": "1", "switch": "s1", **dict.fromkeys(METRICS, 1.0)},
            {"experiment_id": 1, "timestamp": pd.Timestamp("2026-01-01T00:00:01"), "phase": "normal", "port": "1", "switch": "s1", **dict.fromkeys(METRICS, 2.0)},
        ])
        _normal, active, means, scales = fit_training_normal(rows, [1])
        earlier_a = score_online_rows(rows.iloc[[0]][["experiment_id", "timestamp", *active]], active, means, scales)
        changed = rows.copy()
        changed.loc[1, list(active)] = 1_000_000.0
        _normal2, active2, means2, scales2 = fit_training_normal(rows, [1])
        earlier_b = score_online_rows(changed.iloc[[0]][["experiment_id", "timestamp", *active2]], active2, means2, scales2)
        self.assertEqual(float(earlier_a.port_anomaly_score.iloc[0]), float(earlier_b.port_anomaly_score.iloc[0]))

    def test_score_function_does_not_require_or_read_phase(self):
        rows = pd.DataFrame([{"experiment_id": 1, "timestamp": pd.Timestamp("2026-01-01"), **dict.fromkeys(METRICS, 2.0)}])
        means, scales = pd.Series({name: 1.0 for name in METRICS}), pd.Series({name: 1.0 for name in METRICS})
        scored = score_online_rows(rows, METRICS, means, scales)
        self.assertEqual(len(scored), 1)
        self.assertNotIn("phase", scored.columns)


if __name__ == "__main__":
    unittest.main()
