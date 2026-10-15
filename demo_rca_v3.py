"""Replay a held-out prediction from the saved v3 LOEO results (no inference)."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3" / "candidate_dataset.csv"
DEFAULT_EVAL = ROOT / "evaluations" / "balanced_recollection_v3_loeo_release"
METRICS = ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(experiment_id, method="rf_baseline", dataset=DEFAULT_DATA, evaluation_dir=DEFAULT_EVAL):
    dataset, evaluation_dir = Path(dataset), Path(evaluation_dir)
    manifest = json.loads((evaluation_dir / "demo_artifact_hashes.json").read_text(encoding="utf-8"))
    check = {
        "dataset": dataset,
        "predictions": evaluation_dir / "grouped_evaluation.csv",
        "summary": evaluation_dir / "evaluation_summary.json",
        "splits": evaluation_dir / "split_assignments.csv",
        "feature_policy": evaluation_dir / "fold_feature_policy.csv",
    }
    for name, path in check.items():
        if sha256(path) != manifest["hashes"][name]:
            raise ValueError(f"Saved artifact hash mismatch: {name}")
    with (evaluation_dir / "grouped_evaluation.csv").open(newline="", encoding="utf-8") as stream:
        predictions = [row for row in csv.DictReader(stream)
                       if int(row["experiment_id"]) == int(experiment_id) and row["method"] == method]
    if len(predictions) != 1:
        raise ValueError("Expected exactly one saved LOEO prediction for this experiment and method")
    prediction = predictions[0]
    frame = pd.read_csv(dataset)
    exp_rows = frame[frame.experiment_id.astype(int) == int(experiment_id)].copy()
    fault = exp_rows[exp_rows.phase == "fault"].copy()
    if fault.empty:
        raise ValueError("Selected experiment has no annotated fault window")
    fault["timestamp"] = pd.to_datetime(fault.timestamp, format="mixed", errors="raise")
    start = fault.timestamp.min()
    window = fault[fault.timestamp <= start + pd.Timedelta(seconds=10)]
    if window.empty:
        raise ValueError("The selected ten-second oracle fault window has no telemetry")
    means = window.groupby("switch")[list(METRICS)].mean().round(6).to_dict(orient="index")
    return {
        "mode": "saved-results replay; no training or inference",
        "task": "conditional fault localization; annotated phase selects the first 10 seconds",
        "experiment_id": int(experiment_id), "method": method,
        "window_start": start.isoformat(), "window_end": window.timestamp.max().isoformat(),
        "telemetry_rows": int(len(window)), "switch_feature_means": means,
        "ranking": [prediction[f"rank{i}_link"] for i in (1, 2, 3)],
        "scores": [float(prediction[f"rank{i}_score"]) for i in (1, 2, 3)],
        "actual_link_retrospective_only": prediction["actual_link"],
        "active_metrics": prediction["active_metrics"],
        "score_ties": prediction["score_ties"],
        "confidence_note": "Scores are uncalibrated ranker outputs; no causal or online-detection claim.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-id", type=int, default=20)
    parser.add_argument("--method", choices=("rf_baseline", "topology_link_ranker"), default="rf_baseline")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--evaluation-dir", type=Path, default=DEFAULT_EVAL)
    args = parser.parse_args(argv)
    print(json.dumps(replay(args.experiment_id, args.method, args.dataset, args.evaluation_dir), indent=2))


if __name__ == "__main__":
    main()
