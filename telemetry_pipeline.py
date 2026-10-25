"""Shared paths and input validation for per-experiment telemetry files."""

import re
from pathlib import Path

import numpy as np
import pandas as pd


TELEMETRY_DATA_FIELDS = (
    "timestamp",
    "switch",
    "port",
    "rx_packets",
    "rx_bytes",
    "rx_dropped",
    "tx_packets",
    "tx_bytes",
    "tx_dropped",
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
)
# New collections include the interface name resolved from live OpenFlow port
# descriptions. Historical files remain readable and are marked explicitly.
TELEMETRY_FIELDS = TELEMETRY_DATA_FIELDS + ("interface_name", "experiment_id")

PHASE_FIELDS = (
    "experiment_id",
    "timestamp",
    "phase",
    "fault_type",
    "fault_location",
)

EXPECTED_PHASES = ("normal", "fault", "recovery")
VALID_LINKS = {"s1-s2", "s2-s3", "s3-s4"}
_LINK_PATTERN = re.compile(r"^s(\d+)-s(\d+)$")


def is_adjacent_switch_link(link):
    """True for an inter-switch link name s<i>-s<i+1> of any linear topology."""
    match = _LINK_PATTERN.match(str(link))
    if not match:
        return False
    left, right = int(match.group(1)), int(match.group(2))
    return left >= 1 and right == left + 1


def experiment_paths(output_dir, experiment_id):
    """Return the unique telemetry and phase-log paths for one experiment."""
    experiment_id = int(experiment_id)
    if experiment_id < 1:
        raise ValueError("experiment_id must be a positive integer")
    directory = Path(output_dir)
    return (
        directory / f"telemetry_{experiment_id}.csv",
        directory / f"phases_{experiment_id}.csv",
    )


def collector_command(collector_script, telemetry_path, experiment_id, python_executable):
    """Build the explicit CLI handoff from a runner to the collector."""
    return [
        str(python_executable),
        str(Path(collector_script)),
        "--output",
        str(Path(telemetry_path)),
        "--experiment-id",
        str(int(experiment_id)),
    ]


def _validated_ids(series, path, expected_id):
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    if (
        not np.isfinite(values).all()
        or not np.equal(values % 1, 0).all()
        or set(values.astype(int)) != {int(expected_id)}
    ):
        raise ValueError(
            f"CSV {path} contains experiment IDs inconsistent with "
            f"expected experiment {expected_id}"
        )
    return values.astype(int)


def _read_csv(path, description):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Missing {description}: {path}")
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"Empty {description}: {path}") from exc
    if frame.empty:
        raise ValueError(f"Empty {description}: {path}")
    return frame


def read_telemetry_csv(path, experiment_id):
    """Load and validate one experiment's collector CSV."""
    frame = _read_csv(path, "telemetry CSV")
    missing = sorted(set(TELEMETRY_DATA_FIELDS) - set(frame.columns))
    if missing:
        raise ValueError(f"Telemetry CSV {path} is missing columns: {missing}")

    frame = frame.copy()
    if "interface_name" not in frame.columns:
        frame["interface_name"] = "UNVERIFIED"
    else:
        frame["interface_name"] = (
            frame["interface_name"]
            .fillna("UNVERIFIED")
            .astype(str)
            .str.strip()
            .replace("", "UNVERIFIED")
        )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    if frame["timestamp"].isna().any():
        raise ValueError(f"Telemetry CSV {path} has missing or invalid timestamps")
    for column in ("switch", "port"):
        if frame[column].isna().any():
            raise ValueError(f"Telemetry CSV {path} has missing {column} values")

    metric_fields = [field for field in TELEMETRY_DATA_FIELDS if field not in {
        "timestamp", "switch", "port"
    }]
    for column in metric_fields:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Telemetry CSV {path} has invalid values in {column}")

    if frame.duplicated(["timestamp", "switch", "port"]).any():
        raise ValueError(f"Telemetry CSV {path} has duplicate timestamp/switch/port rows")

    if "experiment_id" in frame.columns:
        frame["experiment_id"] = _validated_ids(
            frame["experiment_id"], path, experiment_id
        )

    return frame


def read_phase_csv(path, experiment_id):
    """Load one experiment's phase log and verify its IDs/events."""
    frame = _read_csv(path, "phase CSV")
    missing = sorted(set(PHASE_FIELDS) - set(frame.columns))
    if missing:
        raise ValueError(f"Phase CSV {path} is missing columns: {missing}")

    frame = frame.copy()
    frame["experiment_id"] = _validated_ids(
        frame["experiment_id"], path, experiment_id
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    if frame["timestamp"].isna().any():
        raise ValueError(f"Phase CSV {path} has missing or invalid timestamps")

    frame["phase"] = frame["phase"].astype(str).str.strip().str.lower()
    if frame["phase"].duplicated().any():
        raise ValueError(f"Phase CSV {path} contains duplicate phase events")
    if set(frame["phase"]) != set(EXPECTED_PHASES):
        raise ValueError(
            f"Phase CSV {path} must contain exactly {list(EXPECTED_PHASES)} events"
        )

    fault_locations = frame.loc[
        frame["phase"].isin(["fault", "recovery"]), "fault_location"
    ].astype(str).str.strip().str.lower()
    if len(fault_locations) != 2 or fault_locations.nunique() != 1:
        raise ValueError(f"Phase CSV {path} has inconsistent fault locations")
    if not is_adjacent_switch_link(fault_locations.iloc[0]):
        raise ValueError(f"Phase CSV {path} has an unknown fault link")
    return frame
