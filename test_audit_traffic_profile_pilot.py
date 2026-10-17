import unittest

from audit_traffic_profile_pilot import audit


class PilotArtifactAuditTests(unittest.TestCase):
    def test_audit_verifies_both_preserved_runs_without_admitting_them(self):
        result = audit()
        failed, completed = result["runs"]
        self.assertEqual(failed["status"], "FAILED_INVALID")
        self.assertEqual(failed["physical_id"], 30)
        self.assertEqual(failed["row_count"], 624)
        self.assertEqual(failed["client_sender_datagrams"], 32099)
        self.assertEqual(failed["iperf_client_aggregate"]["lost_datagrams"], 10999)
        self.assertEqual(failed["iperf_server_aggregate"]["lost_datagrams"], 10999)
        self.assertTrue(failed["receiver_summaries_match"])
        self.assertEqual(completed["status"], "COMPLETE")
        self.assertEqual(completed["row_count"], 672)
        self.assertEqual(completed["telemetry_key_count"], 672)
        self.assertTrue(completed["receiver_summaries_match"])
        self.assertEqual(completed["client_sender_datagrams"], 32100)
        self.assertEqual(completed["iperf_client_aggregate"]["lost_datagrams"], 10900)
        self.assertAlmostEqual(
            completed["normal_event_precedes_iperf_client_seconds"], 2.019, places=3
        )
        self.assertAlmostEqual(
            completed["iperf_client_active_phase_seconds"]["normal"], 20.082, places=2
        )
        self.assertFalse(completed["iperf_phase_specific_loss_available"])
        self.assertFalse(completed["cleanup_evidence_in_metadata"])
        self.assertIn("cannot be independently verified", completed["cleanup_assessment"])
        self.assertTrue(result["hash_manifest_verified"])
        self.assertIn("Exploratory", result["admission_criteria_status"])
        self.assertIn("not a repeatability study", result["classification"])


if __name__ == "__main__":
    unittest.main()
