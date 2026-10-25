"""Safely run reserved SDN fault experiments under unique physical IDs.

Default invocation is a read-only preflight. A live run requires --run and must
be launched as root inside the Ubuntu Mininet VM after explicit approval.
All run artifacts are isolated below recollection_runs/ and never enter the
historical experiments/ directory automatically.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from linear_topology import LinearTopology, SUPPORTED_SWITCH_COUNTS, registry_entry
from telemetry import parse_port_interfaces
from telemetry_pipeline import TELEMETRY_FIELDS


PROJECT = Path(__file__).resolve().parent
RUN_ROOT = PROJECT / "recollection_runs"
LOGICAL_TO_PHYSICAL = {
    3: 23, 10: 21,
    20: 24, 21: 25, 22: 26, 23: 27, 24: 28, 25: 29,
    26: 30,
    27: 31,
    40: 44,
    41: 45,
}
FAULT_LINK_BY_LOGICAL = {
    3: "s3-s4", 10: "s2-s3",
    20: "s1-s2", 21: "s1-s2",
    22: "s2-s3", 23: "s2-s3",
    24: "s3-s4", 25: "s3-s4",
    26: "s2-s3",
    27: "s2-s3",
    40: "s2-s3",
    41: "s2-s3",
}
RUN_PURPOSE_BY_LOGICAL = {
    26: "traffic_profile_pilot_only",
    27: "traffic_profile_pilot_retry_only",
    40: "isolated_live_demo_only",
    41: "isolated_live_demo_only",
}
FAULT_TYPE = "link_failure"
PHASES = ("normal", "fault", "recovery")
FIRST_SAMPLE_TIMEOUT_SECONDS = 15.0
FIRST_SAMPLE_POLL_SECONDS = 0.05
IPERF_SERVER_GRACE_SECONDS = 15.0
IPERF_SERVER_WAIT_TIMEOUT_SECONDS = IPERF_SERVER_GRACE_SECONDS + 5.0
IPERF_CLIENT_WAIT_GRACE_SECONDS = 15.0
IPERF_PROCESS_CLEANUP_TIMEOUT_SECONDS = 5.0
IPERF_DURATION_TOLERANCE_SECONDS = 2.0
SENDER_RATE_TOLERANCE = 0.10
# The four-switch study topology stays the default; larger linear topologies
# are selected explicitly with --switches and use their own ID registry.
DEFAULT_TOPOLOGY = LinearTopology(4)
SWITCHES = DEFAULT_TOPOLOGY.switches
SAMPLE_NUMERIC_FIELDS = (
    "rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes",
    "tx_dropped", "rx_packet_rate", "tx_packet_rate",
    "rx_throughput_mbps", "tx_throughput_mbps",
)
LINK_DEFINITIONS = DEFAULT_TOPOLOGY.link_definitions
TRAFFIC_PROFILE_PATH = PROJECT / "traffic_profiles" / "udp_6mbps_v1.json"
TRAFFIC_PROFILE_BY_SWITCH_COUNT = {
    4: "udp_6mbps_v1.json",
    8: "udp_6mbps_8sw_v1.json",
    12: "udp_6mbps_12sw_v1.json",
}


def topology_for(switch_count=None):
    if switch_count is None:
        return DEFAULT_TOPOLOGY
    count = int(switch_count)
    if count not in SUPPORTED_SWITCH_COUNTS:
        raise ValueError("Unsupported switch count %d; supported: %s" % (count, SUPPORTED_SWITCH_COUNTS))
    return LinearTopology(count)


def traffic_profile_path(topology=None):
    topology = DEFAULT_TOPOLOGY if topology is None else topology
    name = TRAFFIC_PROFILE_BY_SWITCH_COUNT.get(topology.switch_count)
    if name is None:
        raise ValueError("No frozen traffic profile for a %d-switch topology" % topology.switch_count)
    # Anchor on the import-time constant so test patches of PROJECT behave as before.
    return TRAFFIC_PROFILE_PATH.parent / name
MAX_OFFERED_CAPACITY_FRACTION = 0.7


def load_traffic_profile(path=None, topology=None):
    topology = DEFAULT_TOPOLOGY if topology is None else topology
    path = Path(path) if path is not None else traffic_profile_path(topology)
    profile = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "profile_id", "protocol", "offered_rate_mbps", "bottleneck_link",
        "bottleneck_capacity_mbps", "maximum_capacity_fraction",
        "payload_size_policy", "phase_durations_seconds",
    }
    missing = required - set(profile)
    if missing:
        raise ValueError(f"Traffic profile is missing fields: {sorted(missing)}")
    if profile["protocol"] != "udp":
        raise ValueError("The recollection runner currently requires a UDP traffic profile")
    if profile["bottleneck_link"] != topology.bottleneck_link:
        raise ValueError(
            "Traffic profile bottleneck %r is not the topology bottleneck %r"
            % (profile["bottleneck_link"], topology.bottleneck_link)
        )
    bottlenecks = [
        float(params["bw"])
        for left, right, params in topology.link_definitions
        if params and "-".join((left, right)) == profile["bottleneck_link"]
    ]
    if len(bottlenecks) != 1:
        raise ValueError(
            f"Traffic profile bottleneck is not unique in the topology: "
            f"{profile['bottleneck_link']}"
        )
    configured_capacity = bottlenecks[0]
    try:
        offered_rate = float(profile["offered_rate_mbps"])
        declared_capacity = float(profile["bottleneck_capacity_mbps"])
        declared_fraction = float(profile["maximum_capacity_fraction"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Traffic profile rates and capacity must be numeric") from exc
    if not all(math.isfinite(value) for value in (
        offered_rate, declared_capacity, declared_fraction,
    )):
        raise ValueError("Traffic profile rates and capacity must be finite")
    if not math.isclose(declared_capacity, configured_capacity):
        raise ValueError(
            "Traffic profile bottleneck capacity does not match LINK_DEFINITIONS"
        )
    if not math.isclose(declared_fraction, MAX_OFFERED_CAPACITY_FRACTION):
        raise ValueError("Traffic profile safety fraction does not match runner policy")
    if offered_rate <= 0 or offered_rate > configured_capacity * MAX_OFFERED_CAPACITY_FRACTION:
        raise ValueError(
            f"Offered load {offered_rate:g} Mbps must be positive and at most "
            f"{MAX_OFFERED_CAPACITY_FRACTION:.0%} of the {configured_capacity:g} Mbps "
            "configured bottleneck"
        )
    if not isinstance(profile["phase_durations_seconds"], dict):
        raise ValueError("Traffic profile phase durations must be an object")
    if set(profile["phase_durations_seconds"]) != set(PHASES):
        raise ValueError("Traffic profile must define all three phase durations")
    try:
        phase_durations = {
            name: int(profile["phase_durations_seconds"][name])
            for name in PHASES
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("Traffic profile phase durations must be integers") from exc
    if any(value < 1 for value in phase_durations.values()):
        raise ValueError("Traffic profile phase durations must be positive")
    return {
        **profile,
        "offered_rate_mbps": offered_rate,
        "bottleneck_capacity_mbps": configured_capacity,
        "maximum_capacity_fraction": MAX_OFFERED_CAPACITY_FRACTION,
        "phase_durations_seconds": phase_durations,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def iperf_bandwidth_argument(rate_mbps):
    rate = float(rate_mbps)
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("iperf bandwidth must be a positive finite rate")
    return f"{format(rate, '.3f').rstrip('0').rstrip('.')}M"


def get_iperf_version():
    completed = subprocess.run(
        ["iperf", "--version"],
        capture_output=True,
        text=True,
    )
    version_output = "\n".join((completed.stdout, completed.stderr)).strip()
    if completed.returncode not in (0, 1):
        raise RuntimeError(
            f"iperf version query exited with status {completed.returncode}: "
            f"{version_output!r}"
        )
    match = re.search(
        r"\biperf(?:\s+version)?\s+(2\.\d+(?:\.\d+)?)\b",
        version_output,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError(
            "Expected iperf2 for the UDP summary parser; "
            f"version output was {version_output!r}"
        )
    return match.group(1)


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="microseconds")


def resolve_registry(logical_id, physical_id, switch_count=None):
    """Return the registered fault link and purpose for an ID pair and topology."""
    topology = topology_for(switch_count)
    if topology.switch_count == 4:
        if LOGICAL_TO_PHYSICAL.get(int(logical_id)) != int(physical_id):
            raise ValueError("Only the reserved logical/physical ID pairs are allowed")
        return {
            "fault_link": FAULT_LINK_BY_LOGICAL[int(logical_id)],
            "run_purpose": RUN_PURPOSE_BY_LOGICAL.get(int(logical_id), "candidate_recollection"),
        }
    entry = registry_entry(topology.switch_count, logical_id, physical_id)
    return {"fault_link": entry["fault_link"], "run_purpose": entry["run_purpose"]}


def run_directory(logical_id, physical_id, switch_count=None):
    topology = topology_for(switch_count)
    resolve_registry(logical_id, physical_id, topology.switch_count)
    name = f"physical_{int(physical_id)}_logical_{int(logical_id)}"
    if topology.switch_count == 4:
        return RUN_ROOT / name
    return RUN_ROOT / f"topology_{topology.switch_count}_switches" / name


def assert_run_paths_available(output_dir, project, physical_id):
    """Refuse an occupied isolated directory or historical physical-ID path."""
    output_dir = Path(output_dir)
    project = Path(project)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to reuse run directory: {output_dir}")
    for name in (f"telemetry_{physical_id}.csv", f"phases_{physical_id}.csv"):
        path = project / "experiments" / name
        if path.exists():
            raise FileExistsError(f"Physical run ID already exists: {path}")


def parse_required_timestamp(value, field_name):
    if value is None or not str(value).strip():
        raise ValueError(f"Missing required timestamp: {field_name}")
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed timestamp for {field_name}: {value!r}") from exc
    # Telemetry timestamps are local naive ISO strings; phase timestamps carry
    # the VM's local UTC offset. Normalize both to UTC for comparison.
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


def validate_sample_row(row, expected_physical_id):
    required = ("timestamp", "switch", "port", "interface_name", "experiment_id")
    missing = [name for name in required if not str(row.get(name, "")).strip()]
    if missing:
        raise ValueError(f"Telemetry sample missing required fields: {missing}")
    sample_time = parse_required_timestamp(row["timestamp"], "telemetry sample")
    try:
        observed_id = int(row["experiment_id"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Malformed telemetry physical run ID") from exc
    if observed_id != int(expected_physical_id):
        raise ValueError(
            f"Telemetry physical run ID {observed_id} does not match "
            f"expected {expected_physical_id}"
        )
    for field in SAMPLE_NUMERIC_FIELDS:
        try:
            value = float(row[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Missing or malformed telemetry value: {field}") from exc
        if not math.isfinite(value):
            raise ValueError(f"Non-finite telemetry value: {field}")
    return sample_time


def wait_for_first_valid_sample(
    telemetry_path,
    collector,
    expected_physical_id,
    *,
    timeout=FIRST_SAMPLE_TIMEOUT_SECONDS,
    poll_interval=FIRST_SAMPLE_POLL_SECONDS,
    monotonic=time.monotonic,
    sleep=time.sleep,
):
    """Wait boundedly for a complete, parseable first sample from the collector."""
    deadline = monotonic() + float(timeout)
    telemetry_path = Path(telemetry_path)
    last_invalid_sample = None
    while monotonic() < deadline:
        if collector.poll() is not None:
            reason = (
                f"; last rejected row: {last_invalid_sample}"
                if last_invalid_sample else ""
            )
            raise RuntimeError(
                "Telemetry collector exited before a valid first sample "
                f"(exit {collector.returncode}){reason}"
            )
        if telemetry_path.is_file():
            try:
                with telemetry_path.open(newline="", encoding="utf-8") as stream:
                    reader = csv.DictReader(stream)
                    if reader.fieldnames is not None and tuple(reader.fieldnames) != TELEMETRY_FIELDS:
                        raise ValueError("Telemetry header does not match the required schema")
                    rows = list(reader)
                for row in rows:
                    try:
                        return validate_sample_row(row, expected_physical_id)
                    except ValueError as exc:
                        last_invalid_sample = str(exc)
            except (csv.Error, UnicodeError) as exc:
                raise ValueError(f"Could not parse first telemetry sample: {exc}") from exc
        sleep(min(float(poll_interval), max(0.0, deadline - monotonic())))
    reason = (
        f"; last rejected row: {last_invalid_sample}"
        if last_invalid_sample else ""
    )
    raise TimeoutError(
        f"Timed out after {timeout:g}s waiting for a valid first telemetry sample{reason}"
    )


def record_normal_phase_after_sample(
    telemetry_path,
    collector,
    expected_physical_id,
    writer,
    stream,
    logical_id,
    physical_id,
    fault_link,
    *,
    timeout=FIRST_SAMPLE_TIMEOUT_SECONDS,
    timestamp_func=now_iso,
):
    first_sample = wait_for_first_valid_sample(
        telemetry_path,
        collector,
        expected_physical_id,
        timeout=timeout,
    )
    event_timestamp = timestamp_func()
    event_time = parse_required_timestamp(event_timestamp, "normal phase event")
    if event_time < first_sample:
        raise ValueError("Normal event precedes the first valid telemetry sample")
    writer.writerow({
        "physical_run_id": physical_id,
        "logical_experiment_id": logical_id,
        "timestamp": event_timestamp,
        "phase": "normal",
        "fault_type": "none",
        "fault_location": "none",
    })
    stream.flush()
    return first_sample.isoformat(), event_timestamp


def validate_event_coverage(first_sample_timestamp, last_sample_timestamp, phase_events):
    if not isinstance(phase_events, dict):
        raise ValueError("Missing phase event timestamps")
    missing = [phase for phase in PHASES if not phase_events.get(phase)]
    if missing:
        raise ValueError(f"Missing required phase event timestamp(s): {missing}")
    first = parse_required_timestamp(first_sample_timestamp, "first telemetry sample")
    last = parse_required_timestamp(last_sample_timestamp, "last telemetry sample")
    events = {
        phase: parse_required_timestamp(phase_events[phase], f"{phase} phase event")
        for phase in PHASES
    }
    if first > last:
        raise ValueError("First telemetry sample is after the last telemetry sample")
    if first > events["normal"]:
        raise ValueError("Normal event precedes the first telemetry sample")
    if not events["normal"] < events["fault"]:
        raise ValueError("Fault event must be after the normal event")
    if not events["fault"] < events["recovery"]:
        raise ValueError("Recovery event must be after the fault event")
    if events["fault"] > last:
        raise ValueError("Fault event is after the last telemetry sample")
    if events["recovery"] > last:
        raise ValueError("Recovery event is after the last telemetry sample")
    return first, last, events


def finalize_run_metadata(metadata, rows, phase_events, expected_physical_id):
    """Set COMPLETE only after row and event timestamp validation succeeds."""
    try:
        if not rows:
            raise ValueError("Telemetry contains no valid sample rows")
        timestamps = [validate_sample_row(row, expected_physical_id) for row in rows]
        first, last, _events = validate_event_coverage(
            min(timestamps).isoformat(), max(timestamps).isoformat(), phase_events
        )
    except ValueError as exc:
        metadata["status"] = "FAILED_INVALID"
        metadata["validation_failure"] = str(exc)
        raise
    metadata["telemetry_start"] = first.isoformat()
    metadata["telemetry_end"] = last.isoformat()
    metadata["telemetry_rows"] = len(rows)
    metadata["status"] = "COMPLETE"
    return metadata


def preflight(logical_id, physical_id, switch_count=None):
    """Read-only checks; does not create files, start Mininet, or inject faults."""
    logical_id, physical_id = int(logical_id), int(physical_id)
    topology = topology_for(switch_count)
    registered = resolve_registry(logical_id, physical_id, topology.switch_count)
    output_dir = run_directory(logical_id, physical_id, topology.switch_count)
    assert_run_paths_available(output_dir, PROJECT, physical_id)
    traffic_profile = load_traffic_profile(topology=topology)
    iperf_version = get_iperf_version()
    if not (PROJECT / "telemetry.py").is_file():
        raise FileNotFoundError("telemetry.py is missing")
    if not (PROJECT / "telemetry_pipeline.py").is_file():
        raise FileNotFoundError("telemetry_pipeline.py is missing")
    ovs = subprocess.run(
        ["ovs-vsctl", "list-br"],
        check=True,
        capture_output=True,
        text=True,
    )
    existing_bridges = set(ovs.stdout.split())
    conflicts = sorted(existing_bridges.intersection(topology.switches))
    if conflicts:
        raise RuntimeError(f"Existing OVS bridges conflict with this topology: {conflicts}")
    controller = socket.socket()
    controller.settimeout(1.0)
    try:
        controller.connect(("127.0.0.1", 6633))
    finally:
        controller.close()
    return {
        "logical_experiment_id": logical_id,
        "physical_run_id": physical_id,
        "fault_link": registered["fault_link"],
        "run_purpose": registered["run_purpose"],
        "switch_count": topology.switch_count,
        "candidate_links": list(topology.candidate_links),
        "topology_spec": topology.to_metadata(),
        "output_dir": str(output_dir),
        "controller": "127.0.0.1:6633 reachable",
        "existing_ovs_bridges": sorted(existing_bridges),
        "historical_experiment_files": "not used; output is isolated",
        "traffic_profile": traffic_profile,
        "iperf_version": iperf_version,
    }


def _create_network(topology=None):
    topology = DEFAULT_TOPOLOGY if topology is None else topology
    from mininet.link import TCLink
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController

    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
    )
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6633)
    net.addHost("h1")
    net.addHost("h2")
    for switch in topology.switches:
        net.addSwitch(switch, protocols="OpenFlow13")
    for left, right, params in topology.link_definitions:
        net.addLink(left, right, **(params or {}))
    return net


_SWITCH_NAME_RE = re.compile(r"^s(\d+)$")


def canonical_link_name(node_a, node_b):
    """Name a link; switch pairs order numerically so s9-s10 is not 's10-s9'.

    Host links keep the historical lexicographic order (h1-s1, h2-s4) so the
    four-switch mapping output is unchanged.
    """
    left, right = _SWITCH_NAME_RE.match(str(node_a)), _SWITCH_NAME_RE.match(str(node_b))
    if left and right:
        ordered = sorted((str(node_a), str(node_b)), key=lambda name: int(name[1:]))
        return "-".join(ordered)
    return "-".join(sorted((str(node_a), str(node_b))))


def _runtime_mapping(net, output_path, switches=None):
    switches = tuple(SWITCHES if switches is None else switches)
    peers = {}
    for link in net.links:
        left, right = link.intf1, link.intf2
        peers[(left.node.name, left.name)] = (right.node.name, right.name)
        peers[(right.node.name, right.name)] = (left.node.name, left.name)

    mapping_rows = []
    interface_to_port = {}
    for switch in switches:
        completed = subprocess.run(
            ["ovs-ofctl", "-O", "OpenFlow13", "show", switch],
            check=True,
            capture_output=True,
            text=True,
        )
        for port, interface in parse_port_interfaces(completed.stdout).items():
            if port == "LOCAL":
                continue
            peer = peers.get((switch, interface))
            if peer is None:
                raise RuntimeError(f"OVS interface is absent from Mininet links: {switch}:{interface}")
            if (switch, interface) in interface_to_port:
                raise RuntimeError(
                    f"OVS runtime mapping assigns multiple ports to {switch}:{interface}"
                )
            interface_to_port[(switch, interface)] = port
            mapping_rows.append({
                "switch": switch,
                "openflow_port": port,
                "interface_name": interface,
                "peer_node": peer[0],
                "peer_interface": peer[1],
                "link": canonical_link_name(switch, peer[0]),
            })
    expected_interfaces = {
        (node, interface)
        for (node, interface), _peer in peers.items()
        if node in switches
    }
    observed_interfaces = {
        (row["switch"], row["interface_name"]) for row in mapping_rows
    }
    if expected_interfaces != observed_interfaces:
        missing = sorted(expected_interfaces - observed_interfaces)
        unexpected = sorted(observed_interfaces - expected_interfaces)
        raise RuntimeError(
            "Runtime OVS mapping does not cover the Mininet switch interfaces; "
            f"missing={missing}, unexpected={unexpected}"
        )
    with output_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "switch", "openflow_port", "interface_name", "peer_node", "peer_interface", "link"
        ))
        writer.writeheader()
        writer.writerows(mapping_rows)
    return peers, interface_to_port, mapping_rows


def _target_link(net, logical_id, peers, mapping_rows, target=None):
    """Resolve the configured fault to one Mininet link and validate its OVS mapping."""
    if target is None:
        target = FAULT_LINK_BY_LOGICAL[int(logical_id)]
    expected_nodes = set(target.split("-"))
    matches = []
    for link in net.links:
        if {link.intf1.node.name, link.intf2.node.name} == expected_nodes:
            matches.append((link.intf1, link.intf2))
    if len(matches) != 1:
        raise ValueError(f"Target mapping validation failed: cannot uniquely resolve Mininet link {target}")

    # Reject ambiguous or contradictory entries before matching the target. Port
    # numbers are taken from ovs-ofctl output and are never inferred from topology order.
    required_fields = {
        "switch", "openflow_port", "interface_name", "peer_node", "peer_interface", "link"
    }
    by_interface = {}
    by_port = {}
    for index, row in enumerate(mapping_rows):
        missing = required_fields.difference(row)
        if missing:
            raise ValueError(f"Target mapping validation failed: mapping row {index} missing {sorted(missing)}")
        switch = str(row["switch"])
        port = str(row["openflow_port"])
        interface = str(row["interface_name"])
        try:
            if int(port) <= 0:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Target mapping validation failed: invalid OpenFlow port {port!r} on {switch}"
            ) from exc
        interface_key = (switch, interface)
        port_key = (switch, port)
        if interface_key in by_interface:
            raise ValueError(f"Target mapping validation failed: duplicate interface mapping {switch}:{interface}")
        if port_key in by_port:
            raise ValueError(f"Target mapping validation failed: duplicate OpenFlow port mapping {switch}:{port}")
        by_interface[interface_key] = row
        by_port[port_key] = row

    left_intf, right_intf = matches[0]
    target_interfaces = []
    for intf, peer_intf in ((left_intf, right_intf), (right_intf, left_intf)):
        switch = intf.node.name
        peer_node = peer_intf.node.name
        key = (switch, intf.name)
        row = by_interface.get(key)
        if row is None:
            raise ValueError(
                f"Target mapping validation failed: no runtime OVS mapping for {switch}:{intf.name}"
            )
        expected_peer = (peer_node, peer_intf.name)
        actual_peer = (str(row["peer_node"]), str(row["peer_interface"]))
        if actual_peer != expected_peer:
            raise ValueError(
                f"Target mapping validation failed: {switch}:{intf.name} maps to "
                f"{actual_peer[0]}:{actual_peer[1]}, expected {peer_node}:{peer_intf.name}"
            )
        if str(row["link"]) != target:
            raise ValueError(
                f"Target mapping validation failed: {switch}:{intf.name} records link "
                f"{row['link']!r}, expected {target!r}"
            )
        if peers.get(key) != expected_peer:
            raise ValueError(
                f"Target mapping validation failed: Mininet peer mismatch for {switch}:{intf.name}"
            )
        target_interfaces.append(dict(row))

    # Require a unique reciprocal row for each side of the switch-to-switch link.
    for row, peer_row in ((target_interfaces[0], target_interfaces[1]),
                          (target_interfaces[1], target_interfaces[0])):
        reciprocal = by_interface.get((str(row["peer_node"]), str(row["peer_interface"])))
        if reciprocal is None:
            raise ValueError(
                f"Target mapping validation failed: missing reciprocal mapping for "
                f"{row['switch']}:{row['interface_name']}"
            )
        if (str(reciprocal["peer_node"]), str(reciprocal["peer_interface"])) != (
            str(row["switch"]), str(row["interface_name"])
        ):
            raise ValueError(
                f"Target mapping validation failed: contradictory reciprocal mapping for "
                f"{row['switch']}:{row['interface_name']}"
            )
        if reciprocal != peer_row:
            raise ValueError(
                f"Target mapping validation failed: target endpoints do not match reciprocal "
                f"runtime mappings for {target}"
            )
    return target, matches[0], target_interfaces


def _set_link(intfs, up):
    state = "up" if up else "down"
    for intf in intfs:
        _stdout, stderr, code = intf.node.pexec(f"ip link set dev {intf.name} {state}")
        if code != 0:
            raise RuntimeError(f"Failed to set {intf.name} {state}: {stderr.strip()}")


def _write_metadata(path, metadata):
    with path.open("w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2, sort_keys=True)
        stream.write("\n")


_IPERF_SUMMARY_RE = re.compile(
    r"^\s*\[\s*\d+\]\s+(\d+(?:\.\d+)?)\s*-\s*"
    r"(\d+(?:\.\d+)?)\s+sec\s+.+?\b(?:K|M|G)?(?:bits|Bytes)/sec\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_IPERF_SENT_RE = re.compile(r"\bSent\s+(\d+)\s+datagrams\b", re.IGNORECASE)
_IPERF_LOSS_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\s*\(")
_IPERF_RATE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*([KMG]?)(bits|Bytes)/sec\b")


def _iperf_summary_matches(log_text):
    return list(_IPERF_SUMMARY_RE.finditer(log_text))


def parse_iperf_final_duration(log_text, role):
    """Return the final sender or receiver interval for a named iperf2 role."""
    if role == "client":
        if "Server Report:" not in log_text:
            raise ValueError("Missing client log receiver-side Server Report")
        summary_text = log_text.split("Server Report:", 1)[0]
    elif role == "client_receiver":
        if "Server Report:" not in log_text:
            raise ValueError("Missing client log receiver-side Server Report")
        summary_text = log_text.split("Server Report:", 1)[1]
    elif role == "server":
        summary_text = log_text
    else:
        raise ValueError(f"Unknown iperf summary role: {role}")
    matches = _iperf_summary_matches(summary_text)
    if not matches:
        raise ValueError(f"Missing final {role} iperf transfer summary")
    match = matches[-1]
    start, end = float(match.group(1)), float(match.group(2))
    duration = end - start
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Invalid final {role} iperf summary duration: {duration}")
    return duration


def _summary_rate_mbps(match, role):
    rates = _IPERF_RATE_RE.findall(match.group(0))
    if not rates:
        raise ValueError(f"Missing final {role} iperf transfer rate")
    value, prefix, unit = rates[-1]
    scale = {"": 1.0, "K": 0.001, "M": 1.0, "G": 1000.0}[prefix]
    if unit == "Bytes":
        scale *= 8.0
    rate_mbps = float(value) * scale
    if not math.isfinite(rate_mbps) or rate_mbps <= 0:
        raise ValueError(f"Invalid final {role} iperf transfer rate: {rate_mbps}")
    return rate_mbps


def validate_iperf_completion(
    *, client_returncode, server_returncode, client_log, server_log,
    requested_duration, client_elapsed, server_elapsed,
    requested_bandwidth_mbps=None,
    tolerance=IPERF_DURATION_TOLERANCE_SECONDS,
):
    """Validate process outcomes and iperf2 final reports before COMPLETE."""
    result = {
        "server_mode": "iperf2 bounded server timeout (-t), followed by natural exit",
        "requested_duration_seconds": float(requested_duration),
        "duration_tolerance_seconds": float(tolerance),
        "client_returncode": client_returncode,
        "server_returncode": server_returncode,
        "client_elapsed_seconds": float(client_elapsed),
        "server_elapsed_seconds": float(server_elapsed),
        "client_summary_valid": False,
        "server_summary_valid": False,
        "duration_valid": False,
    }
    if client_returncode is None:
        raise ValueError("iperf client has no documented terminal outcome")
    if server_returncode is None:
        raise ValueError("iperf server has no documented terminal outcome")
    if client_returncode != 0:
        raise ValueError(f"iperf client exited with status {client_returncode}")
    if server_returncode != 0:
        raise ValueError(f"iperf server exited with status {server_returncode}")
    if "Server Report:" not in client_log:
        raise ValueError("Missing client log receiver-side Server Report")
    sender_section, client_receiver_section = client_log.split("Server Report:", 1)
    sender_matches = _iperf_summary_matches(sender_section)
    receiver_matches = _iperf_summary_matches(client_receiver_section)
    server_matches = _iperf_summary_matches(server_log)
    if not sender_matches:
        raise ValueError("Missing final client sender transfer summary")
    if not receiver_matches:
        raise ValueError("Missing client receiver-side transfer summary")
    if not server_matches:
        raise ValueError("Missing final server receiver transfer summary")
    client_duration = float(sender_matches[-1].group(2)) - float(sender_matches[-1].group(1))
    result["client_summary_valid"] = True
    client_receiver_duration = (
        float(receiver_matches[-1].group(2)) - float(receiver_matches[-1].group(1))
    )
    server_duration = float(server_matches[-1].group(2)) - float(server_matches[-1].group(1))
    result["server_summary_valid"] = True
    result["client_observed_duration_seconds"] = client_duration
    result["client_receiver_observed_duration_seconds"] = client_receiver_duration
    result["server_observed_duration_seconds"] = server_duration
    result["client_sender_reported_mbps"] = _summary_rate_mbps(
        sender_matches[-1], "client sender"
    )
    result["client_receiver_reported_mbps"] = _summary_rate_mbps(
        receiver_matches[-1], "client receiver"
    )
    result["server_receiver_reported_mbps"] = _summary_rate_mbps(
        server_matches[-1], "server receiver"
    )
    if requested_bandwidth_mbps is not None:
        requested_bandwidth_mbps = float(requested_bandwidth_mbps)
        if not math.isfinite(requested_bandwidth_mbps) or requested_bandwidth_mbps <= 0:
            raise ValueError("Requested iperf bandwidth must be a positive finite rate")
        result["requested_bandwidth_mbps"] = requested_bandwidth_mbps
    sent_match = _IPERF_SENT_RE.search(sender_section)
    client_loss_match = _IPERF_LOSS_RE.search(receiver_matches[-1].group(0))
    server_loss_match = _IPERF_LOSS_RE.search(server_matches[-1].group(0))
    if not sent_match or not client_loss_match or not server_loss_match:
        raise ValueError(
            "Missing client sent-datagram count or receiver loss/total statistics"
        )
    sent = int(sent_match.group(1))
    client_lost, client_total = map(int, client_loss_match.groups())
    server_lost, server_total = map(int, server_loss_match.groups())
    received = client_total - client_lost
    result.update({
        "client_sent_datagrams": sent,
        "client_receiver_lost_datagrams": client_lost,
        "client_receiver_total_datagrams": client_total,
        "client_receiver_accounted_minus_sender_count": client_total - sent,
        "receiver_statistics_basis": (
            "iperf2 UDP sequence-number-derived Lost/Total; not a raw socket recv count"
        ),
        "sequence_accounted_nonlost_datagrams": received,
        # Retained for compatibility with existing result consumers. This is
        # sequence-derived, not a direct kernel/socket receive counter.
        "receiver_delivered_datagrams": received,
        "server_receiver_lost_datagrams": server_lost,
        "server_receiver_total_datagrams": server_total,
        "receiver_delivery_valid": False,
        "receiver_reports_match": False,
    })
    if min(sent, client_total, server_total) <= 0 or not (
        0 <= client_lost <= client_total and 0 <= server_lost <= server_total
    ):
        raise ValueError("Invalid iperf receiver packet/loss statistics")
    if received <= 0:
        raise ValueError("iperf receiver summary shows no sequence-accounted non-lost datagrams")
    # iperf2's legacy receiver Lost/Total values are derived from UDP sequence
    # IDs, while "Sent N datagrams" is a client counter. The iperf2 maintainer
    # documents that these counters can differ (packets in flight/final FIN).
    # Keep both counts and their difference as evidence; do not require equality.
    if (client_lost, client_total) != (server_lost, server_total):
        raise ValueError("Client and server receiver summaries disagree on packet totals")
    result["receiver_delivery_valid"] = True
    result["receiver_reports_match"] = (
        abs(client_receiver_duration - server_duration) <= 0.25
    )
    result["receiver_duration_difference_from_sender_seconds"] = round(
        abs(client_duration - client_receiver_duration), 3
    )
    if abs(client_duration - float(requested_duration)) > float(tolerance):
        raise ValueError(
            f"iperf sender duration {client_duration:g}s is outside requested "
            f"{requested_duration:g}s ± {tolerance:g}s"
        )
    if not result["receiver_reports_match"]:
        raise ValueError("Client and server receiver reports do not describe the same duration")
    result["duration_valid"] = True
    return result


def validate_offered_rate(summary, offered_rate_mbps, tolerance=SENDER_RATE_TOLERANCE):
    """Reject a run whose iperf sender did not execute the frozen offered load.

    Observed on 2026-10-24: after a VM suspend, clients averaged ~3 Mbps against
    the 6 Mbps profile while still satisfying the duration rules.
    """
    offered = float(offered_rate_mbps)
    achieved = float(summary["client_sender_reported_mbps"])
    if abs(achieved - offered) > float(tolerance) * offered:
        raise ValueError(
            "iperf sender achieved %.2f Mbps, outside %.0f%% of the %.1f Mbps offered load"
            % (achieved, 100 * float(tolerance), offered)
        )
    summary["offered_rate_valid"] = True
    return achieved


def _stop_and_reap(process, label, timeout=IPERF_PROCESS_CLEANUP_TIMEOUT_SECONDS):
    """Boundedly terminate and reap an iperf child, preserving its exit code."""
    if process is None:
        return None
    code = process.poll()
    if code is None:
        terminate_error = None
        try:
            process.terminate()
        except Exception as exc:
            terminate_error = exc
            try:
                process.kill()
            except Exception as kill_error:
                raise RuntimeError(
                    f"Could not terminate or kill iperf {label}: "
                    f"terminate={terminate_error}; kill={kill_error}"
                ) from kill_error
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                code = process.wait(timeout=timeout)
            except Exception as kill_error:
                raise RuntimeError(
                    f"Could not kill and reap iperf {label}: {kill_error}"
                ) from kill_error
        if terminate_error is not None and code is None:
            raise RuntimeError(
                f"Could not establish iperf {label} outcome after terminate failure: "
                f"{terminate_error}"
            )
    if code is None:
        raise RuntimeError(f"Could not establish terminal outcome for iperf {label}")
    return code


def _read_log(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Could not read iperf log {path}: {exc}") from exc


def run(logical_id, physical_id, normal_seconds=20, fault_seconds=20, recovery_seconds=20,
        switch_count=None):
    if os.geteuid() != 0:
        raise PermissionError("Live Mininet runs must be launched as root")
    topology = topology_for(switch_count)
    checks = preflight(logical_id, physical_id, topology.switch_count)
    if min(normal_seconds, fault_seconds, recovery_seconds) < 1:
        raise ValueError("All phase durations must be positive")
    requested_phases = {
        "normal": int(normal_seconds),
        "fault": int(fault_seconds),
        "recovery": int(recovery_seconds),
    }
    if requested_phases != checks["traffic_profile"]["phase_durations_seconds"]:
        raise ValueError(
            "Run phase durations must match the frozen traffic profile: "
            f"{checks['traffic_profile']['phase_durations_seconds']}"
        )

    from mininet.log import setLogLevel

    setLogLevel("info")
    output_dir = Path(checks["output_dir"])
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(mode=0o750, exist_ok=False)
    telemetry_path = output_dir / "telemetry.csv"
    phases_path = output_dir / "phase_events.csv"
    mapping_path = output_dir / "runtime_port_mapping.csv"
    metadata_path = output_dir / "run_metadata.json"
    iperf_server_log = output_dir / "iperf_server.log"
    iperf_client_log = output_dir / "iperf_client.log"
    metadata = {
        **checks,
        "status": "RUNNING_INVALID_UNTIL_COMPLETE",
        "started_at": now_iso(),
        "topology": [
            {"left": a, "right": b, "params": params or {}}
            for a, b, params in topology.link_definitions
        ],
        "topology_spec": topology.to_metadata(),
        "phase_durations_seconds": {
            "normal": normal_seconds, "fault": fault_seconds, "recovery": recovery_seconds
        },
        "phase_events": {},
    }
    _write_metadata(metadata_path, metadata)
    net = None
    collector = None
    iperf_server = None
    iperf_client = None
    iperf_server_stream = None
    iperf_client_stream = None
    iperf_server_started_monotonic = None
    iperf_client_started_monotonic = None
    iperf_records = {
        "server": {"pid": None, "returncode": None, "elapsed_seconds": None},
        "client": {"pid": None, "returncode": None, "elapsed_seconds": None},
    }
    metadata["iperf"] = {
        "server_mode": "iperf2 bounded server timeout (-t), followed by natural exit",
        "requested_duration_seconds": normal_seconds + fault_seconds + recovery_seconds,
        "duration_tolerance_seconds": IPERF_DURATION_TOLERANCE_SECONDS,
        "server_wait_timeout_seconds": IPERF_SERVER_WAIT_TIMEOUT_SECONDS,
        "processes": iperf_records,
        "completion_valid": False,
    }
    target_intfs = None
    fault_attempted = False
    clean_run = False
    try:
        net = _create_network(topology)
        net.start()
        peers, _interface_to_port, mapping_rows = _runtime_mapping(
            net, mapping_path, topology.switches
        )
        target, target_intfs, validated_target_mapping = _target_link(
            net, logical_id, peers, mapping_rows, target=checks["fault_link"]
        )
        metadata["fault_link"] = target
        metadata["runtime_switch_port_mapping"] = mapping_rows
        metadata["fault_target_runtime_mapping"] = validated_target_mapping
        _write_metadata(metadata_path, metadata)

        collector_duration = normal_seconds + fault_seconds + recovery_seconds + 5
        command = [
            sys.executable,
            "-c",
            "from telemetry import collect; import sys; "
            "collect(sys.argv[1], int(sys.argv[2]), duration=float(sys.argv[3]), "
            "switches=tuple(sys.argv[4].split(',')))",
            str(telemetry_path), str(physical_id), str(collector_duration),
            ",".join(topology.switches),
        ]
        collector = subprocess.Popen(command, cwd=str(PROJECT))

        phase_fields = (
            "physical_run_id", "logical_experiment_id", "timestamp",
            "phase", "fault_type", "fault_location",
        )
        with phases_path.open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=phase_fields)
            writer.writeheader()

            def mark(phase):
                event_time = now_iso()
                writer.writerow({
                    "physical_run_id": physical_id,
                    "logical_experiment_id": logical_id,
                    "timestamp": event_time,
                    "phase": phase,
                    "fault_type": FAULT_TYPE if phase != "normal" else "none",
                    "fault_location": target if phase != "normal" else "none",
                })
                stream.flush()
                metadata["phase_events"][phase] = event_time
                _write_metadata(metadata_path, metadata)

            first_sample_timestamp, normal_timestamp = record_normal_phase_after_sample(
                telemetry_path,
                collector,
                physical_id,
                writer,
                stream,
                logical_id,
                physical_id,
                target,
                timeout=FIRST_SAMPLE_TIMEOUT_SECONDS,
            )
            metadata["first_sample_observed_before_normal"] = first_sample_timestamp
            metadata["phase_events"]["normal"] = normal_timestamp
            _write_metadata(metadata_path, metadata)
            h1 = net.get("h1")
            h2 = net.get("h2")
            requested_iperf_duration = normal_seconds + fault_seconds + recovery_seconds
            iperf_server_stream = iperf_server_log.open("x", encoding="utf-8")
            server_started = time.monotonic()
            iperf_server_started_monotonic = server_started
            iperf_server = h2.popen(
                ["iperf", "-s", "-u", "-p", "5001", "-t",
                 str(int(requested_iperf_duration + IPERF_SERVER_GRACE_SECONDS))],
                stdout=iperf_server_stream,
                stderr=subprocess.STDOUT,
            )
            iperf_records["server"].update({
                "pid": getattr(iperf_server, "pid", None),
                "started_at": now_iso(),
            })
            time.sleep(2)
            if iperf_server.poll() is not None:
                raise RuntimeError(
                    f"iperf server terminated before client startup "
                    f"(exit {iperf_server.returncode})"
                )
            iperf_client_stream = iperf_client_log.open("x", encoding="utf-8")
            client_started = time.monotonic()
            iperf_client_started_monotonic = client_started
            iperf_client = h1.popen(
                ["iperf", "-c", "10.0.0.2", "-u", "-b",
                 iperf_bandwidth_argument(
                     checks["traffic_profile"]["offered_rate_mbps"]
                 ),
                 "-t", str(int(requested_iperf_duration)), "-p", "5001"],
                stdout=iperf_client_stream,
                stderr=subprocess.STDOUT,
            )
            iperf_records["client"].update({
                "pid": getattr(iperf_client, "pid", None),
                "started_at": now_iso(),
            })
            # iperf2 2.0.13 has no advertised one-off server flag. Its server
            # -t option bounds listener lifetime; the extra grace lets the
            # client finish and emit its UDP end-of-test report before natural exit.
            time.sleep(normal_seconds)
            if iperf_server.poll() is not None:
                raise RuntimeError(
                    f"iperf server terminated prematurely during normal phase "
                    f"(exit {iperf_server.returncode})"
                )
            if iperf_client.poll() is not None:
                raise RuntimeError(
                    f"iperf client terminated prematurely during normal phase "
                    f"(exit {iperf_client.returncode})"
                )

            fault_attempted = True
            _set_link(target_intfs, up=False)
            mark("fault")
            time.sleep(fault_seconds)
            if iperf_server.poll() is not None:
                raise RuntimeError(
                    f"iperf server terminated prematurely during fault phase "
                    f"(exit {iperf_server.returncode})"
                )
            if iperf_client.poll() is not None:
                raise RuntimeError(
                    f"iperf client terminated prematurely during fault phase "
                    f"(exit {iperf_client.returncode})"
                )

            _set_link(target_intfs, up=True)
            fault_attempted = False
            mark("recovery")
            time.sleep(recovery_seconds)

            client_returncode = iperf_client.wait(
                timeout=requested_iperf_duration + IPERF_CLIENT_WAIT_GRACE_SECONDS
            )
            client_elapsed = time.monotonic() - client_started
            iperf_records["client"].update({
                "returncode": client_returncode,
                "elapsed_seconds": round(client_elapsed, 6),
                "completed_at": now_iso(),
                "terminal_outcome": "exited" if client_returncode is not None else None,
            })
            if client_returncode != 0:
                raise RuntimeError(f"iperf client exited with status {client_returncode}")
            # iperf2 may exit several seconds after its bounded -t lifetime,
            # including the client/server startup offset.
            server_returncode = iperf_server.wait(
                timeout=IPERF_SERVER_WAIT_TIMEOUT_SECONDS
            )
            server_elapsed = time.monotonic() - server_started
            iperf_records["server"].update({
                "returncode": server_returncode,
                "elapsed_seconds": round(server_elapsed, 6),
                "completed_at": now_iso(),
                "terminal_outcome": "exited" if server_returncode is not None else None,
            })
            if server_returncode != 0:
                raise RuntimeError(f"iperf server exited with status {server_returncode}")
            for process_stream in (iperf_client_stream, iperf_server_stream):
                process_stream.flush()
                os.fsync(process_stream.fileno())
            metadata["iperf"]["summary_validation"] = validate_iperf_completion(
                client_returncode=client_returncode,
                server_returncode=server_returncode,
                client_log=_read_log(iperf_client_log),
                server_log=_read_log(iperf_server_log),
                requested_duration=requested_iperf_duration,
                client_elapsed=client_elapsed,
                server_elapsed=server_elapsed,
                requested_bandwidth_mbps=checks["traffic_profile"]["offered_rate_mbps"],
            )
            validate_offered_rate(
                metadata["iperf"]["summary_validation"],
                checks["traffic_profile"]["offered_rate_mbps"],
            )
            metadata["iperf"]["completion_valid"] = True
            _write_metadata(metadata_path, metadata)

        if collector.wait(timeout=collector_duration + 15) != 0:
            raise RuntimeError(f"Telemetry collector exited {collector.returncode}")
        with telemetry_path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            if tuple(reader.fieldnames or ()) != TELEMETRY_FIELDS:
                raise RuntimeError("Collector output schema mismatch")
        if not rows:
            raise RuntimeError("Collector produced no telemetry rows")
        if {row.get("experiment_id") for row in rows} != {str(physical_id)}:
            raise RuntimeError("Telemetry physical run ID mismatch")
        finalize_run_metadata(metadata, rows, metadata["phase_events"], physical_id)
        if not metadata["iperf"].get("completion_valid"):
            raise RuntimeError("iperf completion evidence was not validated")
        metadata["completed_at"] = now_iso()
        clean_run = True
    except Exception as exc:
        metadata["status"] = "FAILED_INVALID"
        metadata["failure"] = f"{type(exc).__name__}: {exc}"
        metadata.setdefault("iperf", {})["completion_valid"] = False
        metadata["iperf"].setdefault("summary_validation", {})["failure"] = metadata["failure"]
        metadata["failed_at"] = now_iso()
        raise
    finally:
        if fault_attempted and target_intfs:
            try:
                _set_link(target_intfs, up=True)
                metadata["cleanup_link_recovery_at"] = now_iso()
            except Exception as cleanup_error:
                metadata["cleanup_failure"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
                metadata["status"] = "FAILED_INVALID"
                clean_run = False
        for label, process in (("client", iperf_client), ("server", iperf_server)):
            if process is not None:
                try:
                    returncode = _stop_and_reap(process, label)
                    record = iperf_records[label]
                    if record.get("returncode") is None:
                        record["returncode"] = returncode
                        record["completed_at"] = now_iso()
                        record["terminal_outcome"] = "exited during cleanup"
                except Exception as cleanup_error:
                    metadata.setdefault("cleanup_failures", []).append(
                        f"iperf {label}: {type(cleanup_error).__name__}: {cleanup_error}"
                    )
                    metadata["status"] = "FAILED_INVALID"
                    metadata["iperf"]["completion_valid"] = False
                    clean_run = False
        for process_stream in (iperf_client_stream, iperf_server_stream):
            if process_stream is not None:
                try:
                    process_stream.flush()
                    os.fsync(process_stream.fileno())
                    process_stream.close()
                except Exception as cleanup_error:
                    metadata.setdefault("cleanup_failures", []).append(
                        f"iperf log flush/close: {type(cleanup_error).__name__}: {cleanup_error}"
                    )
                    metadata["status"] = "FAILED_INVALID"
                    metadata["iperf"]["completion_valid"] = False
                    clean_run = False
        for label, start_time in (
            ("client", iperf_client_started_monotonic),
            ("server", iperf_server_started_monotonic),
        ):
            record = iperf_records[label]
            if start_time is not None and record.get("elapsed_seconds") is None:
                record["elapsed_seconds"] = round(time.monotonic() - start_time, 6)
        if not metadata["iperf"].get("completion_valid"):
            validation = metadata["iperf"].setdefault("summary_validation", {})
            for label, log_path in (
                ("client", iperf_client_log),
                ("client_receiver", iperf_client_log),
                ("server", iperf_server_log),
            ):
                summary_key = label
                try:
                    duration = parse_iperf_final_duration(_read_log(log_path), label)
                    validation[f"{summary_key}_summary_valid"] = True
                    validation[f"{summary_key}_observed_duration_seconds"] = duration
                except (OSError, ValueError):
                    validation[f"{summary_key}_summary_valid"] = False
            validation["duration_valid"] = bool(
                validation.get("client_summary_valid")
                and validation.get("client_receiver_summary_valid")
                and validation.get("server_summary_valid")
                and abs(validation.get("client_observed_duration_seconds", -1)
                        - metadata["iperf"]["requested_duration_seconds"])
                    <= IPERF_DURATION_TOLERANCE_SECONDS
                and abs(validation.get("client_receiver_observed_duration_seconds", -1)
                        - validation.get("server_observed_duration_seconds", -1))
                    <= 0.25
            )
            if not validation.get("failure"):
                validation["failure"] = metadata.get("failure", "iperf completion was not validated")
        if collector and collector.poll() is None:
            collector.terminate()
            try:
                collector.wait(timeout=5)
            except subprocess.TimeoutExpired:
                collector.kill()
                collector.wait(timeout=5)
            if not clean_run:
                metadata["status"] = "FAILED_INVALID"
        if net:
            try:
                net.stop()
            except Exception as cleanup_error:
                metadata["cleanup_failure"] = f"{type(cleanup_error).__name__}: {cleanup_error}"
                metadata["status"] = "FAILED_INVALID"
                clean_run = False
        if not clean_run:
            metadata["status"] = "FAILED_INVALID"
        _write_metadata(metadata_path, metadata)
    if not clean_run or metadata["status"] != "COMPLETE":
        raise RuntimeError(f"Run is invalid; inspect {metadata_path}")
    print(f"Run complete: {output_dir}")


def verify_topology(switch_count=None, ping=True):
    """Start the topology, capture its runtime mapping, ping, and stop. Writes nothing."""
    import tempfile
    if os.geteuid() != 0:
        raise PermissionError("Live Mininet verification must be launched as root")
    topology = topology_for(switch_count)
    ovs = subprocess.run(["ovs-vsctl", "list-br"], check=True, capture_output=True, text=True)
    conflicts = sorted(set(ovs.stdout.split()).intersection(topology.switches))
    if conflicts:
        raise RuntimeError(f"Existing OVS bridges conflict with this topology: {conflicts}")
    from mininet.log import setLogLevel
    setLogLevel("warning")
    net = _create_network(topology)
    result = {
        "switch_count": topology.switch_count,
        "candidate_links": list(topology.candidate_links),
        "expected_candidate_count": topology.switch_count - 1,
    }
    try:
        started = time.monotonic()
        net.start()
        result["start_seconds"] = round(time.monotonic() - started, 3)
        with tempfile.TemporaryDirectory() as scratch:
            mapping_path = Path(scratch) / "runtime_port_mapping.csv"
            _peers, _interface_to_port, rows = _runtime_mapping(net, mapping_path, topology.switches)
        links = sorted({row["link"] for row in rows})
        inter_switch = [link for link in links if topology.is_candidate(link)]
        result["observed_inter_switch_links"] = inter_switch
        result["observed_inter_switch_link_count"] = len(inter_switch)
        result["mapping_rows"] = rows
        result["switch_count_observed"] = len({row["switch"] for row in rows})
        result["host_count"] = len([node for node in ("h1", "h2") if net.get(node) is not None])
        if ping:
            sweep_started = time.monotonic()
            for switch in topology.switches:
                subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "dump-ports", switch],
                               check=True, capture_output=True, text=True)
                subprocess.run(["ovs-ofctl", "-O", "OpenFlow13", "show", switch],
                               check=True, capture_output=True, text=True)
            result["collector_sweep_seconds"] = round(time.monotonic() - sweep_started, 3)
            result["ping_loss_percent"] = float(net.pingAll(timeout="2"))
    finally:
        net.stop()
    result["post_stop_bridges"] = subprocess.run(
        ["ovs-vsctl", "list-br"], check=True, capture_output=True, text=True
    ).stdout.split()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switches", type=int, choices=SUPPORTED_SWITCH_COUNTS, default=4,
                        help="linear topology size; 4 is the original study topology")
    parser.add_argument("--logical-id", type=int)
    parser.add_argument("--physical-id", type=int)
    parser.add_argument("--normal-seconds", type=int, default=20)
    parser.add_argument("--fault-seconds", type=int, default=20)
    parser.add_argument("--recovery-seconds", type=int, default=20)
    parser.add_argument("--run", action="store_true", help="explicitly launch Mininet and inject the configured link fault")
    parser.add_argument("--verify-topology", action="store_true",
                        help="start the topology, print its runtime mapping and ping result, stop; no run directory, no fault")
    args = parser.parse_args(argv)
    if args.verify_topology:
        print(json.dumps(verify_topology(args.switches), indent=2))
        return
    if args.logical_id is None or args.physical_id is None:
        parser.error("--logical-id and --physical-id are required unless --verify-topology is used")
    if args.run:
        run(args.logical_id, args.physical_id, args.normal_seconds, args.fault_seconds,
            args.recovery_seconds, switch_count=args.switches)
    else:
        print(json.dumps(preflight(args.logical_id, args.physical_id, args.switches), indent=2))
        print("Preflight only: no files created, no Mininet started, no fault injected.")


if __name__ == "__main__":
    main()
