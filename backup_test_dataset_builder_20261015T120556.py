import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import build_validated_candidate as builder


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "run22_milestone_20261014T182846Z" / "inputs" / "candidate_master_dataset.csv"
MANIFEST = ROOT / "run22_milestone_20261014T182846Z" / "inputs" / "audit_manifest.csv"
RUN23 = ROOT / "run23_raw_evidence_physical23_logical3"
RUN21 = ROOT / "run21_failed_raw_evidence_physical21_logical10"


class ValidatedCandidateBuilderTests(unittest.TestCase):
    def test_run23_raw_evidence_passes_all_integrity_checks(self):
        summary, rows = builder.validate_run(RUN23)
        self.assertEqual(summary["source_physical_run_id"], 23)
        self.assertEqual(summary["logical_experiment_id"], 3)
        self.assertEqual(summary["telemetry_rows"], 648)
        self.assertEqual(len(rows), 648)
        self.assertEqual(len(summary["target_mapping"]), 2)
        self.assertTrue(summary["iperf_validation"]["receiver_reports_match"])

    def test_builds_new_derived_candidate_without_touching_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source = temp / "source.csv"
            manifest = temp / "audit.csv"
            raw = temp / "raw23"
            shutil.copy2(SOURCE, source)
            shutil.copy2(MANIFEST, manifest)
            shutil.copytree(RUN23, raw)
            before = (builder.sha256(source), builder.sha256(manifest))
            output = temp / "derived"

            summary = builder.build_candidate(source, manifest, raw, output)

            self.assertEqual(summary["rows"], 12252)
            self.assertEqual(summary["logical_experiments"], 18)
            with (output / "candidate_dataset.csv").open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 12252)
            self.assertEqual({int(row["experiment_id"]) for row in rows}, set(range(1, 20)) - {10})
            self.assertEqual((builder.sha256(source), builder.sha256(manifest)), before)
            provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["run_23"]["source_physical_run_id"], 23)
            self.assertEqual(provenance["physical_to_logical_mapping"], {"23": 3})
            self.assertTrue((output / "exclusion_report.csv").is_file())

    def test_refuses_existing_output_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "occupied"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                builder.build_candidate(SOURCE, MANIFEST, RUN23, output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")

    def test_mapping_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            raw = Path(temp) / "raw23"
            shutil.copytree(RUN23, raw)
            mapping_path = raw / "runtime_port_mapping.csv"
            mapping_path.write_text(
                mapping_path.read_text(encoding="utf-8").replace("s3-eth2", "wrong-iface"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "mapping CSV disagrees"):
                builder.validate_run(raw)

    def test_run21_can_only_pass_explicit_corrected_parser_reaudit(self):
        metadata_path = RUN21 / "run_metadata.json"
        original = metadata_path.read_bytes()
        with self.assertRaisesRegex(ValueError, "status is not eligible"):
            builder.validate_run(RUN21, expected_physical_id=21, logical_id=10,
                                 expected_link="s2-s3")
        audit, rows = builder.validate_run(
            RUN21, expected_physical_id=21, logical_id=10,
            expected_link="s2-s3", allow_failed_counter_reaudit=True,
        )
        self.assertEqual(audit["original_metadata_status"], "FAILED_INVALID")
        self.assertEqual(audit["admission_status"], "VALID")
        self.assertIn("corrected iperf2 sequence-counter", audit["forensic_reaudit"])
        self.assertEqual(audit["iperf_validation"]["client_receiver_accounted_minus_sender_count"], 1)
        self.assertEqual(len(rows), 660)
        self.assertEqual(metadata_path.read_bytes(), original)

    def test_candidate_with_both_recollections_preserves_original_failed_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source, manifest = temp / "source.csv", temp / "audit.csv"
            shutil.copy2(SOURCE, source)
            shutil.copy2(MANIFEST, manifest)
            source_before = builder.sha256(source)
            metadata_before = builder.sha256(RUN21 / "run_metadata.json")
            output = temp / "derived"
            summary = builder.build_candidate(source, manifest, RUN23, output, [RUN21])
            self.assertEqual(summary["rows"], 12912)
            self.assertEqual(summary["logical_experiments"], 19)
            provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["physical_to_logical_mapping"], {"21": 10, "23": 3})
            run21 = next(x for x in provenance["recollected_runs"] if x["source_physical_run_id"] == 21)
            self.assertEqual(run21["original_metadata_status"], "FAILED_INVALID")
            self.assertEqual(run21["admission_status"], "VALID")
            self.assertEqual(builder.sha256(source), source_before)
            self.assertEqual(builder.sha256(RUN21 / "run_metadata.json"), metadata_before)


if __name__ == "__main__":
    unittest.main()
