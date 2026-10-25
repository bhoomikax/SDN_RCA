"""Tests for configurable linear topologies and their use by the runner/graph builder."""

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pandas as pd

import experiment_runner_recollection as runner
from build_graph_multi import build_snapshots
from linear_topology import (
    LinearTopology,
    SUPPORTED_SWITCH_COUNTS,
    TARGET_VALID_EXPERIMENTS,
    assert_registries_disjoint,
    balanced_fault_assignment,
    registry_entry,
    topology_run_registry,
)
from telemetry_pipeline import is_adjacent_switch_link


class LinearTopologyTests(unittest.TestCase):
    def test_switch_host_and_link_counts_for_supported_sizes(self):
        for count, links in ((4, 3), (8, 7), (12, 11)):
            topology = LinearTopology(count)
            self.assertEqual(len(topology.switches), count)
            self.assertEqual(topology.hosts, ("h1", "h2"))
            self.assertEqual(topology.candidate_count, links)
            self.assertEqual(len(topology.candidate_links), count - 1)
            # hosts + switches, and h1-s1 + inter-switch + sN-h2 links
            self.assertEqual(len(topology.nodes), count + 2)
            self.assertEqual(len(topology.link_definitions), count + 1)
            self.assertEqual(topology.link_definitions[0][:2], ("h1", "s1"))
            self.assertEqual(topology.link_definitions[-1][:2], ("s%d" % count, "h2"))
            for index, link in enumerate(topology.candidate_links):
                self.assertEqual(link, "s%d-s%d" % (index + 1, index + 2))
        self.assertEqual(SUPPORTED_SWITCH_COUNTS, (4, 8, 12))
        with self.assertRaises(ValueError):
            LinearTopology(1)

    def test_four_switch_topology_matches_the_original_study(self):
        topology = LinearTopology(4)
        self.assertEqual(topology.switches, ("s1", "s2", "s3", "s4"))
        self.assertEqual(topology.candidate_links, ("s1-s2", "s2-s3", "s3-s4"))
        self.assertEqual(topology.bottleneck_link, "s2-s3")
        self.assertEqual(topology.link_definitions, (
            ("h1", "s1", None),
            ("s1", "s2", None),
            ("s2", "s3", {"bw": 10, "delay": "5ms"}),
            ("s3", "s4", None),
            ("s4", "h2", None),
        ))
        self.assertEqual(runner.SWITCHES, topology.switches)
        self.assertEqual(runner.LINK_DEFINITIONS, topology.link_definitions)
        self.assertEqual(list(topology.nodes), ["h1", "s1", "s2", "s3", "s4", "h2"])

    def test_bottleneck_is_the_middle_candidate_link(self):
        self.assertEqual(LinearTopology(8).bottleneck_link, "s4-s5")
        self.assertEqual(LinearTopology(12).bottleneck_link, "s6-s7")
        for count in SUPPORTED_SWITCH_COUNTS:
            topology = LinearTopology(count)
            bottlenecks = [params for _l, _r, params in topology.link_definitions if params]
            self.assertEqual(bottlenecks, [{"bw": 10, "delay": "5ms"}])

    def test_metadata_round_trip_and_tamper_detection(self):
        for count in SUPPORTED_SWITCH_COUNTS:
            metadata = json.loads(json.dumps(LinearTopology(count).to_metadata()))
            self.assertEqual(LinearTopology.from_metadata(metadata), LinearTopology(count))
        tampered = json.loads(json.dumps(LinearTopology(8).to_metadata()))
        tampered["candidate_links"][0] = "s1-s3"
        with self.assertRaisesRegex(ValueError, "candidate_links"):
            LinearTopology.from_metadata(tampered)

    def test_link_helpers(self):
        topology = LinearTopology(8)
        self.assertEqual(topology.link_endpoints("s4-s5"), ("s4", "s5"))
        self.assertEqual(topology.link_name("s5", "s4"), "s4-s5")
        self.assertEqual(topology.link_name("h2", "s8"), "s8-h2")
        self.assertEqual(topology.remote_switches("s4-s5"), ("s1", "s2", "s3", "s6", "s7", "s8"))
        with self.assertRaises(ValueError):
            topology.link_endpoints("h1-s1")
        with self.assertRaises(ValueError):
            topology.link_name("s1", "s3")
        for count in SUPPORTED_SWITCH_COUNTS:
            for link in LinearTopology(count).candidate_links:
                self.assertTrue(is_adjacent_switch_link(link))
        self.assertFalse(is_adjacent_switch_link("s1-s3"))
        self.assertFalse(is_adjacent_switch_link("h1-s1"))

    def test_balanced_fault_assignment_covers_every_candidate(self):
        for count in (8, 12):
            topology = LinearTopology(count)
            schedule = balanced_fault_assignment(topology.candidate_links, TARGET_VALID_EXPERIMENTS)
            counts = Counter(schedule)
            self.assertEqual(set(counts), set(topology.candidate_links))
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
            # The last candidate is still selectable; faults are not fixed to the middle link.
            self.assertIn(topology.candidate_links[-1], schedule)
            self.assertIn(topology.candidate_links[0], schedule)

    def test_registries_are_fixed_balanced_and_disjoint_from_four_switch_ids(self):
        eight = topology_run_registry(8)
        twelve = topology_run_registry(12)
        self.assertEqual(list(eight)[:3], [101, 102, 103])
        self.assertEqual(eight[101]["physical_run_id"], 1101)
        self.assertEqual(list(twelve)[:1], [201])
        self.assertEqual(twelve[201]["physical_run_id"], 1201)
        self.assertEqual(len(eight), 30)
        self.assertEqual(len(twelve), 60)
        # The extension kept the first thirty 12-switch assignments unchanged.
        self.assertEqual([twelve[201 + i]["fault_link"] for i in range(11)], list(LinearTopology(12).candidate_links))
        self.assertEqual(twelve[230]["physical_run_id"], 1230)
        self.assertEqual(len(set(e["physical_run_id"] for e in eight.values())), len(eight))
        self.assertTrue(assert_registries_disjoint(runner.LOGICAL_TO_PHYSICAL))
        self.assertEqual(registry_entry(8, 101, 1101)["fault_link"], "s1-s2")
        with self.assertRaises(ValueError):
            registry_entry(8, 101, 1102)
        with self.assertRaises(ValueError):
            registry_entry(4, 3, 23)

    def test_runner_directories_and_registry_resolution_per_topology(self):
        self.assertEqual(runner.run_directory(3, 23), runner.RUN_ROOT / "physical_23_logical_3")
        self.assertEqual(
            runner.run_directory(101, 1101, 8),
            runner.RUN_ROOT / "topology_8_switches" / "physical_1101_logical_101",
        )
        self.assertEqual(
            runner.run_directory(201, 1201, 12),
            runner.RUN_ROOT / "topology_12_switches" / "physical_1201_logical_201",
        )
        with self.assertRaises(ValueError):
            runner.run_directory(101, 1101, 4)
        with self.assertRaises(ValueError):
            runner.run_directory(3, 23, 8)
        with self.assertRaises(ValueError):
            runner.topology_for(6)
        self.assertEqual(runner.resolve_registry(3, 23)["fault_link"], "s3-s4")
        self.assertEqual(runner.resolve_registry(102, 1102, 8)["fault_link"], "s2-s3")

    def test_frozen_traffic_profiles_match_each_topology_bottleneck(self):
        for count, link, profile_id in (
            (4, "s2-s3", "udp_6mbps_s2s3_10mbps_v1"),
            (8, "s4-s5", "udp_6mbps_s4s5_10mbps_8sw_v1"),
            (12, "s6-s7", "udp_6mbps_s6s7_10mbps_12sw_v1"),
        ):
            profile = runner.load_traffic_profile(topology=LinearTopology(count))
            self.assertEqual(profile["profile_id"], profile_id)
            self.assertEqual(profile["bottleneck_link"], link)
            self.assertEqual(profile["offered_rate_mbps"], 6.0)
            self.assertEqual(profile["bottleneck_capacity_mbps"], 10.0)
            self.assertEqual(profile["phase_durations_seconds"], {"normal": 20, "fault": 20, "recovery": 20})
        with self.assertRaisesRegex(ValueError, "not the topology bottleneck"):
            runner.load_traffic_profile(
                runner.traffic_profile_path(LinearTopology(8)), topology=LinearTopology(12)
            )

    def test_target_link_accepts_any_registered_candidate_on_larger_topology(self):
        topology = LinearTopology(12)

        def intf(node_name, intf_name):
            return SimpleNamespace(node=SimpleNamespace(name=node_name), name=intf_name)

        links, peers, rows = [], {}, []
        for left, right, _params in topology.link_definitions:
            left_name = "%s-eth%d" % (left, 1 if left == "h1" else (2 if left != "s1" else 2))
            right_name = "%s-eth%d" % (right, 1 if right != "h2" else 0)
            if left == "h1":
                left_name = "h1-eth0"
            a, b = intf(left, left_name), intf(right, right_name)
            links.append(SimpleNamespace(intf1=a, intf2=b))
            peers[(left, left_name)] = (right, right_name)
            peers[(right, right_name)] = (left, left_name)
        port = 100
        for (switch, interface), (peer, peer_interface) in sorted(peers.items()):
            if switch in topology.switches:
                port += 1
                rows.append({
                    "switch": switch, "openflow_port": str(port), "interface_name": interface,
                    "peer_node": peer, "peer_interface": peer_interface,
                    "link": topology.link_name(switch, peer),
                })
        net = SimpleNamespace(links=links)
        for link in topology.candidate_links:
            target, interfaces, validated = runner._target_link(net, 999, peers, rows, target=link)
            self.assertEqual(target, link)
            self.assertEqual({row["switch"] for row in validated}, set(link.split("-")))
            self.assertEqual({intf.node.name for intf in interfaces}, set(link.split("-")))
        with self.assertRaisesRegex(ValueError, "cannot uniquely resolve"):
            runner._target_link(net, 999, peers, rows, target="s1-s3")

    def test_preflight_reports_topology_and_rejects_conflicting_bridges(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("telemetry.py", "telemetry_pipeline.py"):
                (Path(directory) / name).write_text("# stub\n", encoding="utf-8")
            with mock.patch.object(runner, "RUN_ROOT", Path(directory) / "runs"), \
                    mock.patch.object(runner, "PROJECT", Path(directory)), \
                    mock.patch.object(runner, "get_iperf_version", return_value="2.0.13"), \
                    mock.patch.object(runner.subprocess, "run",
                                      return_value=SimpleNamespace(stdout="s9\n")), \
                    mock.patch.object(runner.socket, "socket") as socket_factory:
                socket_factory.return_value = mock.Mock()
                with self.assertRaisesRegex(RuntimeError, "conflict"):
                    runner.preflight(201, 1201, 12)
            with mock.patch.object(runner, "RUN_ROOT", Path(directory) / "runs"), \
                    mock.patch.object(runner, "PROJECT", Path(directory)), \
                    mock.patch.object(runner, "get_iperf_version", return_value="2.0.13"), \
                    mock.patch.object(runner.subprocess, "run",
                                      return_value=SimpleNamespace(stdout="s9\n")), \
                    mock.patch.object(runner.socket, "socket") as socket_factory:
                socket_factory.return_value = mock.Mock()
                checks = runner.preflight(101, 1101, 8)
        self.assertEqual(checks["switch_count"], 8)
        self.assertEqual(checks["fault_link"], "s1-s2")
        self.assertEqual(len(checks["candidate_links"]), 7)
        self.assertEqual(checks["topology_spec"]["bottleneck_link"], "s4-s5")
        self.assertEqual(checks["traffic_profile"]["bottleneck_link"], "s4-s5")
        self.assertTrue(checks["output_dir"].endswith("physical_1101_logical_101"))

    def test_runtime_link_names_order_switches_numerically(self):
        self.assertEqual(runner.canonical_link_name("s10", "s9"), "s9-s10")
        self.assertEqual(runner.canonical_link_name("s11", "s12"), "s11-s12")
        self.assertEqual(runner.canonical_link_name("s3", "s2"), "s2-s3")
        # Host link names keep the historical four-switch spelling.
        self.assertEqual(runner.canonical_link_name("s4", "h2"), "h2-s4")
        self.assertEqual(runner.canonical_link_name("s1", "h1"), "h1-s1")
        topology = LinearTopology(12)
        for link in topology.candidate_links:
            left, right = link.split("-")
            self.assertEqual(runner.canonical_link_name(right, left), link)

    def test_graph_builder_lays_out_variable_switch_counts(self):
        topology = LinearTopology(8)
        rows = []
        for switch in topology.switches:
            for port in (1, 2):
                rows.append({
                    "experiment_id": 101, "timestamp": "2026-01-01 00:00:00", "switch": switch,
                    "port": port, "phase": "fault", "fault_type": "link_failure",
                    "fault_location": "s7-s8", "rx_packet_rate": 1.0, "tx_packet_rate": 2.0,
                    "rx_throughput_mbps": 3.0, "tx_throughput_mbps": 4.0,
                })
        snapshot = build_snapshots(pd.DataFrame(rows), topology)[0]
        self.assertEqual(snapshot["nodes"], list(topology.nodes))
        self.assertEqual(len(snapshot["edges"]), 9)
        self.assertEqual(snapshot["node_features"]["s8"], [2.0, 4.0, 6.0, 8.0])
        self.assertEqual(snapshot["node_features"]["h2"], [0.0] * 4)
        with self.assertRaisesRegex(ValueError, "outside the configured topology"):
            build_snapshots(pd.DataFrame(rows), LinearTopology(4))


if __name__ == "__main__":
    unittest.main()
