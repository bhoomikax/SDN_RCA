"""Validate and merge per-experiment telemetry without replacing prior data."""

import argparse
from pathlib import Path

import pandas as pd

from telemetry_pipeline import experiment_paths, read_phase_csv, read_telemetry_csv


PROJECT_DIR = Path(__file__).resolve().parent
INPUT_DIR = PROJECT_DIR / "experiments"
OUTPUT = PROJECT_DIR / "master_dataset.csv"
EXPERIMENT_IDS = tuple(range(1, 20))


def build_master_dataset(input_dir=INPUT_DIR, experiment_ids=EXPERIMENT_IDS):
    """Read validated per-experiment files and apply the existing phase rules."""
    experiment_ids = tuple(map(int, experiment_ids))
    if not experiment_ids or any(experiment_id < 1 for experiment_id in experiment_ids):
        raise ValueError("experiment_ids must contain positive IDs")
    if len(set(experiment_ids)) != len(experiment_ids):
        raise ValueError("experiment_ids contains duplicates")
    all_data = []
    for experiment_id in experiment_ids:
        telemetry_path, phase_path = experiment_paths(input_dir, experiment_id)
        telemetry = read_telemetry_csv(telemetry_path, experiment_id)
        phases = read_phase_csv(phase_path, experiment_id)

        telemetry_start = telemetry["timestamp"].min()
        telemetry_end = telemetry["timestamp"].max()
        outside_recording = phases.loc[
            (phases["timestamp"] < telemetry_start)
            | (phases["timestamp"] > telemetry_end),
            "phase",
        ].tolist()
        if outside_recording:
            raise ValueError(
                f"Phase timestamps for experiment {experiment_id} fall outside "
                f"its telemetry recording range ({telemetry_start} to "
                f"{telemetry_end}): {outside_recording}"
            )

        # A file is the primary experiment boundary; an optional column, if
        # present, is checked by read_telemetry_csv and normalized here.
        telemetry["experiment_id"] = int(experiment_id)
        start_time = telemetry_start
        elapsed = (telemetry["timestamp"] - start_time).dt.total_seconds()

        # Preserve the existing dataset-building labels and fixed phase times.
        telemetry["phase"] = "normal"
        telemetry.loc[elapsed >= 20, "phase"] = "fault"
        telemetry.loc[elapsed >= 40, "phase"] = "recovery"
        telemetry["fault_type"] = "none"
        telemetry["fault_location"] = "none"

        fault_location = phases.loc[
            phases["phase"] == "fault", "fault_location"
        ].iloc[0]
        nonnormal = telemetry["phase"] != "normal"
        telemetry.loc[nonnormal, "fault_type"] = "link_failure"
        telemetry.loc[nonnormal, "fault_location"] = str(fault_location)
        all_data.append(telemetry)

    if not all_data:
        raise ValueError("No experiment telemetry was supplied")
    master = pd.concat(all_data, ignore_index=True)

    observed_ids = set(pd.to_numeric(master["experiment_id"]).astype(int))
    expected_ids = set(map(int, experiment_ids))
    if observed_ids != expected_ids:
        raise ValueError(
            f"Merged experiment IDs {sorted(observed_ids)} do not match "
            f"expected IDs {sorted(expected_ids)}"
        )
    if master.duplicated(["experiment_id", "timestamp", "switch", "port"]).any():
        raise ValueError("Merged dataset contains duplicate experiment telemetry rows")

    return master.sort_values(
        ["experiment_id", "timestamp"]
    ).reset_index(drop=True)


def write_master_dataset(master, output_path):
    """Write a new merged CSV, refusing to replace any existing file."""
    output_path = Path(output_path)
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(output_path, index=False, mode="x")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    if args.output.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing dataset: {args.output}. "
            "Choose a new --output path to preserve current evidence."
        )
    master = build_master_dataset(args.input_dir)
    write_master_dataset(master, args.output)

    print("MASTER DATASET CREATED")
    print("----------------------")
    print("Rows:", len(master))
    print("Experiments:", master["experiment_id"].nunique())
    print("Phase counts:")
    print(master["phase"].value_counts())
    print("Fault locations:")
    print(master["fault_location"].value_counts())
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
