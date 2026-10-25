"""Tests for the N-switch candidate builder: admission rules, rejection, schema, uniqueness."""

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import build_topology_candidate as builder
from build_validated_candidate import DATASET_FIELDS
from experiment_runner_recollection import validate_iperf_completion
from linear_topology import LinearTopology, topology_run_registry
from telemetry_pipeline import TELEMETRY_FIELDS
from test_recollection_runner import iperf_client_output, iperf_server_output


BASE = datetime(2026, 1, 1, 0, 0, 0)


def make_run_dir(root, topology, logical, physical, fault_link, *, samples=8, tamper=None, mbps="6.29"):
    """Write a synthetic but internally consistent raw run directory."""
    run_dir = Path(root) / ("physical_%d_logical_%d" % (physical, logical))
    run_dir.mkdir(parents=True)
    mapping = []
    for index, switch in enumerate(topology.switches):
        left = "h1" if index == 0 else topology.switches[index - 1]
        right = "h2" if index == len(topology.switches) - 1 else topology.switches[index + 1]
        for port, peer in (("1", left), ("2", right)):
            peer_interface = "%s-eth%s" % (peer, "0" if peer.startswith("h") else ("2" if peer == left else "1"))
            mapping.append({"switch": switch, "openflow_port": port, "interface_name": "%s-eth%s" % (switch, port),
                            "peer_node": peer, "peer_interface": peer_interface,
                            "link": "-".join(sorted((switch, peer))) if peer.startswith("h") else topology.link_name(switch, peer)})
    rows = []
    for i in range(samples):
        stamp = (BASE + timedelta(seconds=i)).isoformat()
        for switch in topology.switches:
            for port in ("LOCAL", "1", "2"):
                row = {field: "0" for field in TELEMETRY_FIELDS}
                row.update({"timestamp": stamp, "switch": switch, "port": port,
                            "interface_name": switch if port == "LOCAL" else "%s-eth%s" % (switch, port),
                            "experiment_id": str(physical), "rx_packets": str(10 * i), "tx_packets": str(10 * i),
                            "rx_bytes": str(100 * i), "tx_bytes": str(100 * i),
                            "rx_packet_rate": "10.0" if i else "0.0", "tx_packet_rate": "10.0" if i else "0.0",
                            "rx_throughput_mbps": "0.5", "tx_throughput_mbps": "0.5"})
                rows.append(row)
    with (run_dir / "telemetry.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=TELEMETRY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (run_dir / "runtime_port_mapping.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("switch", "openflow_port", "interface_name", "peer_node", "peer_interface", "link"))
        writer.writeheader()
        writer.writerows(mapping)
    events = {"normal": 1, "fault": 3, "recovery": 6}
    phase_events = {name: (BASE + timedelta(seconds=sec)).replace(tzinfo=timezone.utc).isoformat() for name, sec in events.items()}
    with (run_dir / "phase_events.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("physical_run_id", "logical_experiment_id", "timestamp", "phase", "fault_type", "fault_location"))
        writer.writeheader()
        for phase in ("normal", "fault", "recovery"):
            writer.writerow({"physical_run_id": physical, "logical_experiment_id": logical, "timestamp": phase_events[phase],
                             "phase": phase, "fault_type": "none" if phase == "normal" else "link_failure",
                             "fault_location": "none" if phase == "normal" else fault_link})
    client_log, server_log = iperf_client_output(60, mbps=mbps), iperf_server_output(60, mbps=mbps)
    (run_dir / "iperf_client.log").write_text(client_log, encoding="utf-8")
    (run_dir / "iperf_server.log").write_text(server_log, encoding="utf-8")
    summary = validate_iperf_completion(client_returncode=0, server_returncode=0, client_log=client_log, server_log=server_log,
                                        requested_duration=60, client_elapsed=60.3, server_elapsed=78.0, requested_bandwidth_mbps=6.0)
    started = (BASE + timedelta(seconds=1)).replace(tzinfo=timezone.utc).isoformat()
    metadata = {
        "status": "COMPLETE", "physical_run_id": physical, "logical_experiment_id": logical, "fault_link": fault_link,
        "switch_count": topology.switch_count, "topology_spec": topology.to_metadata(),
        "traffic_profile": {"bottleneck_link": topology.bottleneck_link, "offered_rate_mbps": 6.0},
        "telemetry_rows": len(rows), "runtime_switch_port_mapping": mapping,
        "fault_target_runtime_mapping": [row for row in mapping if row["link"] == fault_link],
        "phase_events": phase_events,
        "iperf": {"completion_valid": True, "requested_duration_seconds": 60, "summary_validation": summary,
                  "processes": {label: {"pid": 100 + n, "returncode": 0, "started_at": started,
                                        "completed_at": (BASE + timedelta(seconds=70)).replace(tzinfo=timezone.utc).isoformat(),
                                        "elapsed_seconds": 60.3 if label == "client" else 78.0, "terminal_outcome": "exited"}
                                for n, label in enumerate(("client", "server"))}},
    }
    if tamper:
        tamper(run_dir, metadata)
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return run_dir


class TopologyCandidateBuilderTests(unittest.TestCase):
    def test_builds_candidate_from_valid_runs_with_manifest_and_mapping(self):
        topology = LinearTopology(8)
        registry = topology_run_registry(8)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            for logical in (101, 102, 107):
                entry = registry[logical]
                make_run_dir(root, topology, logical, entry["physical_run_id"], entry["fault_link"])
            output = Path(directory) / "candidate"
            result = builder.build_topology_candidate(8, root, output)
            self.assertEqual(result["logical_experiments"], 3)
            self.assertEqual(result["excluded"], 0)
            with (output / "candidate_dataset.csv").open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(tuple(reader.fieldnames), DATASET_FIELDS)
                rows = list(reader)
            self.assertEqual({row["experiment_id"] for row in rows}, {"101", "102", "107"})
            self.assertEqual(len(rows), 3 * 8 * 3 * 8)
            fault_rows = [row for row in rows if row["phase"] == "fault"]
            self.assertEqual({(r["experiment_id"], r["fault_location"]) for r in fault_rows},
                             {("101", "s1-s2"), ("102", "s2-s3"), ("107", "s7-s8")})
            self.assertTrue(all(r["fault_type"] == "none" and r["fault_location"] == "none" for r in rows if r["phase"] == "normal"))
            with (output / "experiment_manifest.csv").open(newline="", encoding="utf-8") as stream:
                manifest = list(csv.DictReader(stream))
            self.assertEqual([m["experiment_id"] for m in manifest], ["101", "102", "107"])
            self.assertEqual({m["switch_count"] for m in manifest}, {"8"})
            self.assertEqual({m["candidate_count"] for m in manifest}, {"7"})
            self.assertEqual(manifest[0]["fault_window_10s_timestamps"], "3")
            with (output / "link_port_mapping.csv").open(newline="", encoding="utf-8") as stream:
                mapping = list(csv.DictReader(stream))
            self.assertEqual(len(mapping), 14)
            self.assertEqual({m["link"] for m in mapping}, set(topology.candidate_links))
            provenance = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["admitted_count"], 3)
            self.assertEqual(provenance["topology"]["switch_count"], 8)
            self.assertEqual(provenance["experiments_per_link"], {"s1-s2": 1, "s2-s3": 1, "s7-s8": 1})
            with self.assertRaises(FileExistsError):
                builder.build_topology_candidate(8, root, output)

    def test_invalid_runs_are_excluded_with_reasons_not_fabricated(self):
        topology = LinearTopology(8)
        registry = topology_run_registry(8)

        def failed_status(_run_dir, metadata):
            metadata["status"] = "FAILED_INVALID"

        def wrong_link(_run_dir, metadata):
            metadata["fault_link"] = "s3-s4"
            metadata["fault_target_runtime_mapping"] = [r for r in metadata["runtime_switch_port_mapping"] if r["link"] == "s3-s4"]

        def missing_log(run_dir, _metadata):
            (run_dir / "iperf_server.log").unlink()

        def phase_outside(_run_dir, metadata):
            metadata["phase_events"]["recovery"] = "2030-01-01T00:00:00+00:00"

        def unregistered(_run_dir, metadata):
            metadata["logical_experiment_id"] = 199

        def other_topology(_run_dir, metadata):
            metadata["switch_count"] = 12
            metadata["topology_spec"] = LinearTopology(12).to_metadata()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            make_run_dir(root, topology, 101, 1101, "s1-s2")
            make_run_dir(root, topology, 102, 1102, "s2-s3", tamper=failed_status)
            make_run_dir(root, topology, 103, 1103, "s3-s4", tamper=missing_log)
            make_run_dir(root, topology, 104, 1104, "s4-s5", tamper=wrong_link)
            make_run_dir(root, topology, 105, 1105, "s5-s6", tamper=phase_outside)
            make_run_dir(root, topology, 106, 1106, "s6-s7", tamper=unregistered)
            make_run_dir(root, topology, 107, 1107, "s7-s8", tamper=other_topology)
            # A run that completed but only paced half the offered load.
            make_run_dir(root, topology, 109, 1109, "s2-s3", mbps="3.02")
            # A directory whose telemetry is duplicated/corrupted.
            dup = make_run_dir(root, topology, 108, 1108, "s1-s2")
            text = (dup / "telemetry.csv").read_text(encoding="utf-8").splitlines()
            (dup / "telemetry.csv").write_text("\n".join(text + [text[1]]) + "\n", encoding="utf-8")
            output = Path(directory) / "candidate"
            result = builder.build_topology_candidate(8, root, output)
            self.assertEqual(result["logical_experiments"], 1)
            self.assertEqual(result["excluded"], 8)
            with (output / "exclusion_report.csv").open(newline="", encoding="utf-8") as stream:
                excluded = {Path(r["run_dir"]).name: r["reason"] for r in csv.DictReader(stream)}
            self.assertIn("not COMPLETE", excluded["physical_1102_logical_102"])
            self.assertIn("missing raw artifact", excluded["physical_1103_logical_103"])
            self.assertIn("registry", excluded["physical_1104_logical_104"])
            self.assertIn("phase", excluded["physical_1105_logical_105"].lower())
            self.assertIn("identity", excluded["physical_1106_logical_106"])
            self.assertIn("switch_count", excluded["physical_1107_logical_107"])
            self.assertIn("achieved 3.02 Mbps", excluded["physical_1109_logical_109"])
            self.assertTrue("duplicate" in excluded["physical_1108_logical_108"].lower()
                            or "row count" in excluded["physical_1108_logical_108"].lower())
            self.assertEqual(set(registry) >= {101, 102}, True)

    def test_rejects_duplicate_experiment_identity_and_inconsistent_mapping(self):
        topology = LinearTopology(8)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            make_run_dir(root, topology, 101, 1101, "s1-s2")
            # Same identity under a differently named directory is rejected by name/identity check.
            other = make_run_dir(root, topology, 102, 1102, "s2-s3")
            metadata = json.loads((other / "run_metadata.json").read_text(encoding="utf-8"))
            metadata["logical_experiment_id"], metadata["physical_run_id"] = 101, 1101
            (other / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            result = builder.build_topology_candidate(8, root, Path(directory) / "candidate_a")
            self.assertEqual(result["logical_experiments"], 1)
            self.assertEqual(result["excluded"], 1)

        def swap_ports(run_dir, metadata):
            for row in metadata["runtime_switch_port_mapping"]:
                if row["switch"] == "s3":
                    row["openflow_port"] = "9" if row["openflow_port"] == "1" else "8"
            with (run_dir / "runtime_port_mapping.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=("switch", "openflow_port", "interface_name", "peer_node", "peer_interface", "link"))
                writer.writeheader()
                writer.writerows(metadata["runtime_switch_port_mapping"])
            metadata["fault_target_runtime_mapping"] = [r for r in metadata["runtime_switch_port_mapping"] if r["link"] == metadata["fault_link"]]
            rows = []
            with (run_dir / "telemetry.csv").open(newline="", encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    if row["switch"] == "s3" and row["port"] != "LOCAL":
                        row["port"] = "9" if row["port"] == "1" else "8"
                    rows.append(row)
            with (run_dir / "telemetry.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=TELEMETRY_FIELDS)
                writer.writeheader()
                writer.writerows(rows)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "raw"
            make_run_dir(root, topology, 101, 1101, "s1-s2")
            make_run_dir(root, topology, 102, 1102, "s2-s3", tamper=swap_ports)
            with self.assertRaisesRegex(ValueError, "endpoint mapping differs"):
                builder.build_topology_candidate(8, root, Path(directory) / "candidate_b")


if __name__ == "__main__":
    unittest.main()
