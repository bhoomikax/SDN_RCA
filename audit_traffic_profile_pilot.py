"""Independently audit preserved 6 Mbps pilot artifacts without modifying them."""

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telemetry_pipeline import TELEMETRY_FIELDS


ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "traffic_profiles" / "udp_6mbps_v1.json"
HASH_MANIFEST = ROOT / "PILOT_EVIDENCE_SHA256SUMS.txt"
RUNS = (
    (30, 26, "FAILED_INVALID"),
    (31, 27, "COMPLETE"),
)
NUMERIC_FIELDS = (
    "rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes",
    "tx_dropped", "rx_packet_rate", "tx_packet_rate",
    "rx_throughput_mbps", "tx_throughput_mbps",
)
ARTIFACTS = (
    "iperf_client.log", "iperf_server.log", "phase_events.csv",
    "run_metadata.json", "runtime_port_mapping.csv", "telemetry.csv",
    "udp_6mbps_v1.json",
)
SUMMARY_RE = re.compile(
    r"^\s*\[\s*\d+\]\s+(\d+(?:\.\d+)?)\s*-\s*"
    r"(\d+(?:\.\d+)?)\s+sec\s+.+?\b(?:K|M|G)?(?:bits|Bytes)/sec\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
RATE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*([KMG]?)(bits|Bytes)/sec\b")
LOSS_RE = re.compile(r"\b(\d+)\s*/\s*(\d+)\s*\((\d+(?:\.\d+)?)%\)")
SENT_RE = re.compile(r"\bSent\s+(\d+)\s+datagrams\b", re.IGNORECASE)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _iperf_summary(path):
    text = path.read_text(encoding="utf-8")
    summaries = list(SUMMARY_RE.finditer(text))
    if not summaries:
        raise ValueError(f"Missing aggregate iperf summary in {path.name}")

    def rate_from(match):
        rates = RATE_RE.findall(match.group(0))
        if not rates:
            raise ValueError(f"Missing aggregate iperf rate in {path.name}")
        value, prefix, unit = rates[-1]
        scale = {"": 1.0, "K": 0.001, "M": 1.0, "G": 1000.0}[prefix]
        if unit == "Bytes":
            scale *= 8.0
        return float(value) * scale

    match = summaries[-1]
    loss = LOSS_RE.search(match.group(0))
    if loss is None:
        raise ValueError(f"Incomplete receiver iperf summary in {path.name}")
    return {
        "duration_seconds": float(summaries[0].group(2)) - float(summaries[0].group(1)),
        "rate_mbps": rate_from(summaries[0]),
        "receiver_duration_seconds": float(match.group(2)) - float(match.group(1)),
        "receiver_rate_mbps": rate_from(match),
        "lost_datagrams": int(loss.group(1)),
        "total_datagrams": int(loss.group(2)),
        "reported_loss_percent": float(loss.group(3)),
    }


def _sent_datagrams(path):
    matches = SENT_RE.findall(path.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise ValueError(f"Expected one sender datagram count in {path.name}")
    return int(matches[0])


def _verify_metadata_value(metadata, key, actual, tolerance=0.011):
    if key not in metadata:
        return
    expected = metadata[key]
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if not math.isclose(float(actual), float(expected), abs_tol=tolerance):
            raise ValueError(f"iperf summary {key} disagrees with run metadata")
    elif actual != expected:
        raise ValueError(f"iperf summary {key} disagrees with run metadata")


def _load_run(physical_id, logical_id, expected_status, profile_hash):
    directory = ROOT / f"pilot_evidence_20261017_physical{physical_id}_logical{logical_id}"
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    entries = list(directory.iterdir())
    if any(not path.is_file() for path in entries) or {
        path.name for path in entries
    } != set(ARTIFACTS):
        raise ValueError(f"Unexpected or missing artifact files in {directory.name}")

    metadata = _read_json(directory / "run_metadata.json")
    if (metadata.get("physical_run_id"), metadata.get("logical_experiment_id")) != (
        physical_id, logical_id
    ):
        raise ValueError(f"ID mismatch in {directory.name}")
    if metadata.get("status") != expected_status:
        raise ValueError(f"Unexpected preserved status in {directory.name}")
    if metadata.get("traffic_profile", {}).get("sha256") != profile_hash:
        raise ValueError(f"Run profile hash mismatch in {directory.name}")
    if _sha256(directory / "udp_6mbps_v1.json") != profile_hash:
        raise ValueError(f"Frozen profile artifact hash mismatch in {directory.name}")
    if metadata.get("fault_link") != "s2-s3":
        raise ValueError(f"Declared fault target mismatch in {directory.name}")
    if metadata.get("traffic_profile", {}).get("phase_durations_seconds") != {
        "normal": 20, "fault": 20, "recovery": 20
    }:
        raise ValueError(f"Run phase profile mismatch in {directory.name}")
    expected_topology = {
        tuple(sorted(link)) for link in (
            ("h1", "s1"), ("s1", "s2"), ("s2", "s3"), ("s3", "s4"), ("s4", "h2")
        )
    }
    actual_topology = {
        tuple(sorted((link["left"], link["right"])))
        for link in metadata.get("topology", [])
    }
    if actual_topology != expected_topology:
        raise ValueError(f"Run topology differs from declared pilot topology in {directory.name}")

    with (directory / "telemetry.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != TELEMETRY_FIELDS:
            raise ValueError(f"Telemetry schema mismatch in {directory.name}")
        rows = list(reader)
    if (
        metadata.get("telemetry_rows") is not None
        and len(rows) != metadata["telemetry_rows"]
    ):
        raise ValueError(f"Telemetry row count mismatch in {directory.name}")
    keys = [(row["timestamp"], row["switch"], row["port"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"Duplicate telemetry observation in {directory.name}")
    if {row["experiment_id"] for row in rows} != {str(physical_id)}:
        raise ValueError(f"Telemetry physical ID mismatch in {directory.name}")
    if {row["switch"] for row in rows} != {"s1", "s2", "s3", "s4"}:
        raise ValueError(f"Incomplete switch coverage in {directory.name}")
    numbered_ports = {
        (row["switch"], row["port"]) for row in rows if row["port"] != "LOCAL"
    }
    if numbered_ports != {
        (switch, port) for switch in ("s1", "s2", "s3", "s4") for port in ("1", "2")
    }:
        raise ValueError(f"Unexpected numbered switch-port coverage in {directory.name}")
    for row in rows:
        for name in NUMERIC_FIELDS:
            try:
                value = float(row[name])
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid numeric field {name} in {directory.name}") from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Non-finite or negative {name} in {directory.name}")

    with (directory / "runtime_port_mapping.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        mapping_rows = list(csv.DictReader(stream))
    if mapping_rows != metadata.get("runtime_switch_port_mapping"):
        raise ValueError(f"Runtime mapping disagrees with metadata in {directory.name}")
    expected_mapping = {
        ("s1", "1", "s1-eth1", "h1", "h1-eth0"),
        ("s1", "2", "s1-eth2", "s2", "s2-eth1"),
        ("s2", "1", "s2-eth1", "s1", "s1-eth2"),
        ("s2", "2", "s2-eth2", "s3", "s3-eth1"),
        ("s3", "1", "s3-eth1", "s2", "s2-eth2"),
        ("s3", "2", "s3-eth2", "s4", "s4-eth1"),
        ("s4", "1", "s4-eth1", "s3", "s3-eth2"),
        ("s4", "2", "s4-eth2", "h2", "h2-eth0"),
    }
    actual_mapping = {
        (
            row["switch"], row["openflow_port"], row["interface_name"],
            row["peer_node"], row["peer_interface"],
        )
        for row in mapping_rows
    }
    if actual_mapping != expected_mapping or len(mapping_rows) != len(expected_mapping):
        raise ValueError(f"Runtime mapping does not cover the declared topology in {directory.name}")
    target_rows = metadata.get("fault_target_runtime_mapping", [])
    target_by_switch = {row["switch"]: row for row in target_rows}
    if set(target_by_switch) != {"s2", "s3"}:
        raise ValueError(f"Missing target mapping in {directory.name}")
    if (
        target_by_switch["s2"]["interface_name"] != "s2-eth2"
        or target_by_switch["s2"]["openflow_port"] != "2"
        or target_by_switch["s3"]["interface_name"] != "s3-eth1"
        or target_by_switch["s3"]["openflow_port"] != "1"
        or target_by_switch["s2"]["peer_interface"] != "s3-eth1"
        or target_by_switch["s3"]["peer_interface"] != "s2-eth2"
        or any(row["link"] != "s2-s3" for row in target_rows)
    ):
        raise ValueError(f"Fault target mapping is not reciprocal in {directory.name}")

    with (directory / "phase_events.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        phase_rows = list(csv.DictReader(stream))
    if [row["phase"] for row in phase_rows] != ["normal", "fault", "recovery"]:
        raise ValueError(f"Unexpected phase rows in {directory.name}")
    if (
        phase_rows[0]["fault_type"] != "none"
        or phase_rows[0]["fault_location"] != "none"
        or any(
            row["fault_type"] != "link_failure" or row["fault_location"] != "s2-s3"
            for row in phase_rows[1:]
        )
    ):
        raise ValueError(f"Fault annotations disagree with the pilot target in {directory.name}")
    csv_events = {row["phase"]: row["timestamp"] for row in phase_rows}
    if csv_events != metadata.get("phase_events"):
        raise ValueError(f"Phase-event CSV disagrees with metadata in {directory.name}")
    events = {
        phase: datetime.fromisoformat(value).astimezone(timezone.utc)
        for phase, value in csv_events.items()
    }
    if not events["normal"] < events["fault"] < events["recovery"]:
        raise ValueError(f"Unordered phase events in {directory.name}")
    telemetry_tz = datetime.fromisoformat(csv_events["normal"]).tzinfo
    stamped_rows = [
        (
            datetime.fromisoformat(row["timestamp"]).replace(
                tzinfo=telemetry_tz
            ).astimezone(timezone.utc),
            row,
        )
        for row in rows
    ]
    first, last = min(stamp for stamp, _ in stamped_rows), max(
        stamp for stamp, _ in stamped_rows
    )
    telemetry_bounds_recorded = all(
        key in metadata for key in ("telemetry_start", "telemetry_end")
    )
    if telemetry_bounds_recorded:
        recorded_start = datetime.fromisoformat(
            metadata["telemetry_start"]
        ).astimezone(timezone.utc)
        recorded_end = datetime.fromisoformat(
            metadata["telemetry_end"]
        ).astimezone(timezone.utc)
        if (first, last) != (recorded_start, recorded_end):
            raise ValueError(f"Telemetry coverage disagrees with metadata in {directory.name}")
    if not first <= events["normal"] < events["fault"] < events["recovery"] <= last:
        raise ValueError(f"Phase events not covered by telemetry in {directory.name}")
    declared_durations = metadata.get("phase_durations_seconds", {})
    if declared_durations != {"normal": 20, "fault": 20, "recovery": 20}:
        raise ValueError(f"Declared phase durations mismatch in {directory.name}")

    client = _iperf_summary(directory / "iperf_client.log")
    server = _iperf_summary(directory / "iperf_server.log")
    sender_datagrams = _sent_datagrams(directory / "iperf_client.log")
    receiver_summaries_match = (
        client["lost_datagrams"] == server["lost_datagrams"]
        and client["total_datagrams"] == server["total_datagrams"]
    )
    iperf = metadata.get("iperf", {})
    validation = iperf.get("summary_validation", {})
    if expected_status == "COMPLETE":
        processes = iperf.get("processes", {})
        if not iperf.get("completion_valid") or not validation.get("receiver_reports_match"):
            raise ValueError("Completed run does not have valid matching iperf summaries")
        if any(processes.get(role, {}).get("returncode") != 0 for role in ("client", "server")):
            raise ValueError("Completed run has a nonzero iperf process status")
        if client["duration_seconds"] < 58 or client["duration_seconds"] > 62:
            raise ValueError("Completed run duration is outside the declared tolerance")
        if client["total_datagrams"] != server["total_datagrams"]:
            raise ValueError("Client/server UDP datagram totals differ")
        if client["lost_datagrams"] != server["lost_datagrams"]:
            raise ValueError("Client/server UDP loss totals differ")
        if sender_datagrams != client["total_datagrams"]:
            raise ValueError("Client sender and receiver datagram totals differ")
        if abs(client["rate_mbps"] - 6.0) > 0.6:
            raise ValueError("Completed run sender rate is outside the declared tolerance")
    elif not (
        not iperf.get("completion_valid")
        and "timed out" in metadata.get("failure", "").lower()
    ):
        raise ValueError("Run 30 no longer shows its preserved invalid iperf wait")

    client_process = metadata.get("iperf", {}).get("processes", {}).get("client", {})
    client_start = datetime.fromisoformat(client_process["started_at"]).astimezone(timezone.utc)
    client_end = datetime.fromisoformat(client_process["completed_at"]).astimezone(timezone.utc)
    phase_bounds = (
        ("normal", max(events["normal"], client_start), events["fault"]),
        ("fault", events["fault"], events["recovery"]),
        ("recovery", events["recovery"], min(client_end, last + timedelta(microseconds=1))),
    )
    phase_metrics = {}
    for phase, start, end in phase_bounds:
        selected = [
            row for stamp, row in stamped_rows
            if start <= stamp < end and (
                (row["switch"], row["port"]) in {("s2", "2"), ("s3", "1")}
            )
        ]
        measurements = {}
        for switch, port, field in (
            ("s2", "2", "tx_throughput_mbps"),
            ("s3", "1", "rx_throughput_mbps"),
        ):
            values = [
                float(row[field]) for row in selected
                if row["switch"] == switch and row["port"] == port
            ]
            if not values:
                raise ValueError(f"Missing {phase} measurements for {switch} port {port}")
            measurements[f"{switch}_port{port}_{field}_mean_mbps"] = sum(values) / len(values)
            measurements[f"{switch}_port{port}_sample_count"] = len(values)
        measurements["active_traffic_window_seconds"] = (end - start).total_seconds()
        if abs(measurements["active_traffic_window_seconds"] - declared_durations[phase]) > 2.0:
            raise ValueError(f"Active {phase} traffic duration outside tolerance in {directory.name}")
        phase_metrics[phase] = measurements

    summary = iperf.get("summary_validation", {})
    _verify_metadata_value(summary, "client_sender_reported_mbps", client["rate_mbps"])
    _verify_metadata_value(summary, "client_receiver_reported_mbps", client["receiver_rate_mbps"])
    _verify_metadata_value(summary, "client_receiver_lost_datagrams", client["lost_datagrams"], 0)
    _verify_metadata_value(summary, "client_receiver_total_datagrams", client["total_datagrams"], 0)
    _verify_metadata_value(summary, "client_sent_datagrams", sender_datagrams, 0)
    client_duration_metadata_value = (
        client["duration_seconds"]
        if "client_receiver_observed_duration_seconds" in summary
        else client["receiver_duration_seconds"]
    )
    _verify_metadata_value(
        summary, "client_observed_duration_seconds", client_duration_metadata_value
    )
    _verify_metadata_value(
        summary, "client_receiver_observed_duration_seconds",
        client["receiver_duration_seconds"]
    )
    _verify_metadata_value(summary, "server_receiver_reported_mbps", server["receiver_rate_mbps"])
    _verify_metadata_value(summary, "server_receiver_lost_datagrams", server["lost_datagrams"], 0)
    _verify_metadata_value(summary, "server_receiver_total_datagrams", server["total_datagrams"], 0)

    artifacts = {
        name: _sha256(directory / name) for name in ARTIFACTS
    }
    cleanup_recorded = any(
        key.startswith("cleanup") or key in {"post_run_ovs_bridges", "post_run_processes"}
        for key in metadata
    )
    return {
        "physical_id": physical_id,
        "logical_id": logical_id,
        "status": expected_status,
        "row_count": len(rows),
        "telemetry_key_count": len(keys),
        "numbered_switch_ports": 8,
        "coverage_start_utc": first.isoformat(),
        "coverage_end_utc": last.isoformat(),
        "telemetry_bounds_recorded_in_metadata": telemetry_bounds_recorded,
        "phase_events_utc": {key: value.isoformat() for key, value in events.items()},
        "observed_phase_durations_seconds": {
            "normal": (events["fault"] - events["normal"]).total_seconds(),
            "fault": (events["recovery"] - events["fault"]).total_seconds(),
            "recovery_until_last_sample": (last - events["recovery"]).total_seconds(),
        },
        "iperf_client_active_phase_seconds": {
            phase: (end - start).total_seconds()
            for phase, start, end in phase_bounds
        },
        "normal_event_precedes_iperf_client_seconds": max(
            0.0, (client_start - events["normal"]).total_seconds()
        ),
        "runtime_fault_mapping": target_rows,
        "iperf_client_aggregate": client,
        "iperf_server_aggregate": server,
        "client_sender_datagrams": sender_datagrams,
        "receiver_summaries_match": receiver_summaries_match,
        "client_minus_server_receiver_summary": {
            "lost_datagrams": client["lost_datagrams"] - server["lost_datagrams"],
            "total_datagrams": client["total_datagrams"] - server["total_datagrams"],
        },
        "phase_telemetry": phase_metrics,
        "iperf_phase_specific_loss_available": False,
        "cleanup_evidence_in_metadata": cleanup_recorded,
        "cleanup_assessment": (
            "Recorded" if cleanup_recorded else
            "No post-run bridge/process snapshot is persisted. Metadata reports no separate "
            "cleanup failure, but process/bridge cleanup cannot be independently verified "
            "from this artifact set."
        ),
        "artifact_sha256": artifacts,
    }


def audit():
    profile = _read_json(PROFILE)
    profile_hash = _sha256(PROFILE)
    if (
        profile.get("profile_id") != "udp_6mbps_s2s3_10mbps_v1"
        or profile.get("offered_rate_mbps") != 6.0
        or profile.get("bottleneck_capacity_mbps") != 10.0
        or profile.get("phase_durations_seconds") != {
            "normal": 20, "fault": 20, "recovery": 20
        }
    ):
        raise ValueError("Current frozen profile does not match the pilot protocol")
    runs = [
        _load_run(physical, logical, status, profile_hash)
        for physical, logical, status in RUNS
    ]
    expected_hashes = {
        f"pilot_evidence_20261017_physical{run['physical_id']}_logical{run['logical_id']}/{name}": digest
        for run in runs
        for name, digest in run["artifact_sha256"].items()
    }
    manifest_hashes = {}
    for line in HASH_MANIFEST.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            if parts[1] in manifest_hashes:
                raise ValueError(f"Duplicate artifact hash manifest entry: {parts[1]}")
            manifest_hashes[parts[1]] = parts[0]
    if manifest_hashes != expected_hashes:
        raise ValueError("Pilot artifact hashes do not match the preserved SHA-256 manifest")
    return {
        "classification": "single engineering pilot; not a repeatability study or dataset cohort",
        "profile_sha256": profile_hash,
        "hash_manifest_verified": True,
        "admission_criteria_status": (
            "Exploratory engineering repeat rule: written after run 30 failed and before "
            "run 31; not preregistered before the pilot program or suitable as confirmatory "
            "evidence."
        ),
        "phase_loss_assessment": (
            "iperf2 files contain only one whole-run receiver summary; baseline and outage "
            "UDP loss cannot be separated. Use telemetry phase rates descriptively, not as "
            "packet-loss estimates."
        ),
        "clock_assessment": (
            "VM NTPSynchronized=no was observed contemporaneously; absolute alignment to "
            "Windows/external clocks is not established."
        ),
        "runs": runs,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
