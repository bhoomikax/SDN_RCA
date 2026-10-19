"""Build a new candidate from the audited 17-run source plus physical run 23.

Outputs are created in a new directory and never replace existing artifacts.
This builder does not use or modify either historical master dataset.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from experiment_runner_recollection import validate_iperf_completion
from telemetry_pipeline import TELEMETRY_FIELDS


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "run22_milestone_20261014T182846Z" / "inputs" / "candidate_master_dataset.csv"
DEFAULT_MANIFEST = ROOT / "run22_milestone_20261014T182846Z" / "inputs" / "audit_manifest.csv"
DEFAULT_RUN = ROOT / "run23_raw_evidence_physical23_logical3"
DEFAULT_OUTPUT = ROOT / "derived_datasets" / "candidate_validated_through_physical23"
EXPECTED_SOURCE_SHA256 = "e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2"
EXPECTED_MANIFEST_SHA256 = "80f12f94a7fb0dd6b648126d1021993e78616aad0daf2ab7f4c1d423c8e16d7c"
DATASET_FIELDS = (
    "timestamp", "switch", "port", "rx_packets", "rx_bytes", "rx_dropped",
    "tx_packets", "tx_bytes", "tx_dropped", "rx_packet_rate", "tx_packet_rate",
    "rx_throughput_mbps", "tx_throughput_mbps", "experiment_id", "phase",
    "fault_type", "fault_location",
)
MAPPING_FIELDS = ("switch", "openflow_port", "interface_name", "peer_node", "peer_interface", "link")
NUMERIC_FIELDS = (
    "rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes", "tx_dropped",
    "rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps",
)
COUNTER_FIELDS = set(NUMERIC_FIELDS[:6])
PHASES = ("normal", "fault", "recovery")
EXPECTED_SOURCE_IDS = set(range(1, 20)) - {3, 10}
APPROVED_RECOLLECTIONS = {
    21: 10, 23: 3,
    24: 20, 25: 21, 26: 22, 27: 23, 28: 24, 29: 25,
    44: 40,
    45: 41,
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return tuple(reader.fieldnames), list(reader)


def _finite_nonnegative(row, fields, line_number):
    for field in fields:
        try:
            value = float(row[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Missing or malformed {field} at row {line_number}") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"Invalid {field} at row {line_number}: {row[field]!r}")
        if field in COUNTER_FIELDS and not value.is_integer():
            raise ValueError(f"Non-integral counter {field} at row {line_number}")


def _event_wall_time(value, field):
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Malformed {field} timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} timestamp is missing a UTC offset")
    # The collector writes naive VM-local timestamps; compare wall-clock values
    # without rewriting either source's original timestamp string.
    return parsed.replace(tzinfo=None)


def validate_source(source_path, manifest_path):
    source_hash, manifest_hash = sha256(source_path), sha256(manifest_path)
    if source_hash != EXPECTED_SOURCE_SHA256:
        raise ValueError(f"Protected 17-run source hash mismatch: {source_hash}")
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise ValueError(f"Protected audit-manifest hash mismatch: {manifest_hash}")
    fields, rows = read_csv(source_path)
    if fields != DATASET_FIELDS:
        raise ValueError(f"Historical candidate schema mismatch: {fields}")
    if not rows:
        raise ValueError("Historical candidate is empty")
    keys, ids, labels = set(), set(), {}
    for number, row in enumerate(rows, start=2):
        try:
            experiment_id = int(row["experiment_id"])
            timestamp = datetime.fromisoformat(row["timestamp"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed source identity/timestamp at row {number}") from exc
        if experiment_id not in EXPECTED_SOURCE_IDS:
            raise ValueError(f"Unexpected historical experiment ID {experiment_id}")
        if row["phase"] not in PHASES:
            raise ValueError(f"Invalid phase at source row {number}: {row['phase']!r}")
        _finite_nonnegative(row, NUMERIC_FIELDS, number)
        key = (experiment_id, timestamp.isoformat(), row["switch"], row["port"])
        if key in keys:
            raise ValueError(f"Duplicate source observation key at row {number}: {key}")
        keys.add(key)
        ids.add(experiment_id)
        if row["phase"] == "fault":
            labels.setdefault(experiment_id, set()).add(row["fault_location"])
    if ids != EXPECTED_SOURCE_IDS:
        raise ValueError(f"Unexpected source experiment set: {sorted(ids)}")
    if any(len(labels.get(exp, set())) != 1 or "none" in labels[exp] for exp in ids):
        raise ValueError("Each source experiment must have exactly one fault-link label")

    manifest_fields, manifest = read_csv(manifest_path)
    required = {"experiment_id", "included", "decision_reason"}
    if not required.issubset(manifest_fields) or len(manifest) != 19:
        raise ValueError("Historical audit manifest schema/row count mismatch")
    by_id = {}
    for row in manifest:
        try:
            exp_id = int(row["experiment_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Malformed experiment ID in audit manifest") from exc
        if exp_id in by_id or exp_id not in range(1, 20):
            raise ValueError(f"Duplicate or invalid audit-manifest ID: {exp_id}")
        by_id[exp_id] = row
    included = {exp for exp, row in by_id.items() if row["included"].lower() == "true"}
    excluded = {exp for exp, row in by_id.items() if row["included"].lower() != "true"}
    if set(by_id) != set(range(1, 20)) or included != ids or excluded != {3, 10}:
        raise ValueError("Audit manifest does not agree with the audited 17-run candidate")
    return {"rows": len(rows), "ids": sorted(ids), "sha256": source_hash,
            "manifest_sha256": manifest_hash, "manifest_exclusions": {
                str(exp): by_id[exp]["decision_reason"] for exp in sorted(excluded)}}


def validate_run(raw_dir, *, expected_physical_id=23, logical_id=3,
                 expected_link="s3-s4", allow_failed_counter_reaudit=False):
    raw_dir = Path(raw_dir)
    expected_files = ("telemetry.csv", "phase_events.csv", "runtime_port_mapping.csv",
                      "run_metadata.json", "iperf_client.log", "iperf_server.log")
    missing = [name for name in expected_files if not (raw_dir / name).is_file()]
    if missing:
        raise ValueError(f"Run 23 is missing raw artifact(s): {missing}")
    hashes = {name: sha256(raw_dir / name) for name in expected_files}
    metadata = json.loads((raw_dir / "run_metadata.json").read_text(encoding="utf-8"))
    original_status = metadata.get("status")
    forensic_failure = str(metadata.get("failure", ""))
    corrected_counter_reaudit = (
        allow_failed_counter_reaudit
        and original_status == "FAILED_INVALID"
        and forensic_failure.startswith("ValueError: Client sent ")
        and "datagrams but receiver accounted for" in forensic_failure
    )
    if original_status != "COMPLETE" and not corrected_counter_reaudit:
        raise ValueError(f"Run metadata status is not eligible for audit: {original_status}")
    if (metadata.get("physical_run_id"), metadata.get("logical_experiment_id")) != (expected_physical_id, logical_id):
        raise ValueError("Physical/logical run IDs do not match the requested evidence")
    if metadata.get("fault_link") != expected_link:
        raise ValueError("Run metadata has an unexpected fault target")

    telemetry_fields, raw = read_csv(raw_dir / "telemetry.csv")
    if telemetry_fields != TELEMETRY_FIELDS or not raw:
        raise ValueError("Run 23 telemetry schema is invalid or empty")
    if metadata.get("telemetry_rows") is not None and len(raw) != metadata.get("telemetry_rows"):
        raise ValueError("Run 23 metadata row count disagrees with telemetry")
    telemetry_keys, stamps, switches = set(), [], set()
    mapping_keys = set()
    for number, row in enumerate(raw, start=2):
        if row["experiment_id"] != str(expected_physical_id) or row["switch"] not in {"s1", "s2", "s3", "s4"}:
            raise ValueError(f"Invalid physical ID/switch at run telemetry row {number}")
        if not row["port"] or not row["interface_name"]:
            raise ValueError(f"Missing port/interface at run-23 telemetry row {number}")
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
        except ValueError as exc:
            raise ValueError(f"Malformed telemetry timestamp at row {number}") from exc
        _finite_nonnegative(row, NUMERIC_FIELDS, number)
        key = (stamp.isoformat(), row["switch"], row["port"])
        if key in telemetry_keys:
            raise ValueError(f"Duplicate run-23 telemetry key at row {number}")
        telemetry_keys.add(key)
        stamps.append(stamp)
        switches.add(row["switch"])
        if row["port"] != "LOCAL":
            mapping_keys.add((row["switch"], row["port"], row["interface_name"]))
    if switches != {"s1", "s2", "s3", "s4"}:
        raise ValueError(f"Run 23 is missing switch coverage: {sorted(switches)}")

    mapping_fields, mapping = read_csv(raw_dir / "runtime_port_mapping.csv")
    if mapping_fields != MAPPING_FIELDS or not mapping:
        raise ValueError("Runtime port mapping schema is invalid or empty")
    mapping_by_interface = {}
    for row in mapping:
        key = (row["switch"], row["openflow_port"], row["interface_name"])
        if key in mapping_by_interface:
            raise ValueError(f"Duplicate runtime port mapping: {key}")
        mapping_by_interface[key] = row
    if mapping != metadata.get("runtime_switch_port_mapping"):
        raise ValueError("Runtime mapping CSV disagrees with run metadata")
    if mapping_keys != set(mapping_by_interface):
        raise ValueError("Telemetry port/interface coverage disagrees with runtime mapping")
    target = [row for row in mapping if row["link"] == expected_link]
    endpoint_switches = set(expected_link.split("-"))
    if len(target) != 2 or {row["switch"] for row in target} != endpoint_switches:
        raise ValueError(f"Runtime target mapping for {expected_link} is missing, duplicated, or ambiguous")
    pairs = {(row["switch"], row["interface_name"], row["peer_node"], row["peer_interface"])
             for row in target}
    for switch, interface, peer, peer_interface in pairs:
        if not any((other_switch, other_interface, other_peer, other_peer_interface) ==
                   (peer, peer_interface, switch, interface)
                   for other_switch, other_interface, other_peer, other_peer_interface in pairs):
            raise ValueError("Runtime target mapping has contradictory peer endpoints")
    if target != metadata.get("fault_target_runtime_mapping"):
        raise ValueError("Fault target mapping differs from recorded runtime mapping")

    phase_fields, phases = read_csv(raw_dir / "phase_events.csv")
    if set(phase_fields) != {"physical_run_id", "logical_experiment_id", "timestamp", "phase", "fault_type", "fault_location"}:
        raise ValueError("Phase-event schema mismatch")
    if len(phases) != 3 or {row["phase"] for row in phases} != set(PHASES):
        raise ValueError("Phase log must contain exactly normal, fault, and recovery")
    if any((row["physical_run_id"], row["logical_experiment_id"]) !=
           (str(expected_physical_id), str(logical_id)) for row in phases):
        raise ValueError("Phase-log physical/logical IDs are inconsistent")
    event_map = {row["phase"]: row["timestamp"] for row in phases}
    if event_map != metadata.get("phase_events"):
        raise ValueError("Phase CSV events disagree with run metadata")
    normal, fault, recovery = (_event_wall_time(event_map[name], name) for name in PHASES)
    first, last = min(stamps), max(stamps)
    if not (first <= normal < fault < recovery <= last):
        raise ValueError("Phase events are unordered or outside telemetry coverage")
    if phases[1]["fault_type"] != "link_failure" or phases[1]["fault_location"] != expected_link:
        raise ValueError(f"Recorded fault event does not identify link failure {expected_link}")

    iperf = metadata.get("iperf", {})
    processes = iperf.get("processes", {})
    for label in ("client", "server"):
        record = processes.get(label, {})
        if record.get("terminal_outcome") != "exited":
            raise ValueError(f"iperf {label} has no documented natural terminal outcome")
        if not isinstance(record.get("pid"), int) or record["pid"] <= 0:
            raise ValueError(f"iperf {label} PID is missing or invalid")
        if record.get("returncode") != 0:
            raise ValueError(f"iperf {label} return code is not successful")
        try:
            started = datetime.fromisoformat(record["started_at"])
            completed = datetime.fromisoformat(record["completed_at"])
            elapsed = float(record["elapsed_seconds"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"iperf {label} process timing metadata is invalid") from exc
        if completed < started or not math.isfinite(elapsed) or elapsed <= 0:
            raise ValueError(f"iperf {label} process timing is unordered or invalid")
    result = validate_iperf_completion(
        client_returncode=processes.get("client", {}).get("returncode"),
        server_returncode=processes.get("server", {}).get("returncode"),
        client_log=(raw_dir / "iperf_client.log").read_text(encoding="utf-8"),
        server_log=(raw_dir / "iperf_server.log").read_text(encoding="utf-8"),
        requested_duration=iperf.get("requested_duration_seconds"),
        client_elapsed=processes.get("client", {}).get("elapsed_seconds"),
        server_elapsed=processes.get("server", {}).get("elapsed_seconds"),
    )
    if not iperf.get("completion_valid") and not corrected_counter_reaudit:
        raise ValueError("Run 23 iperf completion flag is not valid")
    recorded = iperf.get("summary_validation", {})
    recorded_differences = {}
    for key, value in result.items():
        if key in {"client_elapsed_seconds", "server_elapsed_seconds"}:
            continue
        if key not in recorded:
            continue
        if recorded.get(key) != value:
            recorded_differences[key] = {"metadata": recorded.get(key), "reparsed_logs": value}
    if recorded_differences and not corrected_counter_reaudit:
        key = next(iter(recorded_differences))
        if key not in {"client_receiver_accounted_minus_sender_count",
                       "receiver_statistics_basis", "sequence_accounted_nonlost_datagrams"}:
            raise ValueError(f"iperf metadata disagrees with parsed evidence: {key}")
    return {"original_metadata_status": original_status,
            "forensic_reaudit": "PASS; corrected iperf2 sequence-counter semantics" if corrected_counter_reaudit else "not required",
            "recorded_iperf_summary_differences": recorded_differences,
            "original_failure": forensic_failure or None,
            "source_physical_run_id": expected_physical_id,
            "logical_experiment_id": logical_id,
            "raw_artifact_sha256": hashes, "telemetry_rows": len(raw),
            "distinct_timestamps": len({row["timestamp"] for row in raw}),
            "telemetry_start": min(stamps).isoformat(), "telemetry_end": max(stamps).isoformat(),
            "runtime_port_mapping": mapping, "target_mapping": target,
            "phase_events": event_map, "iperf_validation": result,
            "fault_link": expected_link, "admission_status": "VALID",
            "admission_basis": "Complete independent artifact revalidation, including process records, corrected iperf2 summary semantics, schema, telemetry, phase coverage, and runtime mapping."}, raw


def build_candidate(source_path, manifest_path, raw_dir, output_dir, extra_run_dirs=()):
    source_path, manifest_path, output_dir = map(Path, (source_path, manifest_path, output_dir))
    raw_dirs = [Path(raw_dir), *(Path(path) for path in extra_run_dirs)]
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {output_dir}")
    source_audit = validate_source(source_path, manifest_path)
    run_audits, run_rows = [], []
    seen_physical, seen_logical = set(), set()
    for run_path in raw_dirs:
        run_metadata = json.loads((run_path / "run_metadata.json").read_text(encoding="utf-8"))
        physical_id = int(run_metadata["physical_run_id"])
        logical_id = int(run_metadata["logical_experiment_id"])
        link = str(run_metadata["fault_link"])
        if APPROVED_RECOLLECTIONS.get(physical_id) != logical_id:
            raise ValueError(f"Unapproved recollection identity mapping: {physical_id}->{logical_id}")
        if physical_id in seen_physical or logical_id in seen_logical or logical_id in EXPECTED_SOURCE_IDS:
            raise ValueError("Duplicate physical/logical run in additional evidence")
        seen_physical.add(physical_id)
        seen_logical.add(logical_id)
        audit, raw = validate_run(
            run_path, expected_physical_id=physical_id, logical_id=logical_id,
            expected_link=link, allow_failed_counter_reaudit=True,
        )
        run_audits.append(audit)
        run_rows.append((audit, raw))
    # Reserve the entire output namespace atomically before writing anything.
    output_dir.mkdir(parents=True, exist_ok=False)
    fields, source_rows = read_csv(source_path)
    added = []
    for run_audit, raw_rows in run_rows:
        phases = run_audit["phase_events"]
        _normal, fault, recovery = (_event_wall_time(phases[name], name) for name in PHASES)
        logical_id = run_audit["logical_experiment_id"]
        for row in raw_rows:
            stamp = datetime.fromisoformat(row["timestamp"])
            phase = "normal" if stamp < fault else "fault" if stamp < recovery else "recovery"
            added.append({key: row[key] for key in DATASET_FIELDS[:13]} | {
                "experiment_id": str(logical_id), "phase": phase,
                "fault_type": "none" if phase == "normal" else "link_failure",
                "fault_location": "none" if phase == "normal" else run_audit["fault_link"],
            })
    combined = source_rows + added
    expected_ids = EXPECTED_SOURCE_IDS | seen_logical
    combined_ids = {int(row["experiment_id"]) for row in combined}
    if combined_ids != expected_ids:
        raise ValueError(f"Unexpected combined logical experiment IDs: {sorted(combined_ids)}")
    keys, labels = set(), {}
    phase_counts, class_counts = Counter(), Counter()
    for number, row in enumerate(combined, start=2):
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
            exp_id = int(row["experiment_id"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Malformed combined identity at row {number}") from exc
        _finite_nonnegative(row, NUMERIC_FIELDS, number)
        key = (exp_id, stamp.isoformat(), row["switch"], row["port"])
        if key in keys:
            raise ValueError(f"Duplicate combined observation key at row {number}")
        keys.add(key)
        phase_counts[row["phase"]] += 1
        if row["phase"] == "fault":
            labels.setdefault(exp_id, set()).add(row["fault_location"])
            class_counts[row["fault_location"]] += 1
    if set(labels) != expected_ids or any(len(value) != 1 or "none" in value for value in labels.values()):
        raise ValueError("Combined dataset has missing or inconsistent per-run link labels")

    dataset_path = output_dir / "candidate_dataset.csv"
    with dataset_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATASET_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(combined)
    dataset_hash = sha256(dataset_path)
    provenance = {
        "validation": "PASS", "dataset_sha256": dataset_hash,
        "dataset_path": str(dataset_path), "schema": list(DATASET_FIELDS),
        "input_candidate": {"path": str(source_path), **source_audit},
        "audit_manifest_path": str(manifest_path),
        "recollected_runs": run_audits,
        "run_23": next((item for item in run_audits if item["source_physical_run_id"] == 23), None),
        "physical_to_logical_mapping": {str(item["source_physical_run_id"]): item["logical_experiment_id"]
                                        for item in run_audits},
        "included_logical_experiments": sorted(expected_ids),
        "excluded_historical_experiments": source_audit["manifest_exclusions"],
        "rows": len(combined), "source_rows": len(source_rows),
        "recollected_run_row_counts": {str(run_audit["source_physical_run_id"]): len(raw)
                                        for run_audit, raw in run_rows},
        "phase_counts": dict(phase_counts), "fault_link_rows": dict(class_counts),
        "duplicate_key_check": "PASS",
        "time_policy": "Raw timestamp strings retained. Phase CSV stores VM local offset; the telemetry collector stores naive VM-local wall time. Phase assignment compares these local wall-clock values without rewriting either source. Samples before the normal marker remain normal-condition rows; fault is inclusive at its event and recovery is inclusive at its event.",
        "task_scope": "Conditional fault-window localization may use annotated fault phase to select windows. This dataset alone does not establish online detection.",
        "software": {"python": sys.version, "builder": Path(__file__).name},
    }
    with (output_dir / "provenance.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(provenance, stream, indent=2, sort_keys=True)
        stream.write("\n")
    exclusions = [{"experiment_id": int(exp), "status": "EXCLUDED",
                   "reason": reason} for exp, reason in source_audit["manifest_exclusions"].items()]
    exclusions.extend([
        {"experiment_id": 20, "status": "INVALID", "reason": "Known failed-invalid run; not a candidate input."},
        {"experiment_id": 22, "status": "PROVISIONAL", "reason": "Missing trustworthy process completion evidence; excluded."},
    ])
    with (output_dir / "exclusion_report.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("experiment_id", "status", "reason"), lineterminator="\n")
        writer.writeheader()
        writer.writerows(exclusions)
    return {"dataset": str(dataset_path), "rows": len(combined), "logical_experiments": len(expected_ids),
            "sha256": dataset_hash, "output_dir": str(output_dir)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--extra-run-dir", type=Path, action="append", default=[],
                        help="additional independently validated physical run (repeatable)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(json.dumps(build_candidate(args.source, args.manifest, args.run_dir, args.output_dir,
                                     extra_run_dirs=args.extra_run_dir), indent=2))


if __name__ == "__main__":
    main()
