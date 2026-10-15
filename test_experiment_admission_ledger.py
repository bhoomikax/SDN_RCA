import csv
import json
import tempfile
import unittest
from pathlib import Path

from build_experiment_admission_ledger import build


class AdmissionLedgerTests(unittest.TestCase):
    def test_preserves_raw_status_separately_from_derived_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            candidate.mkdir()
            provenance = {
                "input_candidate": {"ids": [1, 2, 4]},
                "recollected_runs": [{
                    "source_physical_run_id": 21, "logical_experiment_id": 3,
                    "original_metadata_status": "FAILED_INVALID", "admission_status": "VALID",
                    "raw_artifact_sha256": {"telemetry.csv": "abc"},
                    "forensic_reaudit": "PASS", "admission_basis": "Independent validation",
                }],
                "included_logical_experiments": [1, 2, 3, 4],
            }
            (candidate / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
            with (candidate / "exclusion_report.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=("experiment_id", "status", "reason"))
                writer.writeheader()
                writer.writerows([
                    {"experiment_id": 20, "status": "INVALID", "reason": "invalid"},
                    {"experiment_id": 22, "status": "PROVISIONAL", "reason": "uncertain"},
                ])
            manifest = root / "manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=("experiment_id", "decision_reason"))
                writer.writeheader()
                writer.writerows([{"experiment_id": 3, "decision_reason": "historical invalid"},
                                  {"experiment_id": 10, "decision_reason": "historical invalid"}])
            source, output = root / "source.csv", root / "ledger.csv"
            source.touch()
            result = build(candidate, source, manifest, output)
            with output.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            replacement = next(row for row in rows if row["physical_run_id"] == "21")
            self.assertEqual(replacement["raw_status"], "FAILED_INVALID")
            self.assertEqual(replacement["derived_audit_status"], "VALID")
            self.assertEqual(replacement["candidate_member"], "true")
            self.assertEqual(result["candidate_member_logical_ids"], [1, 2, 3, 4])
            with self.assertRaises(FileExistsError):
                build(candidate, source, manifest, output)


if __name__ == "__main__":
    unittest.main()
