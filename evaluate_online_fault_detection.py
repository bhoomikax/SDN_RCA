"""Evaluate a causal, phase-blind anomaly detector with grouped LOEO.

Training-normal rows fit feature means/scales and a 99th-percentile threshold.
For held-out runs, each timestamp is scored using only that timestamp's port
telemetry. Phase annotations are joined only after predictions for evaluation.
"""

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3" / "candidate_dataset.csv"
DEFAULT_OUTPUT = ROOT / "evaluations" / "online_fault_detection_v3_verified"
METRICS = ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")
QUANTILE = 0.99


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fit_training_normal(frame, train_ids):
    normal = frame[frame.experiment_id.isin(train_ids) & (frame.phase == "normal") & (frame.port != "LOCAL")]
    active = [name for name in METRICS if normal[name].nunique(dropna=False) > 1]
    if not active:
        raise ValueError("No varying metrics in training-normal telemetry")
    means = normal[active].mean()
    scales = normal[active].std(ddof=0).replace(0, np.nan)
    active = [name for name in active if np.isfinite(scales[name]) and scales[name] > 0]
    if not active:
        raise ValueError("All training-normal metrics are constant")
    return normal, active, means[active], scales[active]


def score_online_rows(rows, active, means, scales):
    """Score point-in-time rows; no phase, label, or future fields are read."""
    values = rows[list(active)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Online feature stream contains non-finite values")
    scores = np.abs((values - means.to_numpy()) / scales.to_numpy()).mean(axis=1)
    scored = rows[["experiment_id", "timestamp"]].copy()
    scored["port_anomaly_score"] = scores
    return scored.groupby(["experiment_id", "timestamp"], as_index=False).port_anomaly_score.max()


def _alarm_edges(values):
    result, previous = [], False
    for value in values:
        alarm = bool(value)
        result.append(alarm and not previous)
        previous = alarm
    return result


def evaluate(dataset, output_dir):
    dataset, output_dir = Path(dataset), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite online evaluation: {output_dir}")
    frame = pd.read_csv(dataset)
    required = {"experiment_id", "timestamp", "phase", "port", *METRICS}
    if required - set(frame.columns):
        raise ValueError(f"Missing input fields: {sorted(required - set(frame.columns))}")
    frame["experiment_id"] = pd.to_numeric(frame.experiment_id, errors="raise").astype(int)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, format="mixed", errors="raise")
    for name in METRICS:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
        if not np.isfinite(frame[name].to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite telemetry feature: {name}")
    ids = sorted(frame.experiment_id.unique().tolist())
    if len(ids) < 3 or frame.duplicated(["experiment_id", "timestamp", "switch", "port"]).any():
        raise ValueError("Need at least three unique experiments and no duplicate observations")
    predictions, experiment_results, split_records = [], [], []
    for fold, held_out in enumerate(ids, start=1):
        train_ids = [item for item in ids if item != held_out]
        normal, active, means, scales = fit_training_normal(frame, train_ids)
        normal_scored = score_online_rows(normal, active, means, scales)
        threshold = float(normal_scored.port_anomaly_score.quantile(QUANTILE))
        stream = frame[(frame.experiment_id == held_out) & (frame.port != "LOCAL")].copy()
        # Prediction function gets only identity/time and metric columns.
        feature_rows = stream[["experiment_id", "timestamp", *active]].copy()
        online = score_online_rows(feature_rows, active, means, scales).sort_values("timestamp")
        online["alarm"] = online.port_anomaly_score > threshold
        online["alarm_episode"] = _alarm_edges(online.alarm.tolist())

        # Oracle phase annotations are joined only after all scores/alarms exist.
        truth = frame[frame.experiment_id == held_out].groupby("timestamp", as_index=False).phase.agg(
            lambda values: "fault" if (values == "fault").any() else str(values.iloc[0])
        )
        scored = online.merge(truth, on="timestamp", how="left", validate="one_to_one")
        if scored.phase.isna().any():
            raise ValueError(f"Missing retrospective phase annotation for experiment {held_out}")
        fault_rows = scored[scored.phase == "fault"]
        if fault_rows.empty:
            raise ValueError(f"No fault annotation for experiment {held_out}")
        onset = fault_rows.timestamp.min()
        detection = scored[(scored.timestamp >= onset) & (scored.phase == "fault") & scored.alarm]
        detected = not detection.empty
        first_detection = detection.timestamp.min() if detected else pd.NaT
        delay = (first_detection - onset).total_seconds() if detected else None
        false_alarm_count = int((scored.alarm_episode & (scored.phase != "fault")).sum())
        normal_duration_hours = max(
            1.0 / 3600.0,
            (scored.loc[scored.phase != "fault", "timestamp"].max()
             - scored.loc[scored.phase != "fault", "timestamp"].min()).total_seconds() / 3600.0
        ) if (scored.phase != "fault").any() else 1.0 / 3600.0
        experiment_results.append({
            "fold": fold, "experiment_id": held_out, "train_experiment_ids": ";".join(map(str, train_ids)),
            "fault_onset_for_scoring_only": onset.isoformat(),
            "detected_in_fault_window": detected,
            "first_detection_for_scoring_only": first_detection.isoformat() if detected else "",
            "detection_delay_seconds": delay, "false_alarm_episodes_outside_fault": false_alarm_count,
            "observed_nonfault_hours": normal_duration_hours,
            "active_metrics": ";".join(active), "threshold_train_normal_q99": threshold,
            "topology_or_label_inputs": "none; phase joined after predictions",
        })
        split_records.append({"fold": fold, "test_experiment_id": held_out,
                              "train_experiment_ids": ";".join(map(str, train_ids)),
                              "train_count": len(train_ids), "test_count": 1,
                              "active_metrics": ";".join(active), "threshold": threshold})
        scored.insert(0, "fold", fold)
        scored["experiment_id"] = held_out
        predictions.extend(scored.to_dict(orient="records"))

    tp = sum(bool(row["detected_in_fault_window"]) for row in experiment_results)
    fn = len(experiment_results) - tp
    fp = sum(int(row["false_alarm_episodes_outside_fault"]) for row in experiment_results)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    total_nonfault_hours = sum(float(row["observed_nonfault_hours"]) for row in experiment_results)
    delays = [float(row["detection_delay_seconds"]) for row in experiment_results
              if row["detection_delay_seconds"] is not None]
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, records in (("per_experiment.csv", experiment_results),
                          ("per_timestamp_predictions.csv", predictions),
                          ("split_thresholds.csv", split_records)):
        with (output_dir / name).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    summary = {
        "task": "online fault detection; each prediction uses only current timestamp and training-normal fitted statistics",
        "protocol": f"leave-one-logical-experiment-out ({len(ids)} folds)",
        "threshold": f"99th percentile of training-normal timestamp maximum anomaly scores; fixed, not tuned on held-out data",
        "ground_truth_use": "training phase labels select training-normal fit rows; held-out phase annotations are joined only after prediction to score onset, recall and false alarms",
        "experiments": len(ids), "detected_experiments": tp, "missed_experiments": fn,
        "false_alarm_episodes": fp, "event_precision": precision, "event_recall": recall,
        "event_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_alarm_episodes_per_nonfault_hour": fp / total_nonfault_hours if total_nonfault_hours else None,
        "median_detection_delay_seconds": float(np.median(delays)) if delays else None,
        "mean_detection_delay_seconds": float(np.mean(delays)) if delays else None,
        "candidate_sha256": sha256(dataset), "evaluator_sha256": sha256(__file__),
        "python": sys.version,
        "limitations": ["one controlled topology and 25 runs", "phase annotations are evaluation oracle only",
                         "threshold is a simple train-normal anomaly rule", "no causal link localization is produced"],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(args.dataset, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
