"""Offline guard tests for the new, opt-in recollection runner."""

import csv
from contextlib import ExitStack
import json
import re
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import experiment_runner_recollection as runner
from experiment_runner_recollection import (
    FAULT_LINK_BY_LOGICAL,
    LOGICAL_TO_PHYSICAL,
    assert_run_paths_available,
    finalize_run_metadata,
    record_normal_phase_after_sample,
    run_directory,
    _target_link,
    validate_event_coverage,
    wait_for_first_valid_sample,
)
from telemetry_pipeline import TELEMETRY_FIELDS


BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def iso(seconds):
    return (BASE_TIME + timedelta(seconds=seconds)).isoformat()


def telemetry_row(timestamp=None):
    row = {field: "0" for field in TELEMETRY_FIELDS}
    row.update({
        "timestamp": timestamp if timestamp is not None else iso(0),
        "switch": "s1",
        "port": "1",
        "interface_name": "s1-eth1",
        "experiment_id": "20",
    })
    return row


def phase_events(normal=1, fault=2, recovery=3):
    return {name: iso(value) for name, value in (
        ("normal", normal), ("fault", fault), ("recovery", recovery)
    )}


def iperf_client_output(duration, sent=100, lost=0, total=100):
    sender = f"[  3] 0.0- {duration:.1f} sec 512 KBytes 1.05 Mbits/sec\n"
    receiver = (
        f"[  3] 0.0- {duration:.1f} sec 512 KBytes 1.05 Mbits/sec "
        f"0.136 ms {lost}/ {total} (0%)\n"
    )
    return (
        "[ ID] Interval       Transfer     Bandwidth\n" + sender
        + f"[  3] Sent {sent} datagrams\n[  3] Server Report:\n" + receiver
    )


def iperf_server_output(duration, lost=0, total=100):
    return (
        "[ ID] Interval       Transfer     Bandwidth        Jitter   Lost/Total Datagrams\n"
        + f"[  3] 0.0- {duration:.1f} sec 512 KBytes 1.05 Mbits/sec "
        + f"0.136 ms {lost}/ {total} (0%)\n"
    )


class LiveCollectorStub:
    returncode = None

    def poll(self):
        return None


class SampleCheckingWriter:
    def __init__(self, path):
        self.path = path
        self.rows = []

    def writerow(self, row):
        with self.path.open(newline="", encoding="utf-8") as stream:
            parsed = list(csv.DictReader(stream))
        if not parsed or not parsed[0]["timestamp"]:
            raise AssertionError("phase was recorded before a valid sample existed")
        self.rows.append(row)


class NoopStream:
    def flush(self):
        pass


def runtime_target_fixture(mapping_change=None):
    s3 = SimpleNamespace(name="s3")
    s4 = SimpleNamespace(name="s4")
    left = SimpleNamespace(node=s3, name="s3-eth2")
    right = SimpleNamespace(node=s4, name="s4-eth1")
    net = SimpleNamespace(links=[SimpleNamespace(intf1=left, intf2=right)])
    peers = {
        ("s3", "s3-eth2"): ("s4", "s4-eth1"),
        ("s4", "s4-eth1"): ("s3", "s3-eth2"),
    }
    rows = [
        {"switch": "s3", "openflow_port": "9", "interface_name": "s3-eth2",
         "peer_node": "s4", "peer_interface": "s4-eth1", "link": "s3-s4"},
        {"switch": "s4", "openflow_port": "17", "interface_name": "s4-eth1",
         "peer_node": "s3", "peer_interface": "s3-eth2", "link": "s3-s4"},
    ]
    if mapping_change:
        mapping_change(rows)
    return net, peers, rows


class FakeNetwork:
    def __init__(self, links, iperf_mode="success"):
        self.links = links
        self.stopped = False
        self.iperf_mode = iperf_mode
        self.iperf_processes = []

    def start(self):
        pass

    def stop(self):
        self.stopped = True

    def get(self, name):
        return FakeHost(name, self.iperf_mode, self.iperf_processes)


class FakeIperfProcess:
    def __init__(self, role, mode, command, stdout):
        self.role = role
        self.mode = mode
        self.command = command
        self.wait_timeouts = []
        self.returncode = 2 if role == "server" and mode == "premature_server" else None
        self.pid = 100 if role == "client" else 101
        transfer_duration = 3
        if mode == "missing_summary" and role == "client":
            output = "[ 3] local connected with peer\n"
        else:
            output = (iperf_server_output(transfer_duration) if role == "server"
                      else iperf_client_output(transfer_duration))
        if stdout is not None:
            stdout.write(output)
            stdout.flush()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.wait_timeouts.append(timeout)
        if self.mode in ("client_timeout", "cleanup_failure") and self.role == "client" and self.returncode is None:
            raise runner.subprocess.TimeoutExpired("iperf-client", timeout)
        if self.mode == "server_timeout" and self.role == "server" and self.returncode is None:
            raise runner.subprocess.TimeoutExpired("iperf-server", timeout)
        if (
            self.mode == "server_delayed_exit"
            and self.role == "server"
            and self.returncode is None
            and timeout < 18.0
        ):
            raise runner.subprocess.TimeoutExpired("iperf-server", timeout)
        if self.returncode is None:
            self.returncode = 5 if (
                (self.mode == "client_nonzero" and self.role == "client")
                or (self.mode == "server_nonzero" and self.role == "server")
            ) else 0
        return self.returncode

    def terminate(self):
        if self.mode == "cleanup_failure":
            raise OSError("mock iperf terminate failure")
        self.returncode = -15

    def kill(self):
        if self.mode == "cleanup_failure":
            raise OSError("mock iperf kill failure")
        self.returncode = -9


class FakeHost:
    def __init__(self, name, mode, processes):
        self.name = name
        self.mode = mode
        self.processes = processes

    def popen(self, command, **kwargs):
        role = "server" if "-s" in command else "client"
        process = FakeIperfProcess(role, self.mode, command, kwargs.get("stdout"))
        self.processes.append(process)
        return process


class FakeCollector:
    def __init__(self, path, physical_id, mode, sample_end=6):
        self.path = Path(path)
        self.returncode = None
        fields = TELEMETRY_FIELDS
        rows = []
        if mode == "valid":
            rows = [telemetry_row(iso(-1)), telemetry_row(iso(sample_end))]
        elif mode == "malformed":
            rows = [telemetry_row("not-a-timestamp")]
        elif mode == "wrong_id":
            rows = [telemetry_row(iso(0))]
        elif mode == "early_exit":
            self.returncode = 7

        for sample in rows:
            sample["experiment_id"] = "999" if mode == "wrong_id" else str(physical_id)
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


class RecollectionRunnerTests(unittest.TestCase):
    def run_mocked_orchestration(
        self, project, *, collector_mode="valid", sample_end=6,
        mapping_change=None, stop_failure=False, physical_id=None,
        iperf_mode="success",
    ):
        physical_id = runner.LOGICAL_TO_PHYSICAL[3] if physical_id is None else physical_id
        run_root = Path(project) / "recollection_runs"
        out_dir = run_root / f"physical_{physical_id}_logical_3"
        net_fixture, peers, rows = runtime_target_fixture(mapping_change)
        net = FakeNetwork(net_fixture.links, iperf_mode)
        if stop_failure:
            net.stop = mock.Mock(side_effect=RuntimeError("mock stop failure"))
        popen_calls = []

        def write_mapping(_net, path):
            actual_peers = {}
            for link in _net.links:
                actual_peers[(link.intf1.node.name, link.intf1.name)] = (
                    link.intf2.node.name, link.intf2.name
                )
                actual_peers[(link.intf2.node.name, link.intf2.name)] = (
                    link.intf1.node.name, link.intf1.name
                )
            with Path(path).open("x", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=(
                    "switch", "openflow_port", "interface_name", "peer_node",
                    "peer_interface", "link",
                ))
                writer.writeheader()
                writer.writerows(rows)
            return actual_peers, {}, rows

        def start_collector(command, cwd=None):
            popen_calls.append((command, cwd))
            return FakeCollector(command[-3], int(command[-2]), collector_mode, sample_end)

        original_record_normal = runner.record_normal_phase_after_sample

        def record_normal_with_test_clock(*args, **kwargs):
            kwargs["timestamp_func"] = lambda: runner.now_iso()
            return original_record_normal(*args, **kwargs)

        def preflight(logical_id, physical_id):
            directory = runner.run_directory(logical_id, physical_id)
            runner.assert_run_paths_available(directory, project, physical_id)
            traffic_profile = runner.load_traffic_profile()
            traffic_profile["phase_durations_seconds"] = {
                "normal": 1, "fault": 1, "recovery": 1,
            }
            return {
                "logical_experiment_id": logical_id,
                "physical_run_id": physical_id,
                "fault_link": FAULT_LINK_BY_LOGICAL[logical_id],
                "output_dir": str(directory),
                "controller": "mocked",
                "existing_ovs_bridges": [],
                "historical_experiment_files": "not used",
                "traffic_profile": traffic_profile,
                "iperf_version": "2.0.13",
            }

        import_mininet = types.ModuleType("mininet")
        import_mininet.__path__ = []
        mininet_log = types.ModuleType("mininet.log")
        mininet_log.setLogLevel = mock.Mock()
        import_mininet.log = mininet_log
        # run start, normal event, server start, client start, fault, recovery,
        # client completion, server completion, finalization.
        event_clock = iter((
            iso(-2), iso(0), iso(-1), iso(-1), iso(2), iso(4), iso(5), iso(6), iso(7),
        ))
        fault_action = mock.Mock()
        caught = None
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(sys.modules, {
                "mininet": import_mininet, "mininet.log": mininet_log,
            }))
            stack.enter_context(mock.patch.object(runner, "PROJECT", Path(project)))
            stack.enter_context(mock.patch.object(runner, "RUN_ROOT", run_root))
            stack.enter_context(mock.patch.object(runner, "preflight", side_effect=preflight))
            stack.enter_context(mock.patch.object(runner, "_create_network", return_value=net))
            stack.enter_context(mock.patch.object(runner, "_runtime_mapping", side_effect=write_mapping))
            stack.enter_context(mock.patch.object(
                runner, "record_normal_phase_after_sample", side_effect=record_normal_with_test_clock
            ))
            stack.enter_context(mock.patch.object(runner.subprocess, "Popen", side_effect=start_collector))
            stack.enter_context(mock.patch.object(runner, "_set_link", fault_action))
            stack.enter_context(mock.patch.object(runner.time, "sleep"))
            stack.enter_context(mock.patch.object(
                runner, "now_iso", side_effect=lambda: next(event_clock, iso(6))
            ))
            stack.enter_context(mock.patch.object(runner, "FIRST_SAMPLE_TIMEOUT_SECONDS", 0.01))
            stack.enter_context(
                mock.patch.object(runner.os, "geteuid", return_value=0, create=True)
            )
            try:
                runner.run(3, physical_id, normal_seconds=1, fault_seconds=1, recovery_seconds=1)
            except Exception as exc:
                caught = exc
        return out_dir, caught, fault_action, net, popen_calls

    def test_reserved_physical_mapping_is_explicit(self):
        self.assertEqual(LOGICAL_TO_PHYSICAL, {
            3: 23, 10: 21, 20: 24, 21: 25, 22: 26, 23: 27, 24: 28, 25: 29,
            26: 30, 27: 31,
        })
        self.assertEqual(FAULT_LINK_BY_LOGICAL, {
            3: "s3-s4", 10: "s2-s3", 20: "s1-s2", 21: "s1-s2",
            22: "s2-s3", 23: "s2-s3", 24: "s3-s4", 25: "s3-s4",
            26: "s2-s3", 27: "s2-s3",
        })
        self.assertEqual(runner.RUN_PURPOSE_BY_LOGICAL[26], "traffic_profile_pilot_only")
        self.assertEqual(runner.RUN_PURPOSE_BY_LOGICAL[27], "traffic_profile_pilot_retry_only")

    def test_server_natural_exit_grace_handles_delayed_iperf2_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, _fault, net, _calls = self.run_mocked_orchestration(
                directory, iperf_mode="server_delayed_exit"
            )
            self.assertIsNone(error)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "COMPLETE")
            self.assertEqual(
                metadata["iperf"]["server_wait_timeout_seconds"],
                runner.IPERF_SERVER_WAIT_TIMEOUT_SECONDS,
            )
            server_process = next(
                process for process in net.iperf_processes if process.role == "server"
            )
            self.assertEqual(
                server_process.wait_timeouts,
                [runner.IPERF_SERVER_WAIT_TIMEOUT_SECONDS],
            )

    def test_run_rejects_phase_durations_different_from_profile(self):
        profile = runner.load_traffic_profile()
        preflight = {
            "traffic_profile": profile,
        }
        with mock.patch.object(runner.os, "geteuid", return_value=0, create=True):
            with mock.patch.object(runner, "preflight", return_value=preflight):
                with self.assertRaisesRegex(ValueError, "match the frozen traffic profile"):
                    runner.run(3, 23, normal_seconds=1, fault_seconds=1, recovery_seconds=1)

    def test_versioned_udp_profile_respects_bottleneck_margin(self):
        profile = runner.load_traffic_profile()
        self.assertEqual(profile["profile_id"], "udp_6mbps_s2s3_10mbps_v1")
        self.assertEqual(profile["offered_rate_mbps"], 6.0)
        self.assertEqual(profile["bottleneck_capacity_mbps"], 10.0)
        self.assertLessEqual(
            profile["offered_rate_mbps"],
            profile["bottleneck_capacity_mbps"] * 0.7,
        )
        self.assertEqual(runner.iperf_bandwidth_argument(profile["offered_rate_mbps"]), "6M")

    def test_traffic_profile_rejects_oversubscription(self):
        profile = runner.load_traffic_profile()
        profile["offered_rate_mbps"] = 7.5
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversubscribed.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "at most 70%"):
                runner.load_traffic_profile(path)

    def test_preflight_requires_iperf2(self):
        with mock.patch.object(
            runner.subprocess,
            "run",
            return_value=SimpleNamespace(
                stdout="", stderr="iperf version 2.0.13", returncode=1,
            ),
        ) as run:
            self.assertEqual(runner.get_iperf_version(), "2.0.13")
        run.assert_called_once_with(
            ["iperf", "--version"], capture_output=True, text=True,
        )
        with mock.patch.object(
            runner.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="iperf 3.14", stderr="", returncode=0),
        ):
            with self.assertRaisesRegex(RuntimeError, "Expected iperf2"):
                runner.get_iperf_version()
        with mock.patch.object(
            runner.subprocess,
            "run",
            return_value=SimpleNamespace(stdout="", stderr="query failure", returncode=2),
        ):
            with self.assertRaisesRegex(RuntimeError, "exited with status 2"):
                runner.get_iperf_version()

    def test_outputs_are_isolated_by_physical_and_logical_ids(self):
        self.assertEqual(
            run_directory(3, 23).name,
            "physical_23_logical_3",
        )
        self.assertEqual(
            run_directory(10, 21).name,
            "physical_21_logical_10",
        )

    def test_wrong_or_occupied_id_pair_is_rejected(self):
        with self.assertRaises(ValueError):
            run_directory(3, 20)
        with self.assertRaises(ValueError):
            run_directory(10, 22)

    def test_normal_event_is_recorded_only_after_first_valid_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "telemetry.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=TELEMETRY_FIELDS)
                writer.writeheader()
                writer.writerow(telemetry_row())
            event_time = iso(1)
            writer = SampleCheckingWriter(path)
            first, event = record_normal_phase_after_sample(
                path, LiveCollectorStub(), 20, writer, NoopStream(),
                3, 20, "s3-s4", timeout=0.1,
                timestamp_func=lambda: event_time,
            )
            self.assertEqual(first, iso(0))
            self.assertEqual(event, event_time)
            self.assertEqual(writer.rows[0]["phase"], "normal")

    def test_collector_timeout_without_a_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(TimeoutError, "waiting for a valid first"):
                wait_for_first_valid_sample(
                    Path(directory) / "not_created.csv", LiveCollectorStub(), 20,
                    timeout=0.02, poll_interval=0.002,
                )

    def test_collector_exit_without_a_sample_fails_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            dead = SimpleNamespace(returncode=2, poll=lambda: 2)
            with self.assertRaisesRegex(RuntimeError, "exited before a valid first sample"):
                wait_for_first_valid_sample(
                    Path(directory) / "missing.csv", dead, 20, timeout=1,
                )

    def test_malformed_first_sample_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "telemetry.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=TELEMETRY_FIELDS)
                writer.writeheader()
                writer.writerow(telemetry_row("not-a-timestamp"))
            with self.assertRaisesRegex(TimeoutError, "Malformed timestamp"):
                wait_for_first_valid_sample(path, LiveCollectorStub(), 20, timeout=0.02)

    def test_normal_event_before_first_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Normal event precedes"):
            validate_event_coverage(iso(2), iso(5), phase_events(1, 3, 4))

    def test_fault_event_after_last_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Fault event is after"):
            validate_event_coverage(iso(0), iso(4), phase_events(1, 5, 6))

    def test_recovery_event_after_last_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Recovery event is after"):
            validate_event_coverage(iso(0), iso(4), phase_events(1, 2, 5))

    def test_phase_events_must_be_strictly_ordered(self):
        with self.assertRaisesRegex(ValueError, "Fault event must be after"):
            validate_event_coverage(iso(0), iso(4), phase_events(1, 1, 3))
        with self.assertRaisesRegex(ValueError, "Recovery event must be after"):
            validate_event_coverage(iso(0), iso(4), phase_events(1, 2, 2))

    def test_missing_or_malformed_event_timestamps_are_rejected(self):
        missing = phase_events()
        del missing["fault"]
        with self.assertRaisesRegex(ValueError, "Missing required phase"):
            validate_event_coverage(iso(0), iso(4), missing)
        malformed = phase_events()
        malformed["recovery"] = "bad-time"
        with self.assertRaisesRegex(ValueError, "Malformed timestamp"):
            validate_event_coverage(iso(0), iso(4), malformed)

    def test_missing_or_malformed_sample_timestamps_fail_closed(self):
        metadata = {"status": "RUNNING_INVALID_UNTIL_COMPLETE"}
        with self.assertRaisesRegex(ValueError, "no valid sample rows"):
            finalize_run_metadata(metadata, [], phase_events(), 20)
        self.assertEqual(metadata["status"], "FAILED_INVALID")
        self.assertIn("validation_failure", metadata)

        metadata = {"status": "RUNNING_INVALID_UNTIL_COMPLETE"}
        row = telemetry_row("")
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            finalize_run_metadata(metadata, [row], phase_events(), 20)
        self.assertEqual(metadata["status"], "FAILED_INVALID")

        metadata = {"status": "RUNNING_INVALID_UNTIL_COMPLETE"}
        row = telemetry_row("bad-sample-time")
        with self.assertRaisesRegex(ValueError, "Malformed timestamp"):
            finalize_run_metadata(metadata, [row], phase_events(), 20)
        self.assertEqual(metadata["status"], "FAILED_INVALID")

    def test_fully_covered_ordered_events_are_the_only_complete_case(self):
        metadata = {"status": "RUNNING_INVALID_UNTIL_COMPLETE"}
        rows = [telemetry_row(iso(0)), telemetry_row(iso(4))]
        finalize_run_metadata(metadata, rows, phase_events(), 20)
        self.assertEqual(metadata["status"], "COMPLETE")
        self.assertEqual(metadata["telemetry_rows"], 2)
        self.assertEqual(metadata["telemetry_start"], iso(0))
        self.assertEqual(metadata["telemetry_end"], iso(4))

    def test_occupied_output_directory_refuses_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            occupied = project / "recollection_runs" / "physical_23_logical_3"
            occupied.mkdir(parents=True)
            with self.assertRaisesRegex(FileExistsError, "Refusing to reuse"):
                assert_run_paths_available(occupied, project, 23)

    def test_existing_historical_physical_id_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            experiments = project / "experiments"
            experiments.mkdir()
            (experiments / "telemetry_23.csv").write_text("preserve", encoding="utf-8")
            proposed = project / "recollection_runs" / "physical_23_logical_3"
            with self.assertRaisesRegex(FileExistsError, "Physical run ID already exists"):
                assert_run_paths_available(proposed, project, 23)

    def test_target_mapping_accepts_actual_dynamic_ports_and_rejects_conflicts(self):
        net, peers, rows = runtime_target_fixture()
        target, interfaces, recorded = _target_link(net, 3, peers, rows)
        self.assertEqual(target, "s3-s4")
        self.assertEqual([row["openflow_port"] for row in recorded], ["9", "17"])
        self.assertEqual(interfaces[0].name, "s3-eth2")

        bad_net, bad_peers, bad_rows = runtime_target_fixture(
            lambda values: values[0].update(peer_interface="wrong-interface")
        )
        with self.assertRaisesRegex(ValueError, "Target mapping validation failed"):
            _target_link(bad_net, 3, bad_peers, bad_rows)

        duplicate_net, duplicate_peers, duplicate_rows = runtime_target_fixture()
        duplicate_rows.append(dict(duplicate_rows[0]))
        with self.assertRaisesRegex(ValueError, "duplicate interface mapping"):
            _target_link(duplicate_net, 3, duplicate_peers, duplicate_rows)

        duplicate_port_net, duplicate_port_peers, duplicate_port_rows = runtime_target_fixture()
        duplicate_port_rows.append({
            **duplicate_port_rows[0],
            "interface_name": "s3-eth-extra",
            "peer_node": "s5",
            "peer_interface": "s5-eth1",
        })
        with self.assertRaisesRegex(ValueError, "duplicate OpenFlow port mapping"):
            _target_link(duplicate_port_net, 3, duplicate_port_peers, duplicate_port_rows)

        missing_net, missing_peers, missing_rows = runtime_target_fixture()
        missing_rows.pop(0)
        with self.assertRaisesRegex(ValueError, "no runtime OVS mapping"):
            _target_link(missing_net, 3, missing_peers, missing_rows)

        nonreciprocal_net, nonreciprocal_peers, nonreciprocal_rows = runtime_target_fixture(
            lambda values: values[1].update(peer_interface="s3-eth1")
        )
        with self.assertRaisesRegex(ValueError, "Target mapping validation failed"):
            _target_link(nonreciprocal_net, 3, nonreciprocal_peers, nonreciprocal_rows)

    def test_runtime_mapping_uses_observed_ports_not_fixed_port_numbers(self):
        def intf(node_name, intf_name):
            return SimpleNamespace(node=SimpleNamespace(name=node_name), name=intf_name)

        endpoints = (
            (intf("h1", "h1-eth0"), intf("s1", "s1-eth1")),
            (intf("s1", "s1-eth2"), intf("s2", "s2-eth1")),
            (intf("s2", "s2-eth2"), intf("s3", "s3-eth1")),
            (intf("s3", "s3-eth2"), intf("s4", "s4-eth1")),
            (intf("s4", "s4-eth2"), intf("h2", "h2-eth0")),
        )
        net = SimpleNamespace(
            links=[SimpleNamespace(intf1=left, intf2=right) for left, right in endpoints]
        )
        dynamic_ports = {
            "s1": ("7", "8"), "s2": ("17", "18"),
            "s3": ("29", "30"), "s4": ("41", "42"),
        }

        def ovs_show(command, **_kwargs):
            switch = command[-1]
            names = sorted(
                intf.name for link in net.links for intf in (link.intf1, link.intf2)
                if intf.node.name == switch
            )
            output = "\n".join(
                f"  {port}({name}): addr:00:00:00:00:00:01"
                for port, name in zip(dynamic_ports[switch], names)
            )
            return SimpleNamespace(stdout=output)

        with tempfile.TemporaryDirectory() as directory:
            mapping_path = Path(directory) / "runtime_port_mapping.csv"
            with mock.patch.object(runner.subprocess, "run", side_effect=ovs_show):
                peers, interface_to_port, rows = runner._runtime_mapping(net, mapping_path)
            self.assertEqual(interface_to_port[("s3", "s3-eth2")], "30")
            self.assertEqual(interface_to_port[("s4", "s4-eth1")], "41")
            self.assertEqual(len(rows), 8)
            with mapping_path.open(newline="", encoding="utf-8") as stream:
                written = list(csv.DictReader(stream))
            self.assertEqual(len(written), 8)
            target, _interfaces, validated = _target_link(net, 3, peers, rows)
            self.assertEqual(target, "s3-s4")
            self.assertEqual([row["openflow_port"] for row in validated], ["30", "41"])

    def test_successful_mocked_orchestration_records_complete_and_all_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, calls = self.run_mocked_orchestration(directory)
            self.assertIsNone(error)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "COMPLETE")
            self.assertEqual(metadata["physical_run_id"], 23)
            self.assertEqual(metadata["logical_experiment_id"], 3)
            self.assertEqual(metadata["fault_link"], "s3-s4")
            self.assertTrue(metadata["iperf"]["completion_valid"])
            self.assertEqual(
                metadata["traffic_profile"]["profile_id"],
                "udp_6mbps_s2s3_10mbps_v1",
            )
            self.assertEqual(
                metadata["iperf"]["summary_validation"]["requested_bandwidth_mbps"],
                6.0,
            )
            self.assertEqual(metadata["iperf"]["summary_validation"]["client_observed_duration_seconds"], 3.0)
            self.assertEqual(metadata["iperf"]["processes"]["client"]["returncode"], 0)
            self.assertEqual(metadata["iperf"]["processes"]["server"]["returncode"], 0)
            self.assertEqual(
                [row["openflow_port"] for row in metadata["fault_target_runtime_mapping"]],
                ["9", "17"],
            )
            for name in (
                "telemetry.csv", "phase_events.csv", "runtime_port_mapping.csv",
                "run_metadata.json", "iperf_server.log", "iperf_client.log",
            ):
                self.assertTrue((out / name).is_file(), name)
            self.assertEqual(len(calls), 1)
            self.assertEqual(fault.call_count, 2)
            client_command = next(
                process.command for process in _net.iperf_processes
                if process.role == "client"
            )
            self.assertEqual(client_command[client_command.index("-b") + 1], "6M")

    def test_iperf_process_and_final_summary_validation(self):
        good_client = iperf_client_output(60)
        good_server = iperf_server_output(60)
        result = runner.validate_iperf_completion(
            client_returncode=0, server_returncode=0, client_log=good_client,
            server_log=good_server, requested_duration=60,
            client_elapsed=60.2, server_elapsed=62.1,
        )
        self.assertTrue(result["duration_valid"])
        self.assertTrue(result["receiver_delivery_valid"])
        self.assertTrue(result["receiver_reports_match"])
        self.assertEqual(result["receiver_delivered_datagrams"], 100)
        self.assertEqual(result["client_sender_reported_mbps"], 1.05)
        self.assertEqual(result["client_receiver_reported_mbps"], 1.05)
        self.assertEqual(result["server_receiver_reported_mbps"], 1.05)
        for kwargs, error in (
            ({"client_returncode": 4, "server_returncode": 0,
              "client_log": good_client, "server_log": good_server}, "client exited with status 4"),
            ({"client_returncode": 0, "server_returncode": 7,
              "client_log": good_client, "server_log": good_server}, "server exited with status 7"),
            ({"client_returncode": 0, "server_returncode": 0,
              "client_log": "connected only", "server_log": good_server}, "Missing client log receiver"),
            ({"client_returncode": 0, "server_returncode": 0,
              "client_log": iperf_client_output(20), "server_log": iperf_server_output(20)},
             "outside requested"),
            ({"client_returncode": 0, "server_returncode": 0,
              "client_log": good_client, "server_log": iperf_server_output(60, total=99)},
             "receiver summaries disagree"),
        ):
            args = {
                "requested_duration": 60, "client_elapsed": 60, "server_elapsed": 62,
                **kwargs,
            }
            with self.assertRaisesRegex(ValueError, error):
                runner.validate_iperf_completion(**args)

    def test_iperf_parser_accepts_padded_intervals_and_requires_receiver_delivery(self):
        client_log = iperf_client_output(4, sent=357, lost=0, total=357)
        server_log = iperf_server_output(4, lost=0, total=357)
        result = runner.validate_iperf_completion(
            client_returncode=0, server_returncode=0,
            client_log=client_log, server_log=server_log,
            requested_duration=4, client_elapsed=4.09, server_elapsed=12.57,
        )
        self.assertEqual(result["receiver_delivered_datagrams"], 357)
        self.assertTrue(result["receiver_delivery_valid"])
        with self.assertRaisesRegex(ValueError, "no sequence-accounted non-lost datagrams"):
            runner.validate_iperf_completion(
                client_returncode=0, server_returncode=0,
                client_log=iperf_client_output(4, sent=357, lost=357, total=357),
                server_log=iperf_server_output(4, lost=357, total=357),
                requested_duration=4, client_elapsed=4, server_elapsed=12,
            )

    def test_iperf2_sequence_totals_may_differ_from_sender_count(self):
        # iperf2's legacy Lost/Total fields are sequence-derived, not a raw
        # socket receive count; its maintainer documents a counter difference.
        result = runner.validate_iperf_completion(
            client_returncode=0, server_returncode=0,
            client_log=iperf_client_output(60, sent=133747, lost=103188, total=133748),
            server_log=iperf_server_output(60, lost=103188, total=133748),
            requested_duration=60, client_elapsed=61.4, server_elapsed=78.1,
        )
        self.assertEqual(result["client_receiver_accounted_minus_sender_count"], 1)
        self.assertEqual(result["sequence_accounted_nonlost_datagrams"], 30560)
        self.assertIn("sequence-number-derived", result["receiver_statistics_basis"])
        self.assertTrue(result["receiver_reports_match"])

    def test_iperf_client_timeout_is_invalid_and_logs_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, _calls = self.run_mocked_orchestration(
                directory, iperf_mode="client_timeout"
            )
            self.assertIsInstance(error, runner.subprocess.TimeoutExpired)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertFalse(metadata["iperf"]["completion_valid"])
            self.assertTrue((out / "iperf_client.log").is_file())
            self.assertTrue((out / "iperf_server.log").is_file())
            self.assertEqual(fault.call_count, 2)

    def test_iperf_nonzero_client_or_server_exit_is_invalid(self):
        for mode, message in (("client_nonzero", "client exited with status 5"),
                              ("server_nonzero", "server exited with status 5")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                out, error, _fault, _net, _calls = self.run_mocked_orchestration(
                    directory, iperf_mode=mode
                )
                self.assertIsInstance(error, RuntimeError)
                metadata = json.loads((out / "run_metadata.json").read_text())
                self.assertEqual(metadata["status"], "FAILED_INVALID")
                self.assertIn(message, metadata["failure"])

    def test_iperf_missing_summary_and_premature_server_are_invalid(self):
        for mode, message in (("missing_summary", "Missing client log receiver"),
                              ("premature_server", "terminated before client startup")):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                out, error, fault, _net, _calls = self.run_mocked_orchestration(
                    directory, iperf_mode=mode
                )
                self.assertIsNotNone(error)
                metadata = json.loads((out / "run_metadata.json").read_text())
                self.assertEqual(metadata["status"], "FAILED_INVALID")
                self.assertIn(message, metadata["failure"])
                self.assertTrue((out / "iperf_server.log").exists())
                if mode == "premature_server":
                    fault.assert_not_called()

    def test_iperf_cleanup_failure_cannot_mark_run_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, _fault, _net, _calls = self.run_mocked_orchestration(
                directory, iperf_mode="cleanup_failure"
            )
            self.assertIsInstance(error, runner.subprocess.TimeoutExpired)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertTrue(any("terminate failure" in item
                                for item in metadata.get("cleanup_failures", [])))

    def test_orchestration_timeout_preserves_failed_metadata_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, _fault, _net, calls = self.run_mocked_orchestration(
                directory, collector_mode="empty"
            )
            self.assertIsInstance(error, TimeoutError)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("Timed out", metadata["failure"])
            self.assertTrue((out / "telemetry.csv").is_file())
            self.assertTrue((out / "phase_events.csv").is_file())
            self.assertEqual(len(calls), 1)

    def test_orchestration_early_collector_exit_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, _calls = self.run_mocked_orchestration(
                directory, collector_mode="early_exit"
            )
            self.assertIsInstance(error, RuntimeError)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("exited before a valid first sample", metadata["failure"])
            self.assertTrue((out / "telemetry.csv").is_file())
            self.assertTrue((out / "phase_events.csv").is_file())
            fault.assert_not_called()

    def test_orchestration_malformed_telemetry_fails_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, _fault, _net, _calls = self.run_mocked_orchestration(
                directory, collector_mode="malformed"
            )
            self.assertIsInstance(error, TimeoutError)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("Malformed timestamp", metadata["failure"])
            self.assertTrue((out / "telemetry.csv").is_file())

    def test_orchestration_wrong_physical_id_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, _calls = self.run_mocked_orchestration(
                directory, collector_mode="wrong_id"
            )
            self.assertIsInstance(error, TimeoutError)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("physical run ID 999", metadata["failure"])
            fault.assert_not_called()

    def test_orchestration_phase_coverage_failure_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, _calls = self.run_mocked_orchestration(
                directory, sample_end=3
            )
            self.assertIsInstance(error, ValueError)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("Recovery event is after", metadata["validation_failure"])
            self.assertTrue((out / "runtime_port_mapping.csv").is_file())
            self.assertTrue((out / "phase_events.csv").is_file())
            self.assertEqual(
                [row["openflow_port"] for row in metadata["fault_target_runtime_mapping"]],
                ["9", "17"],
            )
            self.assertEqual(fault.call_count, 2)

    def test_target_mapping_mismatch_aborts_before_collector_or_fault(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, calls = self.run_mocked_orchestration(
                directory,
                mapping_change=lambda rows: rows[0].update(peer_node="s2"),
            )
            self.assertIsInstance(error, ValueError)
            self.assertIn("Target mapping validation failed", str(error))
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("Target mapping validation failed", metadata["failure"])
            self.assertTrue((out / "runtime_port_mapping.csv").is_file())
            self.assertEqual(calls, [])
            fault.assert_not_called()

    def test_cleanup_failure_cannot_leave_metadata_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, _calls = self.run_mocked_orchestration(
                directory, stop_failure=True
            )
            self.assertIsInstance(error, RuntimeError)
            metadata = json.loads((out / "run_metadata.json").read_text())
            self.assertEqual(metadata["status"], "FAILED_INVALID")
            self.assertIn("mock stop failure", metadata["cleanup_failure"])
            self.assertTrue((out / "telemetry.csv").is_file())
            self.assertEqual(fault.call_count, 2)

    def test_orchestration_refuses_occupied_directory_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            occupied = Path(directory) / "recollection_runs" / "physical_23_logical_3"
            occupied.mkdir(parents=True)
            marker = occupied / "preserve.txt"
            marker.write_text("original evidence", encoding="utf-8")
            out, error, fault, _net, calls = self.run_mocked_orchestration(directory)
            self.assertEqual(out, occupied)
            self.assertIsInstance(error, FileExistsError)
            self.assertEqual(marker.read_text(encoding="utf-8"), "original evidence")
            self.assertEqual(fault.call_count, 0)
            self.assertEqual(calls, [])

    def test_orchestration_rejects_existing_physical_id_before_network_start(self):
        with tempfile.TemporaryDirectory() as directory:
            out, error, fault, _net, calls = self.run_mocked_orchestration(
                directory, physical_id=20
            )
            self.assertIsInstance(error, ValueError)
            self.assertIn("reserved logical/physical ID pairs", str(error))
            self.assertFalse(out.exists())
            self.assertEqual(fault.call_count, 0)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
