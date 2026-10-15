"""Build a new candidate dataset from the audited candidate plus run 22.

The original candidate, audit manifest, master dataset, and raw VM run are
inputs only. Every output uses exclusive creation and is confined to this
timestamped milestone directory.
"""

import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
INPUTS = ROOT / "inputs"
RAW = INPUTS / "physical_22_logical_3"
CANDIDATE_IN = INPUTS / "candidate_master_dataset.csv"
MANIFEST_IN = INPUTS / "audit_manifest.csv"
CANDIDATE_OUT = ROOT / "candidate_master_dataset.csv"
AUDIT_OUT = ROOT / "audit" / "run22_raw_provenance.json"
PROVENANCE_OUT = ROOT / "candidate_provenance.json"

EXPECTED_CANDIDATE_SHA256 = "e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2"
EXPECTED_MANIFEST_SHA256 = "80f12f94a7fb0dd6b648126d1021993e78616aad0daf2ab7f4c1d423c8e16d7c"
EXPECTED_RAW_HASHES = {
    "iperf_client.log": "83261df41a207b9f7b72f2d137c485c6bbae848ab95b8654470a1ff72d84a17c",
    "iperf_server.log": "27a7bfe3bb806eea8117cefd988245c21cb346cf2c959401b783d9a78cf16597",
    "phase_events.csv": "b0fc142bb7a649c4de91083f7fad74f303e3e269f11be9a37cb346d130f4d8fd",
    "run_metadata.json": "78c1ab1fcdd752831e0c4b90e06cfd9a401e08ace5356d82f919a0d601005216",
    "runtime_port_mapping.csv": "ebfb86680cb1ac992cb4c45dceb70b6b7a9ea1222328991c5fb00e83d8a61dae",
    "telemetry.csv": "ff4961070701316ae476542a6d8424e8cf8cf145e192dfec68debe34c0bb497c",
}
DATASET_COLUMNS = [
    "timestamp", "switch", "port", "rx_packets", "rx_bytes", "rx_dropped",
    "tx_packets", "tx_bytes", "tx_dropped", "rx_packet_rate", "tx_packet_rate",
    "rx_throughput_mbps", "tx_throughput_mbps", "experiment_id", "phase",
    "fault_type", "fault_location",
]
TELEMETRY_COLUMNS = [
    "timestamp", "switch", "port", "rx_packets", "rx_bytes", "rx_dropped",
    "tx_packets", "tx_bytes", "tx_dropped", "rx_packet_rate", "tx_packet_rate",
    "rx_throughput_mbps", "tx_throughput_mbps", "interface_name", "experiment_id",
]
MAPPING_COLUMNS = [
    "switch", "openflow_port", "interface_name", "peer_node", "peer_interface", "link",
]
COUNTERS = ("rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes", "tx_dropped")
NUMERIC = COUNTERS + ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")
EXPECTED_SWITCHES = {"s1", "s2", "s3", "s4"}
EXPECTED_LINK_MAP = [
    {"switch": "s3", "openflow_port": "2", "interface_name": "s3-eth2", "peer_node": "s4", "peer_interface": "s4-eth1", "link": "s3-s4"},
    {"switch": "s4", "openflow_port": "1", "interface_name": "s4-eth1", "peer_node": "s3", "peer_interface": "s3-eth2", "link": "s3-s4"},
]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_new(path, value):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def event_wall_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Phase event lacks UTC offset: {value!r}")
    # Collector CSV timestamps are naive VM-local wall time. Retain their
    # strings and compare them to the event's recorded local wall-clock value.
    return parsed.replace(tzinfo=None)


def audit_raw_run():
    actual_hashes = {name: sha256(RAW / name) for name in EXPECTED_RAW_HASHES}
    if actual_hashes != EXPECTED_RAW_HASHES:
        raise ValueError(f"Run-22 raw hash mismatch: {actual_hashes}")

    metadata = json.loads((RAW / "run_metadata.json").read_text(encoding="utf-8"))
    if (metadata.get("status"), metadata.get("physical_run_id"), metadata.get("logical_experiment_id")) != ("COMPLETE", 22, 3):
        raise ValueError("Run metadata status or physical/logical IDs are invalid")
    if metadata.get("fault_link") != "s3-s4":
        raise ValueError("Run metadata has an unexpected fault target")

    with (RAW / "telemetry.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != TELEMETRY_COLUMNS:
            raise ValueError(f"Unexpected run-22 telemetry schema: {reader.fieldnames}")
        raw_rows = list(reader)
    if not raw_rows or len(raw_rows) != metadata.get("telemetry_rows"):
        raise ValueError("Telemetry row count is empty or disagrees with metadata")
    keys = set()
    times = []
    for line, row in enumerate(raw_rows, start=2):
        if row["switch"] not in EXPECTED_SWITCHES or row["experiment_id"] != "22":
            raise ValueError(f"Invalid switch/physical ID at telemetry line {line}")
        if not row["port"] or not row["interface_name"]:
            raise ValueError(f"Missing port/interface at telemetry line {line}")
        key = (row["timestamp"], row["switch"], row["port"])
        if key in keys:
            raise ValueError(f"Duplicate telemetry key at line {line}: {key}")
        keys.add(key)
        times.append(datetime.fromisoformat(row["timestamp"]))
        for name in NUMERIC:
            value = float(row[name])
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid numeric telemetry at line {line}: {name}")
        for name in COUNTERS:
            if not float(row[name]).is_integer():
                raise ValueError(f"Non-integral counter at line {line}: {name}")
    if {row["switch"] for row in raw_rows} != EXPECTED_SWITCHES:
        raise ValueError("Run-22 telemetry is missing switch coverage")

    with (RAW / "runtime_port_mapping.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != MAPPING_COLUMNS:
            raise ValueError("Runtime port mapping schema mismatch")
        mapping = list(reader)
    if mapping != metadata.get("runtime_switch_port_mapping"):
        raise ValueError("Runtime mapping CSV disagrees with run metadata")
    target = [row for row in mapping if row["link"] == "s3-s4"]
    if target != EXPECTED_LINK_MAP or target != metadata.get("fault_target_runtime_mapping"):
        raise ValueError(f"Runtime target mapping did not match the independently expected mapping: {target}")
    mapping_keys = {(x["switch"], x["openflow_port"], x["interface_name"]) for x in mapping}
    sample_keys = {(x["switch"], x["port"], x["interface_name"]) for x in raw_rows if x["port"] != "LOCAL"}
    if mapping_keys != sample_keys:
        raise ValueError("Telemetry switch/port/interface coverage disagrees with runtime mapping")

    with (RAW / "phase_events.csv").open(newline="", encoding="utf-8") as stream:
        events = list(csv.DictReader(stream))
    if len(events) != 3 or {x["phase"] for x in events} != {"normal", "fault", "recovery"}:
        raise ValueError("Phase CSV must contain exactly normal, fault, and recovery events")
    if any((x["physical_run_id"], x["logical_experiment_id"]) != ("22", "3") for x in events):
        raise ValueError("Phase CSV physical/logical IDs are inconsistent")
    event_map = {x["phase"]: x["timestamp"] for x in events}
    if event_map != metadata.get("phase_events"):
        raise ValueError("Phase CSV events disagree with metadata")
    normal, fault, recovery = (event_wall_time(event_map[x]) for x in ("normal", "fault", "recovery"))
    first, last = min(times), max(times)
    if not (first <= normal < fault < recovery <= last):
        raise ValueError("Run-22 phase events are unordered or outside telemetry coverage")
    logs = {name: (RAW / name).stat().st_size for name in ("iperf_client.log", "iperf_server.log")}
    if not all(size > 0 for size in logs.values()):
        raise ValueError("iperf logs are missing or empty")

    return {
        "result": "PASS",
        "raw_run_directory": "/home/mininet/sdn_project/recollection_runs/physical_22_logical_3",
        "physical_run_id": 22,
        "logical_experiment_id": 3,
        "status": metadata["status"],
        "sha256": actual_hashes,
        "telemetry_rows": len(raw_rows),
        "unique_timestamp_switch_port_keys": len(keys),
        "distinct_timestamps": len({x["timestamp"] for x in raw_rows}),
        "switches": sorted({x["switch"] for x in raw_rows}),
        "runtime_mapping_rows": len(mapping),
        "validated_s3_s4_mapping": target,
        "phase_events": event_map,
        "telemetry_first_wall_time": first.isoformat(),
        "telemetry_last_wall_time": last.isoformat(),
        "iperf_log_bytes": logs,
        "note": "Telemetry timestamps are naive VM-local wall times; event timestamps retain their recorded -07:00 offset. Comparisons use the event's recorded local wall-clock component without altering either source.",
    }


def build_candidate():
    if CANDIDATE_OUT.exists() or AUDIT_OUT.exists() or PROVENANCE_OUT.exists():
        raise FileExistsError("Refusing to overwrite a milestone output")
    if sha256(CANDIDATE_IN) != EXPECTED_CANDIDATE_SHA256:
        raise ValueError("Protected source candidate hash changed")
    if sha256(MANIFEST_IN) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Protected source manifest hash changed")
    raw_audit = audit_raw_run()

    source = pd.read_csv(CANDIDATE_IN)
    if list(source.columns) != DATASET_COLUMNS:
        raise ValueError(f"Source candidate schema mismatch: {list(source.columns)}")
    source["experiment_id"] = pd.to_numeric(source["experiment_id"], errors="raise").astype(int)
    if source.duplicated(["experiment_id", "timestamp", "switch", "port"]).any():
        raise ValueError("Source candidate contains duplicate experiment/time/switch/port rows")
    source_ids = set(source["experiment_id"])

    with MANIFEST_IN.open(newline="", encoding="utf-8") as stream:
        manifest = list(csv.DictReader(stream))
    if len(manifest) != 19 or {int(x["experiment_id"]) for x in manifest} != set(range(1, 20)):
        raise ValueError("Audit manifest does not cover logical IDs 1 through 19 exactly")
    included_ids = {int(x["experiment_id"]) for x in manifest if x["included"] == "True"}
    excluded = {int(x["experiment_id"]): x["decision_reason"] for x in manifest if x["included"] != "True"}
    if included_ids != source_ids or excluded.keys() != {3, 10}:
        raise ValueError("Candidate experiment IDs disagree with the audit manifest")
    if source_ids != set(range(1, 20)) - {3, 10}:
        raise ValueError("Existing candidate is not the expected 17-experiment retained set")
    if len(source) != 11604:
        raise ValueError(f"Existing candidate row count changed: {len(source)}")

    raw = pd.read_csv(RAW / "telemetry.csv")
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="raise")
    raw["experiment_id"] = 3  # physical run 22 maps to logical experiment 3 in this dataset schema
    events = json.loads((RAW / "run_metadata.json").read_text(encoding="utf-8"))["phase_events"]
    normal = pd.Timestamp(event_wall_time(events["normal"]))
    fault = pd.Timestamp(event_wall_time(events["fault"]))
    recovery = pd.Timestamp(event_wall_time(events["recovery"]))
    raw["phase"] = "normal"
    raw.loc[raw["timestamp"] >= fault, "phase"] = "fault"
    raw.loc[raw["timestamp"] >= recovery, "phase"] = "recovery"
    raw["fault_type"] = "none"
    raw["fault_location"] = "none"
    nonnormal = raw["phase"] != "normal"
    raw.loc[nonnormal, "fault_type"] = "link_failure"
    raw.loc[nonnormal, "fault_location"] = "s3-s4"
    # Keep the required pre-normal collector sample as normal-condition data;
    # the runner deliberately waits for it before writing the normal event.
    samples_before_normal_marker = int((raw["timestamp"] < normal).sum())
    added = raw[DATASET_COLUMNS].copy()
    result = pd.concat([source, added], ignore_index=True)
    if list(result.columns) != DATASET_COLUMNS:
        raise AssertionError("Output schema changed during concatenation")
    result["experiment_id"] = pd.to_numeric(result["experiment_id"], errors="raise").astype(int)
    result["timestamp"] = pd.to_datetime(result["timestamp"], errors="raise")
    for col in NUMERIC:
        result[col] = pd.to_numeric(result[col], errors="raise")
        if not result[col].map(math.isfinite).all() or (result[col] < 0).any():
            raise ValueError(f"Invalid output values in {col}")
    if result.duplicated(["experiment_id", "timestamp", "switch", "port"]).any():
        raise ValueError("Combined candidate contains duplicate experiment telemetry rows")
    ids = set(result["experiment_id"].unique())
    expected_ids = set(range(1, 20)) - {10}
    if ids != expected_ids or len(ids) != 18 or len(result) != 12276:
        raise ValueError(f"Unexpected combined candidate size/IDs: {len(result)}, {sorted(ids)}")
    if set(result["phase"]) != {"normal", "fault", "recovery"}:
        raise ValueError("Combined candidate contains unexpected phases")
    labels = result[result["phase"] == "fault"].groupby("experiment_id")["fault_location"].nunique()
    if set(labels.index) != expected_ids or not (labels == 1).all():
        raise ValueError("Every included experiment must have one ground-truth link class")
    locations = result[result["phase"] == "fault"].groupby("experiment_id")["fault_location"].first()
    if locations.loc[3] != "s3-s4":
        raise ValueError("Run 22 ground truth did not resolve to s3-s4")

    raw_audit_path = AUDIT_OUT
    write_json_new(raw_audit_path, raw_audit)
    # Exclusive creation: a prior candidate is never replaced.
    result.to_csv(CANDIDATE_OUT, index=False, mode="x", date_format="%Y-%m-%d %H:%M:%S.%f")
    counts = {str(k): int(v) for k, v in result["phase"].value_counts().to_dict().items()}
    per_exp = {
        str(int(exp_id)): {
            "rows": int(len(group)),
            "phase_counts": {str(k): int(v) for k, v in group["phase"].value_counts().to_dict().items()},
            "fault_link": str(group.loc[group["phase"] == "fault", "fault_location"].iloc[0]),
        }
        for exp_id, group in result.groupby("experiment_id")
    }
    provenance = {
        "validation": "PASS",
        "source_candidate_path": "/home/mininet/sdn_project/phase_reconciliation_20261014/candidate_master_dataset.csv",
        "source_candidate_sha256": EXPECTED_CANDIDATE_SHA256,
        "source_audit_manifest_path": "/home/mininet/sdn_project/phase_reconciliation_20261014/audit_manifest.csv",
        "source_audit_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "raw_run_directory": raw_audit["raw_run_directory"],
        "raw_run_sha256": raw_audit["sha256"],
        "run_mapping": {"physical_run_id": 22, "logical_experiment_id": 3},
        "included_logical_experiments": sorted(expected_ids),
        "excluded_experiments": {str(k): v for k, v in excluded.items()},
        "added_run": {"physical_run_id": 22, "logical_experiment_id": 3, "rows": len(added), "fault_link": "s3-s4"},
        "input_rows": len(source),
        "output_rows": len(result),
        "schema": DATASET_COLUMNS,
        "phase_counts": counts,
        "per_experiment": per_exp,
        "duplicate_key_check": "PASS",
        "timestamp_check": "PASS; run 22 events compared in the recorded VM-local wall-clock zone, with original timestamp strings retained semantically",
        "new_phase_boundary_rule": "normal through samples before the fault event; fault from fault event inclusive to recovery exclusive; recovery from recovery event inclusive",
        "pre_normal_sample_rule": "the valid collector sample before the normal marker is retained as normal-condition data; it is the sample required before the runner can record that marker",
        "run22_samples_before_normal_marker": samples_before_normal_marker,
        "dataset_schema_note": "physical run ID 22 is represented as logical experiment_id 3 to preserve the established dataset schema; the physical/logical mapping is retained here",
        "software": {"python": __import__("sys").version, "pandas": pd.__version__},
        "commands": [
            "python build_candidate.py",
            "python evaluate_grouped_rca.py",
            "python -m unittest -v test_grouped_rca.py",
            "python -m unittest discover -q",
        ],
        "evaluation_protocol": "leave-one-logical-experiment-out, 18 folds; conditional first-10-second fault-window localization; not online detection",
    }
    provenance["output_candidate_sha256"] = sha256(CANDIDATE_OUT)
    write_json_new(PROVENANCE_OUT, provenance)
    print(json.dumps({
        "candidate": str(CANDIDATE_OUT), "rows": len(result), "experiments": len(ids),
        "phase_counts": counts, "candidate_sha256": provenance["output_candidate_sha256"],
        "raw_audit": str(AUDIT_OUT), "provenance": str(PROVENANCE_OUT),
    }, indent=2))


if __name__ == "__main__":
    build_candidate()
