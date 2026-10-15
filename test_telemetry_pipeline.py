"""Lightweight offline tests for telemetry paths, schemas, and merge guards."""

import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from merge_experiments import build_master_dataset, write_master_dataset
from telemetry import collect, get_port_stats, parse_port_interfaces
from telemetry_pipeline import (
    PHASE_FIELDS,
    TELEMETRY_FIELDS,
    collector_command,
    experiment_paths,
    read_phase_csv,
    read_telemetry_csv,
)


def sample_stats():
    return {
        "1": {
            "rx_packets": 10,
            "rx_bytes": 1000,
            "rx_dropped": 0,
            "tx_packets": 20,
            "tx_bytes": 2000,
            "tx_dropped": 0,
        }
    }


def write_sample_files(directory, experiment_id=7, *, telemetry_id=None):
    telemetry_path, phase_path = experiment_paths(directory, experiment_id)
    base = datetime(2026, 1, 1)
    telemetry_rows = []
    for second in (0, 21, 41):
        row = {
            "timestamp": (base + timedelta(seconds=second)).isoformat(),
            "switch": "s1",
            "port": "1",
            "interface_name": "s1-eth1",
            "rx_packets": 10 + second,
            "rx_bytes": 1000 + second,
            "rx_dropped": 0,
            "tx_packets": 20 + second,
            "tx_bytes": 2000 + second,
            "tx_dropped": 0,
            "rx_packet_rate": 1,
            "tx_packet_rate": 1,
            "rx_throughput_mbps": 0.008,
            "tx_throughput_mbps": 0.008,
            "experiment_id": experiment_id if telemetry_id is None else telemetry_id,
        }
        telemetry_rows.append(row)
    pd.DataFrame(telemetry_rows).to_csv(telemetry_path, index=False)

    phase_rows = [
        {
            "experiment_id": experiment_id,
            "timestamp": (base + timedelta(seconds=second)).isoformat(),
            "phase": phase,
            "fault_type": "none" if phase == "normal" else "link_failure",
            "fault_location": "none" if phase == "normal" else "s1-s2",
        }
        for phase, second in (("normal", 0), ("fault", 21), ("recovery", 41))
    ]
    pd.DataFrame(phase_rows, columns=PHASE_FIELDS).to_csv(phase_path, index=False)
    return telemetry_path, phase_path


class TelemetryPipelineTests(unittest.TestCase):
    def test_runtime_openflow_port_interface_parser(self):
        output = """OFPT_FEATURES_REPLY (OF1.3):\n  1(s1-eth1): addr:00:00:00:00:00:01\n  2(s1-eth2): addr:00:00:00:00:00:02\n  LOCAL(s1): addr:00:00:00:00:00:00\n"""
        self.assertEqual(
            parse_port_interfaces(output),
            {"1": "s1-eth1", "2": "s1-eth2", "LOCAL": "s1"},
        )

    def test_port_stats_join_live_openflow_interface_names(self):
        show = "  1(s1-eth1): addr:00:00:00:00:00:01\n  LOCAL(s1): addr:00:00:00:00:00:00\n"
        counters = """OFPST_PORT reply (OF1.3): 2 ports\nport 1: rx pkts=10, bytes=1000, drop=0, errs=0, frame=0, over=0, crc=0\n    tx pkts=20, bytes=2000, drop=0, errs=0, coll=0\nport LOCAL: rx pkts=0, bytes=0, drop=0, errs=0, frame=0, over=0, crc=0\n    tx pkts=0, bytes=0, drop=0, errs=0, coll=0\n"""
        with patch(
            "telemetry.subprocess.run",
            side_effect=[
                SimpleNamespace(stdout=show),
                SimpleNamespace(stdout=counters),
            ],
        ):
            stats = get_port_stats("s1")
        self.assertEqual(stats["1"]["interface_name"], "s1-eth1")
        self.assertEqual(stats["1"]["rx_packets"], 10)
        self.assertEqual(stats["LOCAL"]["interface_name"], "s1")

    def test_experiment_paths_and_collector_handoff(self):
        telemetry_path, phase_path = experiment_paths("experiments", 10)
        self.assertEqual(telemetry_path, Path("experiments/telemetry_10.csv"))
        self.assertEqual(phase_path, Path("experiments/phases_10.csv"))
        self.assertEqual(
            collector_command("telemetry.py", telemetry_path, 10, "python3"),
            [
                "python3",
                "telemetry.py",
                "--output",
                str(Path("experiments") / "telemetry_10.csv"),
                "--experiment-id",
                "10",
            ],
        )

    def test_collector_writes_requested_schema_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "telemetry_10.csv"
            tick = [0.0]

            def clock():
                return tick[0]

            def sleep(seconds):
                tick[0] += seconds

            count = collect(
                output,
                10,
                duration=0.5,
                interval=1,
                switches=("s1",),
                stats_reader=lambda _switch: sample_stats(),
                clock=clock,
                sleep=sleep,
            )
            self.assertEqual(count, 1)
            with output.open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(tuple(reader.fieldnames), TELEMETRY_FIELDS)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["interface_name"], "UNVERIFIED")
            with self.assertRaises(FileExistsError):
                collect(output, 10, duration=0)

    def test_merge_reads_per_experiment_file_and_keeps_existing_phase_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry_path, _ = write_sample_files(directory)
            # Legacy experiment CSVs lack an experiment_id column; the filename
            # and matching phase log remain their experiment identity.
            legacy = pd.read_csv(telemetry_path).drop(
                columns=["experiment_id", "interface_name"]
            )
            legacy.to_csv(telemetry_path, index=False)
            merged = build_master_dataset(directory, (7,))
            self.assertEqual(set(merged.experiment_id), {7})
            self.assertEqual(set(merged.interface_name), {"UNVERIFIED"})
            self.assertEqual(merged.phase.tolist(), ["normal", "fault", "recovery"])
            self.assertEqual(
                merged.fault_location.tolist(), ["none", "s1-s2", "s1-s2"]
            )

    def test_missing_file_empty_csv_and_missing_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry_path, phase_path = experiment_paths(directory, 7)
            with self.assertRaises(FileNotFoundError):
                read_telemetry_csv(telemetry_path, 7)
            with self.assertRaises(FileNotFoundError):
                read_phase_csv(phase_path, 7)

            telemetry_path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Empty telemetry"):
                read_telemetry_csv(telemetry_path, 7)

            pd.DataFrame([{"timestamp": "2026-01-01"}]).to_csv(
                telemetry_path, index=False
            )
            with self.assertRaisesRegex(ValueError, "missing columns"):
                read_telemetry_csv(telemetry_path, 7)

            phase_path.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Empty phase"):
                read_phase_csv(phase_path, 7)
            pd.DataFrame([{"experiment_id": 7}]).to_csv(phase_path, index=False)
            with self.assertRaisesRegex(ValueError, "missing columns"):
                read_phase_csv(phase_path, 7)

    def test_inconsistent_ids_duplicate_rows_and_phase_events_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry_path, phase_path = write_sample_files(
                directory, telemetry_id=8
            )
            with self.assertRaisesRegex(ValueError, "experiment IDs inconsistent"):
                read_telemetry_csv(telemetry_path, 7)

            write_sample_files(directory)
            telemetry = pd.read_csv(telemetry_path)
            pd.concat([telemetry, telemetry.iloc[[0]]]).to_csv(
                telemetry_path, index=False
            )
            with self.assertRaisesRegex(ValueError, "duplicate timestamp"):
                read_telemetry_csv(telemetry_path, 7)

            phases = pd.read_csv(phase_path)
            phases.loc[1, "experiment_id"] = 8
            phases.to_csv(phase_path, index=False)
            with self.assertRaisesRegex(ValueError, "IDs inconsistent"):
                read_phase_csv(phase_path, 7)

            write_sample_files(directory)
            phases = pd.read_csv(phase_path)
            phases.loc[2, "phase"] = "fault"
            phases.to_csv(phase_path, index=False)
            with self.assertRaisesRegex(ValueError, "duplicate phase"):
                read_phase_csv(phase_path, 7)

    def test_merge_rejects_duplicate_requested_ids_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "contains duplicates"):
                build_master_dataset(directory, (7, 7))

            output = Path(directory) / "existing.csv"
            output.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_master_dataset(pd.DataFrame(), output)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_merge_rejects_phase_log_outside_telemetry_time_range(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry_path, phase_path = write_sample_files(directory)
            phases = pd.read_csv(phase_path)
            phases["timestamp"] = (
                pd.to_datetime(phases["timestamp"]) + pd.Timedelta(days=1)
            ).astype(str)
            phases.to_csv(phase_path, index=False)
            with self.assertRaisesRegex(ValueError, "outside its telemetry recording range"):
                build_master_dataset(directory, (7,))


if __name__ == "__main__":
    unittest.main()
