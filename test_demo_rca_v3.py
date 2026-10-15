import unittest

from demo_rca_v3 import replay


class CandidateV3DemoTests(unittest.TestCase):
    def test_replays_saved_heldout_prediction_and_window(self):
        result = replay(20)
        self.assertEqual(result["mode"], "saved-results replay; no training or inference")
        self.assertEqual(result["experiment_id"], 20)
        self.assertEqual(len(result["ranking"]), 3)
        self.assertGreater(result["telemetry_rows"], 0)
        self.assertEqual(result["actual_link_retrospective_only"], "s1-s2")


if __name__ == "__main__":
    unittest.main()
