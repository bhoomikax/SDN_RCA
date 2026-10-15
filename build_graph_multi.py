"""Build a topology snapshot dataset without discarding switch-port rows.

Switch node features are sums over all numbered (non-LOCAL) ports at a
timestamp. Host node features are zeros because this telemetry schema contains
no host measurements. Output creation is exclusive; existing graph artifacts
are never overwritten.
"""

import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "master_dataset.csv"
DEFAULT_OUTPUT = ROOT / "graph_dataset_multi_portsum_v1.json"
NODES = ["h1", "s1", "s2", "s3", "s4", "h2"]
EDGES = [["h1", "s1"], ["s1", "s2"], ["s2", "s3"], ["s3", "s4"], ["s4", "h2"]]
FEATURE_COLUMNS = ["rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps"]
REQUIRED_COLUMNS = {
    "experiment_id", "timestamp", "switch", "port", "phase", "fault_type", "fault_location",
    *FEATURE_COLUMNS,
}


def build_snapshots(frame: pd.DataFrame):
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Input missing required columns: {sorted(missing)}")
    data = frame.copy()
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        # Missing metric values are allowed and represented as zero below, but
        # identity, timestamp, and labels are required.
        required_identity = ["experiment_id", "timestamp", "switch", "port", "phase", "fault_type", "fault_location"]
        if data[required_identity].isna().any().any():
            raise ValueError("Input contains missing identity, timestamp, or label values")
    try:
        parsed_timestamps = [datetime.fromisoformat(str(value)) for value in data["timestamp"]]
    except (TypeError, ValueError) as exc:
        raise ValueError("Input contains an invalid timestamp") from exc
    awareness = {stamp.utcoffset() is not None for stamp in parsed_timestamps}
    if len(awareness) > 1:
        raise ValueError("Input mixes timezone-aware and timezone-naive timestamps")
    data["timestamp"] = parsed_timestamps
    data["experiment_id"] = pd.to_numeric(data["experiment_id"], errors="coerce")
    if data["experiment_id"].isna().any() or (data["experiment_id"] % 1 != 0).any():
        raise ValueError("Experiment IDs must be valid integers")
    data["experiment_id"] = data["experiment_id"].astype(int)
    for column in FEATURE_COLUMNS:
        numeric = pd.to_numeric(data[column], errors="coerce")
        malformed = data[column].notna() & numeric.isna()
        if malformed.any():
            raise ValueError(f"Feature {column} contains nonnumeric values")
        data[column] = numeric.fillna(0.0)
        if not np.isfinite(data[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Feature {column} contains non-finite values")

    data["switch"] = data["switch"].astype(str).str.strip().str.lower()
    data["port_text"] = data["port"].astype(str).str.strip().str.lower()
    data = data[data["port_text"] != "local"].copy()
    data["port_number"] = pd.to_numeric(data["port_text"], errors="coerce")
    if data["port_number"].isna().any():
        bad = sorted(data.loc[data["port_number"].isna(), "port_text"].unique().tolist())
        raise ValueError(f"Non-LOCAL ports must be numeric: {bad}")
    unknown_switches = set(data["switch"]) - set(NODES)
    if unknown_switches:
        raise ValueError(f"Switches are outside the configured topology: {sorted(unknown_switches)}")
    key = ["experiment_id", "timestamp", "switch", "port_number"]
    if data.duplicated(key).any():
        raise ValueError("Duplicate experiment/timestamp/switch/port records")

    snapshots = []
    for (experiment_id, timestamp), time_df in data.groupby(["experiment_id", "timestamp"], sort=True):
        for label in ("phase", "fault_type", "fault_location"):
            values = time_df[label].astype(str).str.strip().unique()
            if len(values) != 1:
                raise ValueError(f"Inconsistent {label} at experiment {experiment_id}, {timestamp}")
        node_features = {node: [0.0] * len(FEATURE_COLUMNS) for node in NODES}
        node_port_counts = {node: 0 for node in NODES}
        for switch, switch_df in time_df.groupby("switch", sort=False):
            # Sum all observed numbered switch ports; never select an arbitrary
            # first row (which was usually the all-zero LOCAL port).
            totals = switch_df[FEATURE_COLUMNS].sum(axis=0).astype(float).tolist()
            node_features[switch] = totals
            node_port_counts[switch] = int(len(switch_df))
        snapshots.append({
            "experiment_id": int(experiment_id),
            "timestamp": timestamp.isoformat(sep=" "),
            "nodes": NODES,
            "edges": EDGES,
            "node_features": node_features,
            "node_port_counts": node_port_counts,
            "phase": str(time_df["phase"].iloc[0]),
            "fault_type": str(time_df["fault_type"].iloc[0]),
            "fault_location": str(time_df["fault_location"].iloc[0]),
        })
    if not snapshots:
        raise ValueError("No graph snapshots remain after excluding LOCAL ports")
    return snapshots


def build(input_path: Path, output_path: Path):
    input_path, output_path = Path(input_path), Path(output_path)
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite graph artifact: {output_path}")
    frame = pd.read_csv(input_path)
    snapshots = build_snapshots(frame)
    payload = {
        "schema_version": 2,
        "source_path": str(input_path),
        "source_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "feature_names": FEATURE_COLUMNS,
        "port_aggregation": "sum over all numbered non-LOCAL ports per switch and timestamp",
        "host_feature_policy": "zero-filled; host telemetry is unavailable in the source schema",
        "topology_mapping_confidence": "static configured topology; historical runtime port mappings are unavailable",
        "snapshots": snapshots,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2)
        stream.write("\n")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    payload = build(args.input, args.output)
    print(f"Created {args.output}: {len(payload['snapshots'])} snapshots; source SHA-256 {payload['source_sha256']}")


if __name__ == "__main__":
    main()
