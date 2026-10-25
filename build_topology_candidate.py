"""Build a validated candidate dataset for one linear topology size from raw runs.

Applies the same admission rules as build_validated_candidate.py (schema,
finite values, duplicate keys, switch coverage, runtime mapping consistency,
reciprocal target mapping, ordered phase coverage, iperf process and summary
evidence, hashes) to runs collected with --switches N. Runs that fail any
check are excluded and recorded; nothing is fabricated, relabeled, or
duplicated. Outputs go to a new directory only; raw evidence is never written.
"""

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from build_validated_candidate import (
    DATASET_FIELDS, MAPPING_FIELDS, NUMERIC_FIELDS, PHASES, _event_wall_time,
    _finite_nonnegative, read_csv, sha256,
)
from experiment_runner_recollection import validate_iperf_completion
from linear_topology import LinearTopology, topology_run_registry
from telemetry_pipeline import TELEMETRY_FIELDS


RAW_FILES = ("telemetry.csv", "phase_events.csv", "runtime_port_mapping.csv",
             "run_metadata.json", "iperf_client.log", "iperf_server.log")
MANIFEST_FIELDS = (
    "experiment_id", "physical_run_id", "switch_count", "candidate_count", "fault_type",
    "fault_link", "normal_event", "fault_event", "recovery_event", "telemetry_rows",
    "distinct_timestamps", "median_sample_interval_seconds", "fault_window_10s_timestamps",
    "iperf_sender_seconds", "iperf_sender_mbps", "iperf_receiver_lost_datagrams", "iperf_receiver_total_datagrams",
    "rx_counters_all_zero", "status", "admission_basis", "run_dir",
)
# The frozen profile offers 6 Mbps; iperf2 reports 6.29 Mbps for a correctly paced
# client. A run whose sender averaged far less (observed: ~3 Mbps after a VM
# suspend) did not execute the profile and is rejected.
SENDER_RATE_TOLERANCE = 0.10
ALLOWED_IPERF_DIFFERENCES = {
    "client_receiver_accounted_minus_sender_count", "receiver_statistics_basis",
    "sequence_accounted_nonlost_datagrams", "receiver_duration_difference_from_sender_seconds",
}


def validate_topology_run(run_dir, topology, registry):
    """Revalidate one raw run directory; raise ValueError with the rejection reason."""
    run_dir = Path(run_dir)
    missing = [name for name in RAW_FILES if not (run_dir / name).is_file()]
    if missing:
        raise ValueError("missing raw artifact(s): %s" % missing)
    hashes = {name: sha256(run_dir / name) for name in RAW_FILES}
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    status = metadata.get("status")
    if status != "COMPLETE":
        raise ValueError("run metadata status is %r, not COMPLETE" % status)
    try:
        physical_id = int(metadata["physical_run_id"])
        logical_id = int(metadata["logical_experiment_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("missing or malformed run identity") from exc
    expected_name = "physical_%d_logical_%d" % (physical_id, logical_id)
    if run_dir.name != expected_name:
        raise ValueError("directory name %r disagrees with metadata identity %r" % (run_dir.name, expected_name))
    entry = registry.get(logical_id)
    if entry is None or entry["physical_run_id"] != physical_id:
        raise ValueError("unregistered logical/physical pair %d/%d" % (logical_id, physical_id))
    link = metadata.get("fault_link")
    if link != entry["fault_link"]:
        raise ValueError("fault link %r disagrees with registry %r" % (link, entry["fault_link"]))
    if not topology.is_candidate(link):
        raise ValueError("fault link %r is not an inter-switch candidate" % link)
    if metadata.get("switch_count") != topology.switch_count:
        raise ValueError("metadata switch_count %r != %d" % (metadata.get("switch_count"), topology.switch_count))
    try:
        LinearTopology.from_metadata(metadata.get("topology_spec"))
    except ValueError as exc:
        raise ValueError("topology_spec invalid: %s" % exc) from exc
    if LinearTopology.from_metadata(metadata["topology_spec"]) != topology:
        raise ValueError("topology_spec describes a different topology")
    profile = metadata.get("traffic_profile", {})
    if profile.get("bottleneck_link") != topology.bottleneck_link or float(profile.get("offered_rate_mbps", 0)) != 6.0:
        raise ValueError("traffic profile does not match the frozen 6 Mbps profile for this topology")

    telemetry_fields, raw = read_csv(run_dir / "telemetry.csv")
    if telemetry_fields != TELEMETRY_FIELDS or not raw:
        raise ValueError("telemetry schema invalid or empty")
    if metadata.get("telemetry_rows") is not None and len(raw) != metadata["telemetry_rows"]:
        raise ValueError("metadata row count disagrees with telemetry")
    keys, stamps, switches, mapping_keys = set(), [], set(), set()
    rx_all_zero = True
    for number, row in enumerate(raw, start=2):
        if row["experiment_id"] != str(physical_id):
            raise ValueError("telemetry physical ID mismatch at row %d" % number)
        if row["switch"] not in topology.switches:
            raise ValueError("unexpected switch %r at row %d" % (row["switch"], number))
        if not row["port"] or not row["interface_name"]:
            raise ValueError("missing port/interface at row %d" % number)
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
        except ValueError as exc:
            raise ValueError("malformed telemetry timestamp at row %d" % number) from exc
        _finite_nonnegative(row, NUMERIC_FIELDS, number)
        key = (stamp.isoformat(), row["switch"], row["port"])
        if key in keys:
            raise ValueError("duplicate telemetry key at row %d" % number)
        keys.add(key)
        stamps.append(stamp)
        switches.add(row["switch"])
        if row["port"] != "LOCAL":
            mapping_keys.add((row["switch"], row["port"], row["interface_name"]))
            if any(float(row[name]) != 0.0 for name in ("rx_packets", "rx_bytes", "rx_packet_rate", "rx_throughput_mbps")):
                rx_all_zero = False
    if switches != set(topology.switches):
        raise ValueError("missing switch coverage: %s" % sorted(set(topology.switches) - switches))

    mapping_fields, mapping = read_csv(run_dir / "runtime_port_mapping.csv")
    if mapping_fields != MAPPING_FIELDS or not mapping:
        raise ValueError("runtime port mapping schema invalid or empty")
    seen = set()
    for row in mapping:
        key = (row["switch"], row["openflow_port"], row["interface_name"])
        if key in seen:
            raise ValueError("duplicate runtime port mapping %s" % (key,))
        seen.add(key)
    if mapping != metadata.get("runtime_switch_port_mapping"):
        raise ValueError("runtime mapping CSV disagrees with run metadata")
    if mapping_keys != seen:
        raise ValueError("telemetry port/interface coverage disagrees with runtime mapping")
    link_rows = {}
    for row in mapping:
        link_rows.setdefault(row["link"], []).append(row)
    for candidate in topology.candidate_links:
        rows = link_rows.get(candidate, [])
        if len(rows) != 2 or {row["switch"] for row in rows} != set(candidate.split("-")):
            raise ValueError("candidate link %s lacks exactly two endpoint mappings" % candidate)
        pairs = {(r["switch"], r["interface_name"], r["peer_node"], r["peer_interface"]) for r in rows}
        for switch, interface, peer, peer_interface in pairs:
            if (peer, peer_interface, switch, interface) not in pairs:
                raise ValueError("non-reciprocal endpoint mapping for %s" % candidate)
    if link_rows.get(link) != metadata.get("fault_target_runtime_mapping"):
        raise ValueError("fault target mapping differs from recorded runtime mapping")

    phase_fields, phases = read_csv(run_dir / "phase_events.csv")
    if set(phase_fields) != {"physical_run_id", "logical_experiment_id", "timestamp", "phase", "fault_type", "fault_location"}:
        raise ValueError("phase-event schema mismatch")
    if len(phases) != 3 or {row["phase"] for row in phases} != set(PHASES):
        raise ValueError("phase log must contain exactly normal, fault, and recovery")
    if any((row["physical_run_id"], row["logical_experiment_id"]) != (str(physical_id), str(logical_id)) for row in phases):
        raise ValueError("phase-log IDs inconsistent")
    event_map = {row["phase"]: row["timestamp"] for row in phases}
    if event_map != metadata.get("phase_events"):
        raise ValueError("phase CSV events disagree with run metadata")
    normal, fault, recovery = (_event_wall_time(event_map[name], name) for name in PHASES)
    first, last = min(stamps), max(stamps)
    if not (first <= normal < fault < recovery <= last):
        raise ValueError("phase events unordered or outside telemetry coverage")
    fault_row = next(row for row in phases if row["phase"] == "fault")
    if fault_row["fault_type"] != "link_failure" or fault_row["fault_location"] != link:
        raise ValueError("recorded fault event does not identify link failure %s" % link)

    iperf = metadata.get("iperf", {})
    processes = iperf.get("processes", {})
    for label in ("client", "server"):
        record = processes.get(label, {})
        if record.get("terminal_outcome") != "exited":
            raise ValueError("iperf %s has no documented natural terminal outcome" % label)
        if not isinstance(record.get("pid"), int) or record["pid"] <= 0:
            raise ValueError("iperf %s PID missing or invalid" % label)
        if record.get("returncode") != 0:
            raise ValueError("iperf %s return code not successful" % label)
        try:
            started = datetime.fromisoformat(record["started_at"])
            completed = datetime.fromisoformat(record["completed_at"])
            elapsed = float(record["elapsed_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("iperf %s process timing metadata invalid" % label) from exc
        if completed < started or not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError("iperf %s process timing unordered or invalid" % label)
    result = validate_iperf_completion(
        client_returncode=processes["client"]["returncode"],
        server_returncode=processes["server"]["returncode"],
        client_log=(run_dir / "iperf_client.log").read_text(encoding="utf-8"),
        server_log=(run_dir / "iperf_server.log").read_text(encoding="utf-8"),
        requested_duration=iperf.get("requested_duration_seconds"),
        client_elapsed=processes["client"]["elapsed_seconds"],
        server_elapsed=processes["server"]["elapsed_seconds"],
        requested_bandwidth_mbps=profile.get("offered_rate_mbps"),
    )
    if not iperf.get("completion_valid"):
        raise ValueError("iperf completion flag is not valid")
    offered = float(profile["offered_rate_mbps"])
    achieved = float(result["client_sender_reported_mbps"])
    if abs(achieved - offered) > SENDER_RATE_TOLERANCE * offered:
        raise ValueError("iperf sender achieved %.2f Mbps, outside %.0f%% of the %.1f Mbps profile (traffic execution invalid)"
                         % (achieved, 100 * SENDER_RATE_TOLERANCE, offered))
    recorded = iperf.get("summary_validation", {})
    differences = {}
    for key, value in result.items():
        if key in {"client_elapsed_seconds", "server_elapsed_seconds"} or key not in recorded:
            continue
        if recorded.get(key) != value:
            differences[key] = {"metadata": recorded.get(key), "reparsed_logs": value}
    unexpected = sorted(set(differences) - ALLOWED_IPERF_DIFFERENCES)
    if unexpected:
        raise ValueError("iperf metadata disagrees with parsed evidence: %s" % unexpected)

    ordered_stamps = sorted(set(stamps))
    intervals = [(b - a).total_seconds() for a, b in zip(ordered_stamps, ordered_stamps[1:])]
    fault_window = [s for s in ordered_stamps if fault <= s < recovery and (s - fault).total_seconds() <= 10.0]
    return {
        "logical_experiment_id": logical_id, "physical_run_id": physical_id,
        "fault_link": link, "switch_count": topology.switch_count,
        "raw_artifact_sha256": hashes, "telemetry_rows": len(raw),
        "distinct_timestamps": len(ordered_stamps),
        "median_sample_interval_seconds": round(statistics.median(intervals), 4) if intervals else None,
        "fault_window_10s_timestamps": len(fault_window),
        "telemetry_start": first.isoformat(), "telemetry_end": last.isoformat(),
        "phase_events": event_map, "runtime_port_mapping": mapping,
        "target_mapping": link_rows[link], "iperf_validation": result,
        "recorded_iperf_summary_differences": differences,
        "rx_counters_all_zero": rx_all_zero,
        "admission_status": "VALID",
        "admission_basis": ("Complete independent artifact revalidation: registry identity, topology spec, "
                            "schema, finite telemetry, duplicate keys, switch and candidate-link mapping "
                            "coverage, reciprocal target mapping, ordered phase coverage, iperf process "
                            "records and reparsed summaries, raw artifact hashes."),
    }, raw


def discover_run_dirs(runs_root):
    runs_root = Path(runs_root)
    if not runs_root.is_dir():
        raise FileNotFoundError(runs_root)
    return sorted(
        path for path in runs_root.iterdir()
        if path.is_dir() and path.name.startswith("physical_") and "_logical_" in path.name
    )


def build_topology_candidate(switch_count, runs_root, output_dir, run_dirs=None):
    topology = LinearTopology(switch_count)
    registry = topology_run_registry(topology.switch_count)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Refusing to overwrite output directory: %s" % output_dir)
    run_dirs = list(run_dirs) if run_dirs is not None else discover_run_dirs(runs_root)
    if not run_dirs:
        raise ValueError("No run directories found under %s" % runs_root)
    admitted, excluded = [], []
    seen_logical, seen_physical = set(), set()
    for run_dir in run_dirs:
        try:
            audit, raw = validate_topology_run(run_dir, topology, registry)
            if audit["logical_experiment_id"] in seen_logical or audit["physical_run_id"] in seen_physical:
                raise ValueError("duplicate logical/physical identity across run directories")
            seen_logical.add(audit["logical_experiment_id"])
            seen_physical.add(audit["physical_run_id"])
            audit["run_dir"] = str(run_dir)
            admitted.append((audit, raw))
        except (ValueError, KeyError, OSError, TypeError) as exc:
            status = None
            try:
                status = json.loads((Path(run_dir) / "run_metadata.json").read_text(encoding="utf-8")).get("status")
            except Exception:  # noqa: BLE001 - any unreadable metadata is reported as such
                status = "UNREADABLE"
            excluded.append({"run_dir": str(run_dir), "metadata_status": status,
                             "status": "EXCLUDED", "reason": "%s: %s" % (type(exc).__name__, exc)})
    if not admitted:
        raise ValueError("No run passed validation; nothing to build. Exclusions: %s" % excluded)

    # Canonical candidate-link endpoint mapping must agree across admitted runs.
    canonical = None
    for audit, _raw in admitted:
        this = sorted(
            (row["link"], row["switch"], row["openflow_port"], row["interface_name"])
            for row in audit["runtime_port_mapping"] if topology.is_candidate(row["link"])
        )
        if canonical is None:
            canonical = this
        elif this != canonical:
            raise ValueError("Candidate-link endpoint mapping differs between runs; refusing to merge "
                             "(first disagreement in logical %d)" % audit["logical_experiment_id"])

    output_dir.mkdir(parents=True, exist_ok=False)
    combined, manifest = [], []
    for audit, raw in admitted:
        phases = audit["phase_events"]
        _normal, fault, recovery = (_event_wall_time(phases[name], name) for name in PHASES)
        logical_id = audit["logical_experiment_id"]
        for row in raw:
            stamp = datetime.fromisoformat(row["timestamp"])
            phase = "normal" if stamp < fault else "fault" if stamp < recovery else "recovery"
            record = {key: row[key] for key in DATASET_FIELDS[:13]}
            record.update({
                "experiment_id": str(logical_id), "phase": phase,
                "fault_type": "none" if phase == "normal" else "link_failure",
                "fault_location": "none" if phase == "normal" else audit["fault_link"],
            })
            combined.append(record)
        iperf = audit["iperf_validation"]
        manifest.append({
            "experiment_id": logical_id, "physical_run_id": audit["physical_run_id"],
            "switch_count": topology.switch_count, "candidate_count": topology.candidate_count,
            "fault_type": "link_failure", "fault_link": audit["fault_link"],
            "normal_event": phases["normal"], "fault_event": phases["fault"], "recovery_event": phases["recovery"],
            "telemetry_rows": audit["telemetry_rows"], "distinct_timestamps": audit["distinct_timestamps"],
            "median_sample_interval_seconds": audit["median_sample_interval_seconds"],
            "fault_window_10s_timestamps": audit["fault_window_10s_timestamps"],
            "iperf_sender_seconds": iperf["client_observed_duration_seconds"],
            "iperf_sender_mbps": iperf["client_sender_reported_mbps"],
            "iperf_receiver_lost_datagrams": iperf["client_receiver_lost_datagrams"],
            "iperf_receiver_total_datagrams": iperf["client_receiver_total_datagrams"],
            "rx_counters_all_zero": audit["rx_counters_all_zero"],
            "status": "ADMITTED", "admission_basis": audit["admission_basis"], "run_dir": audit["run_dir"],
        })
    keys, labels = set(), {}
    phase_counts, class_counts = Counter(), Counter()
    for number, row in enumerate(combined, start=2):
        stamp = datetime.fromisoformat(row["timestamp"])
        exp_id = int(row["experiment_id"])
        _finite_nonnegative(row, NUMERIC_FIELDS, number)
        key = (exp_id, stamp.isoformat(), row["switch"], row["port"])
        if key in keys:
            raise ValueError("Duplicate combined observation key at row %d" % number)
        keys.add(key)
        phase_counts[row["phase"]] += 1
        if row["phase"] == "fault":
            labels.setdefault(exp_id, set()).add(row["fault_location"])
            class_counts[row["fault_location"]] += 1
    if set(labels) != seen_logical or any(len(v) != 1 or "none" in v for v in labels.values()):
        raise ValueError("Combined dataset has missing or inconsistent per-run link labels")

    dataset_path = output_dir / "candidate_dataset.csv"
    with dataset_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATASET_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(combined)
    with (output_dir / "experiment_manifest.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(manifest, key=lambda row: row["experiment_id"]))
    with (output_dir / "link_port_mapping.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("link", "switch", "openflow_port", "interface_name"),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows({"link": a, "switch": b, "openflow_port": c, "interface_name": d} for a, b, c, d in canonical)
    with (output_dir / "exclusion_report.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("run_dir", "metadata_status", "status", "reason"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(excluded)
    dataset_hash = sha256(dataset_path)
    experiment_labels = {str(k): next(iter(v)) for k, v in sorted(labels.items())}
    provenance = {
        "validation": "PASS", "dataset_sha256": dataset_hash, "dataset_path": str(dataset_path),
        "schema": list(DATASET_FIELDS), "topology": topology.to_metadata(),
        "candidate_links": list(topology.candidate_links),
        "admitted_logical_experiments": sorted(seen_logical),
        "admitted_count": len(seen_logical), "target_count": 25,
        "excluded_runs": excluded, "run_audits": [audit for audit, _raw in admitted],
        "experiment_labels": experiment_labels,
        "label_support": dict(sorted(class_counts.items())),
        "experiments_per_link": dict(Counter(experiment_labels.values())),
        "rows": len(combined), "phase_counts": dict(phase_counts),
        "duplicate_key_check": "PASS",
        "time_policy": "Raw timestamp strings retained. Phase CSV stores VM local offset; the collector stores naive VM-local wall time; phase assignment compares local wall-clock values. Fault and recovery are inclusive at their events.",
        "task_scope": "Conditional fault-window localization may use the annotated fault phase to select windows. This dataset alone does not establish online detection.",
        "collection_note": "All runs use the frozen 6 Mbps UDP profile with 20/20/20 s phases and a single 10 Mbps/5 ms bottleneck on the middle candidate link. Runs were sequential on one Mininet/OVS VM.",
        "software": {"python": sys.version, "builder": Path(__file__).name},
    }
    with (output_dir / "provenance.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(provenance, stream, indent=2, sort_keys=True, default=str)
        stream.write("\n")
    return {"dataset": str(dataset_path), "rows": len(combined), "logical_experiments": len(seen_logical),
            "excluded": len(excluded), "sha256": dataset_hash, "output_dir": str(output_dir),
            "experiments_per_link": provenance["experiments_per_link"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switches", type=int, required=True)
    parser.add_argument("--runs-root", type=Path, required=True,
                        help="directory holding physical_<p>_logical_<l> raw run directories")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build_topology_candidate(args.switches, args.runs_root, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
