"""Replay saved v3 results or freshly refit one experiment-grouped LOEO fold."""

import argparse
import csv
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "derived_datasets" / "balanced_recollection_20261015_v3" / "candidate_dataset.csv"
DEFAULT_EVAL = ROOT / "evaluations" / "balanced_recollection_v3_loeo_release"
METRICS = ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _measurement_evidence(dataset, experiment_id, train_ids):
    frame = pd.read_csv(dataset)
    frame["experiment_id"] = pd.to_numeric(frame.experiment_id, errors="raise").astype(int)
    frame["timestamp"] = pd.to_datetime(frame.timestamp, format="mixed", errors="raise")
    exp_rows = frame[frame.experiment_id == int(experiment_id)]
    fault = exp_rows[exp_rows.phase == "fault"]
    if fault.empty:
        raise ValueError("Selected experiment has no annotated fault window")
    start = fault.timestamp.min()
    window = fault[fault.timestamp <= start + pd.Timedelta(seconds=10)]
    if window.empty:
        raise ValueError("The selected ten-second oracle fault window has no telemetry")

    training_normal = frame[
        frame.experiment_id.isin(train_ids)
        & (frame.phase == "normal")
        & (frame.port.astype(str) != "LOCAL")
    ]
    if training_normal.empty:
        raise ValueError("LOEO training groups contain no normal telemetry")
    baseline = training_normal.groupby("switch")[list(METRICS)].mean()
    fault_means = window.groupby("switch")[list(METRICS)].mean()
    switch_evidence = {}
    for switch in sorted(set(baseline.index) | set(fault_means.index)):
        baseline_values = baseline.loc[switch] if switch in baseline.index else None
        fault_values = fault_means.loc[switch] if switch in fault_means.index else None
        if baseline_values is None or fault_values is None:
            continue
        delta = fault_values - baseline_values
        switch_evidence[switch] = {
            "training_normal_mean": baseline_values.round(6).to_dict(),
            "fault_window_mean": fault_values.round(6).to_dict(),
            "fault_minus_baseline": delta.round(6).to_dict(),
        }
    return {
        "window_start": start.isoformat(),
        "window_end": window.timestamp.max().isoformat(),
        "telemetry_rows": int(len(window)),
        "switch_evidence": switch_evidence,
    }


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


def fresh_inference(experiment_id, method="rf_baseline", dataset=DEFAULT_DATA):
    dataset = Path(dataset)
    if not dataset.is_file():
        raise FileNotFoundError(f"Validated candidate is missing: {dataset}")
    provenance_path = dataset.parent / "provenance.json"
    if not provenance_path.is_file():
        raise FileNotFoundError(f"Candidate provenance is missing: {provenance_path}")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    dataset_hash = sha256(dataset)
    if provenance.get("dataset_sha256") != dataset_hash:
        raise ValueError("Candidate hash does not match its provenance manifest")

    evaluator_path = ROOT / "evaluate_grouped_rca_generalized.py"
    spec = importlib.util.spec_from_file_location(
        "sdn_rca_fresh_grouped_evaluator", evaluator_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load grouped evaluator: {evaluator_path}")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    with tempfile.TemporaryDirectory(prefix="sdn_rca_fresh_inference_") as temporary:
        output_dir = Path(temporary)
        evaluator.DATA = dataset
        evaluator.RESULTS = output_dir / "grouped_evaluation.csv"
        evaluator.SUMMARY = output_dir / "evaluation_summary.json"
        evaluator.SPLITS = output_dir / "split_assignments.csv"
        evaluator.FEATURES_OUT = output_dir / "fold_feature_policy.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            evaluator.evaluate()

        with evaluator.RESULTS.open(newline="", encoding="utf-8") as stream:
            predictions = [
                row for row in csv.DictReader(stream)
                if int(row["experiment_id"]) == int(experiment_id)
                and row["method"] == method
            ]
        if len(predictions) != 1:
            raise ValueError(
                "Expected one freshly computed LOEO prediction for the selected "
                "experiment and method"
            )
        prediction = predictions[0]
        training_ids = [
            int(value) for value in prediction["train_experiment_ids"].split(";") if value
        ]
        evidence = _measurement_evidence(dataset, experiment_id, training_ids)
        links = [prediction[f"rank{i}_link"] for i in (1, 2, 3)]
        scores = [float(prediction[f"rank{i}_score"]) for i in (1, 2, 3)]
        return {
            "mode": "fresh LOEO inference; model and preprocessing refit from training experiments",
            "task": "conditional fault localization; annotated phase selects the first 10 seconds",
            "dataset_sha256": dataset_hash,
            "experiment_id": int(experiment_id),
            "method": method,
            "training_experiment_ids": training_ids,
            "training_experiment_count": len(training_ids),
            "active_metrics": prediction["active_metrics"],
            "ranking": links,
            "scores": scores,
            "score_kind": (
                "Uncalibrated RF class scores" if method == "rf_baseline"
                else "Uncalibrated topology-ranker utilities"
            ),
            "topology_neighbors": {
                link: [endpoint[0] for endpoint in evaluator.LINK_PORTS[link]]
                for link in links
            },
            "actual_link_retrospective_only": prediction["actual_link"],
            "top1_hit_retrospective_only": prediction["top1_hit"] == "True",
            "top2_hit_retrospective_only": prediction["top2_hit"] == "True",
            "measurement_evidence": evidence,
            "explanation_boundary": (
                "Telemetry deltas are descriptive associations, not model feature "
                "attributions or causal proof. Fault-window selection uses oracle phase labels."
            ),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("saved-replay", "fresh-inference"), default="saved-replay",
    )
    parser.add_argument("--experiment-id", type=int, default=20)
    parser.add_argument("--method", choices=("rf_baseline", "topology_link_ranker"), default="rf_baseline")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--evaluation-dir", type=Path, default=DEFAULT_EVAL)
    args = parser.parse_args(argv)
    if args.mode == "saved-replay":
        result = replay(args.experiment_id, args.method, args.dataset, args.evaluation_dir)
    else:
        result = fresh_inference(args.experiment_id, args.method, args.dataset)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
