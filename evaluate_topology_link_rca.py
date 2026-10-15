"""Compare the existing RF link classifier with a topology-aware link ranker.

This evaluator reads master_dataset.csv and writes a new results CSV only. It
does not modify datasets, model checkpoints, or existing result files.
"""

from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


INPUT = Path("master_dataset.csv")
OUTPUT = Path("topology_link_rca_results.csv")

LABELS = ["s1-s2", "s2-s3", "s3-s4"]
SWITCHES = ["s1", "s2", "s3", "s4"]
LINKS = {
    "s1-s2": ("s1", "s2"),
    "s2-s3": ("s2", "s3"),
    "s3-s4": ("s3", "s4"),
}

# These are OpenFlow port IDs implied by the supplied Mininet net.addLink()
# order: h1-s1, s1-s2, s2-s3, s3-s4, s4-h2. The collector stores the port ID
# from ovs-ofctl, not the Mininet interface name. Runtime OVS ofports are not
# recorded in master_dataset.csv, so the resulting interface association is a
# setup-derived proxy and must not be described as live-verified evidence.
LINK_PORTS = {
    "s1-s2": (("s1", "2"), ("s2", "1")),
    "s2-s3": (("s2", "2"), ("s3", "1")),
    "s3-s4": (("s3", "2"), ("s4", "1")),
}
PORT_TO_INTERFACE = {
    ("s1", "1"): "h1-s1",
    ("s1", "2"): "s1-s2",
    ("s2", "1"): "s1-s2",
    ("s2", "2"): "s2-s3",
    ("s3", "1"): "s2-s3",
    ("s3", "2"): "s3-s4",
    ("s4", "1"): "s3-s4",
    ("s4", "2"): "s4-h2",
}

METRICS = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
]
RF_FEATURES = ["mean_anomaly", "max_anomaly", "persistence", "first_anomaly"]
EARLY_SECONDS = 10.0
NORMAL_THRESHOLD_QUANTILE = 0.95
Z_SCORE_CLIP = 10.0
EXPECTED_TRAIN_IDS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 17, 19}
EXPECTED_TEST_IDS = {10, 11, 12, 15, 16, 18}

REQUIRED_COLUMNS = {
    "timestamp",
    "switch",
    "port",
    "experiment_id",
    "phase",
    "fault_location",
    *METRICS,
}
FORBIDDEN_PREDICTOR_COLUMNS = {
    "experiment_id",
    "fault_location",
    "fault_type",
    "phase",
    "timestamp",
    "switch",
    "port",
}


def normalize_port(value):
    text = str(value).strip()
    if text.upper() == "LOCAL":
        return "LOCAL"
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"Unrecognized port value: {value!r}") from exc
    if not np.isfinite(number) or not number.is_integer():
        raise ValueError(f"Invalid OpenFlow port value: {value!r}")
    return str(int(number))


def load_and_validate():
    if not INPUT.is_file():
        raise FileNotFoundError(f"Required dataset not found: {INPUT}")
    if OUTPUT.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing output: {OUTPUT}"
        )

    frame = pd.read_csv(INPUT)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    if frame.empty:
        raise ValueError("Dataset contains no rows")

    frame = frame.copy()
    # The audited historical CSVs use a space separator while raw Mininet
    # telemetry uses ISO's ``T`` separator. Parse each ISO timestamp
    # independently so newer strict format inference does not reject a valid
    # mixed-format, timezone-naive column.
    try:
        parsed_timestamps = [
            datetime.fromisoformat(str(value)) for value in frame["timestamp"]
        ]
    except (TypeError, ValueError) as exc:
        raise ValueError("Dataset contains missing or invalid timestamps") from exc
    frame["timestamp"] = pd.Series(parsed_timestamps, index=frame.index)
    if frame["timestamp"].isna().any():
        raise ValueError("Dataset contains missing or invalid timestamps")

    for column in METRICS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        values = frame[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"Dataset contains invalid values in {column}")

    for column in ["experiment_id", "switch", "phase", "fault_location"]:
        if frame[column].isna().any():
            raise ValueError(f"Dataset contains missing values in {column}")

    frame["experiment_id"] = pd.to_numeric(
        frame["experiment_id"], errors="raise"
    ).astype(int)
    frame["switch"] = frame["switch"].astype(str).str.strip()
    frame["port"] = frame["port"].map(normalize_port)
    frame["phase"] = frame["phase"].astype(str).str.strip().str.lower()
    frame["fault_location"] = (
        frame["fault_location"].astype(str).str.strip().str.lower()
    )

    bad_switches = sorted(set(frame["switch"]) - set(SWITCHES))
    if bad_switches:
        raise ValueError(f"Unexpected switch values: {bad_switches}")
    bad_phases = sorted(set(frame["phase"]) - {"normal", "fault", "recovery"})
    if bad_phases:
        raise ValueError(f"Unexpected phase values: {bad_phases}")

    observed_ports = set(frame["port"])
    if not {"1", "2", "LOCAL"}.issubset(observed_ports):
        raise ValueError(
            "Expected OpenFlow ports 1, 2, and LOCAL; observed "
            f"{sorted(observed_ports)}"
        )
    unexpected_ports = observed_ports - {"1", "2", "LOCAL"}
    if unexpected_ports:
        raise ValueError(f"Unexpected OpenFlow port values: {unexpected_ports}")

    # Check every mapped physical port is represented in each experiment.
    all_ids = set(frame["experiment_id"].unique())
    for exp_id in all_ids:
        present = set(
            zip(
                frame.loc[frame["experiment_id"] == exp_id, "switch"],
                frame.loc[frame["experiment_id"] == exp_id, "port"],
            )
        )
        missing_ports = sorted(set(PORT_TO_INTERFACE) - present)
        if missing_ports:
            raise ValueError(
                f"Experiment {exp_id} is missing mapped physical ports: "
                f"{missing_ports}"
            )

    fault_rows = frame[frame["phase"] == "fault"]
    label_counts = fault_rows.groupby("experiment_id")["fault_location"].nunique()
    inconsistent = label_counts[label_counts != 1]
    if not inconsistent.empty:
        raise ValueError(
            "Each experiment must have exactly one fault link; inconsistent "
            f"experiment IDs: {inconsistent.index.tolist()}"
        )

    labels = fault_rows.groupby("experiment_id")["fault_location"].first()
    labels = labels[labels.isin(LABELS)]
    if set(labels.unique()) != set(LABELS):
        raise ValueError(
            f"Expected all three link labels {LABELS}; got "
            f"{sorted(labels.unique())}"
        )

    # The label is retained separately for stratification/evaluation and is
    # removed from all sensor feature frames before scoring.
    sensor_columns = [
        "experiment_id", "timestamp", "switch", "port", "phase", *METRICS
    ]
    sensor = frame[sensor_columns].copy()
    predictor_columns = set(sensor_columns) - {
        "experiment_id", "timestamp", "switch", "port", "phase"
    }
    if predictor_columns & FORBIDDEN_PREDICTOR_COLUMNS:
        raise AssertionError("Forbidden metadata entered the sensor predictors")

    # One row per experiment/timestamp/switch/port. This also makes duplicate
    # observations explicit and prevents row ordering from selecting a port.
    sensor = (
        sensor.groupby(
            ["experiment_id", "timestamp", "switch", "port", "phase"],
            as_index=False,
        )[METRICS]
        .mean()
    )

    return frame, sensor, labels


def make_split(labels):
    ids = labels.index.to_numpy()
    values = labels.to_numpy()
    train_ids, test_ids = train_test_split(
        ids,
        test_size=0.30,
        random_state=42,
        stratify=values,
    )
    train_ids, test_ids = set(map(int, train_ids)), set(map(int, test_ids))
    if train_ids & test_ids:
        raise AssertionError("Experiment leakage: train and test IDs overlap")
    if train_ids != EXPECTED_TRAIN_IDS or test_ids != EXPECTED_TEST_IDS:
        raise ValueError(
            "Dataset no longer reproduces the audited 13/6 split. "
            f"Train={sorted(train_ids)}, test={sorted(test_ids)}"
        )
    return train_ids, test_ids


def baseline_for_rf(sensor, train_ids):
    normal = sensor[
        sensor["experiment_id"].isin(train_ids)
        & (sensor["phase"] == "normal")
    ]
    means = normal.groupby("switch")[METRICS].mean()
    stds = normal.groupby("switch")[METRICS].std()
    stds = stds.fillna(0.0001).clip(lower=0.0001)
    if set(SWITCHES) - set(means.index):
        raise ValueError("Missing switch normal baselines for RF features")
    return means, stds


def make_rf_features(sensor, means, stds, experiment_ids):
    result = {}
    for exp_id, exp in sensor.groupby("experiment_id"):
        if exp_id not in experiment_ids:
            continue
        fault = exp[exp["phase"] == "fault"]
        if fault.empty:
            continue
        start = fault["timestamp"].min()
        early = fault[
            fault["timestamp"] <= start + pd.Timedelta(seconds=EARLY_SECONDS)
        ]
        by_switch = {}
        for switch in SWITCHES:
            data = early[early["switch"] == switch]
            if data.empty:
                break
            z = (
                (data[METRICS] - means.loc[switch, METRICS]).abs()
                / stds.loc[switch, METRICS]
            )
            scores = z.mean(axis=1).to_numpy(dtype=float)
            times = (data["timestamp"] - start).dt.total_seconds().to_numpy()
            anomalous = np.flatnonzero(scores > 1.0)
            first = float(times[anomalous[0]]) if len(anomalous) else 999.0
            by_switch[switch] = [
                float(scores.mean()),
                float(scores.max()),
                float(np.mean(scores > 1.0)),
                first,
            ]
        if len(by_switch) != len(SWITCHES):
            continue
        vector = np.concatenate(
            [np.asarray(by_switch[switch], dtype=float) for switch in SWITCHES]
        )
        result[int(exp_id)] = vector

    if set(map(int, experiment_ids)) - set(result):
        missing = sorted(set(map(int, experiment_ids)) - set(result))
        raise ValueError(f"RF feature extraction missed experiments: {missing}")
    return result


def active_port_metrics(sensor, train_ids):
    normal = sensor[
        sensor["experiment_id"].isin(train_ids)
        & (sensor["phase"] == "normal")
        & (sensor["port"] != "LOCAL")
    ]
    if normal.empty:
        raise ValueError("No training normal physical-port telemetry")
    active = [column for column in METRICS if normal[column].nunique() > 1]
    constant = [column for column in METRICS if column not in active]
    if not active:
        raise ValueError("All port telemetry features are constant in training")
    return normal, active, constant


def fit_port_baseline(normal, active):
    grouped = normal.groupby(["switch", "port"])[active]
    means = grouped.mean()
    stds = grouped.std().fillna(0.0).clip(lower=0.0001)
    required = set(PORT_TO_INTERFACE)
    missing = required - set(means.index)
    if missing:
        raise ValueError(
            f"Training normal data lacks mapped switch/port baselines: "
            f"{sorted(missing)}"
        )
    return means, stds


def score_port_rows(sensor, means, stds, active):
    physical = sensor[sensor["port"] != "LOCAL"].copy()
    score_parts = []
    for key, rows in physical.groupby(["switch", "port"], sort=False):
        if key not in means.index:
            raise ValueError(f"No baseline for observed physical port {key}")
        z = (
            (rows[active] - means.loc[key, active]).abs()
            / stds.loc[key, active]
        ).clip(upper=Z_SCORE_CLIP)
        part = rows[["experiment_id", "timestamp", "switch", "port", "phase"]].copy()
        part["anomaly_score"] = z.mean(axis=1).to_numpy(dtype=float)
        score_parts.append(part)
    if not score_parts:
        raise ValueError("No physical-port anomaly rows could be scored")
    scored = pd.concat(score_parts, ignore_index=True)
    if not np.isfinite(scored["anomaly_score"].to_numpy()).all():
        raise ValueError("Invalid values produced in port anomaly scores")
    return scored


def candidate_evidence(exp_scores, link, endpoints, threshold):
    endpoint_values = []
    onset_times = []
    for switch, port in endpoints:
        rows = exp_scores[
            (exp_scores["switch"] == switch) & (exp_scores["port"] == port)
        ]
        if rows.empty:
            raise ValueError(f"Missing link endpoint telemetry for {link}: {(switch, port)}")
        values = rows["anomaly_score"].to_numpy(dtype=float)
        endpoint_values.append(float(values.mean()))
        anomalous = rows[rows["anomaly_score"] > threshold]
        if anomalous.empty:
            onset_times.append(None)
        else:
            onset_times.append(
                float(
                    (anomalous["timestamp"].min() - exp_scores["fault_start"].iloc[0])
                    .total_seconds()
                )
            )

    # A link anomaly proxy requires both mapped endpoint ports to be unusual.
    joint = min(endpoint_values)
    imbalance = abs(endpoint_values[0] - endpoint_values[1])
    if all(value is not None for value in onset_times):
        pair_onset = max(onset_times)  # both endpoints have crossed threshold
    else:
        pair_onset = 999.0

    other_switches = set(SWITCHES) - {endpoints[0][0], endpoints[1][0]}
    remote_onsets = []
    for switch in other_switches:
        rows = exp_scores[exp_scores["switch"] == switch]
        anomalous = rows[rows["anomaly_score"] > threshold]
        remote_onsets.append(
            float(
                (anomalous["timestamp"].min() - exp_scores["fault_start"].iloc[0])
                .total_seconds()
            )
            if not anomalous.empty
            else EARLY_SECONDS + 1.0
        )
    remote_onset = min(remote_onsets) if remote_onsets else EARLY_SECONDS + 1.0
    propagation_margin = (
        remote_onset - pair_onset if pair_onset < 999.0 else -EARLY_SECONDS
    )

    return {
        "link_anomaly": joint,
        "endpoint_mean_anomaly": float(np.mean(endpoint_values)),
        "endpoint_imbalance": imbalance,
        "pair_onset_seconds": pair_onset,
        "remote_onset_seconds": remote_onset,
        "propagation_margin_seconds": propagation_margin,
    }


def topology_rank_for_experiment(scored, exp_id, threshold):
    exp = scored[
        (scored["experiment_id"] == exp_id) & (scored["phase"] == "fault")
    ].copy()
    if exp.empty:
        raise ValueError(f"No fault-phase anomaly data for test experiment {exp_id}")
    fault_start = exp["timestamp"].min()
    exp = exp[
        exp["timestamp"] <= fault_start + pd.Timedelta(seconds=EARLY_SECONDS)
    ].copy()
    if exp.empty:
        raise ValueError(f"No early fault telemetry for experiment {exp_id}")
    exp["fault_start"] = fault_start

    evidence = {
        link: candidate_evidence(exp, link, LINK_PORTS[link], threshold)
        for link in LABELS
    }
    table = pd.DataFrame.from_dict(evidence, orient="index")
    table.index.name = "candidate_link"

    # Equal-weight rank aggregation is fixed in advance and is not tuned on
    # held-out labels. Topology contributes through paired endpoint ports and
    # the timing margin between both endpoints and the other two switches.
    rank_specs = [
        ("link_anomaly", False),
        ("endpoint_imbalance", True),
        ("pair_onset_seconds", True),
        ("propagation_margin_seconds", False),
    ]
    utilities = []
    for column, ascending in rank_specs:
        ranks = table[column].rank(method="average", ascending=ascending)
        utility = (len(table) + 1.0 - ranks) / len(table)
        utilities.append(utility)
    table["rank_score"] = pd.concat(utilities, axis=1).mean(axis=1)
    table = table.sort_values(
        ["rank_score", "link_anomaly", "endpoint_mean_anomaly"],
        ascending=[False, False, False],
        kind="mergesort",
    )
    return table


def topk_metrics(actuals, rankings):
    actuals = list(actuals)
    rankings = list(rankings)
    n = len(actuals)
    if not n:
        raise ValueError("Cannot compute metrics on an empty test set")
    return {
        "support": n,
        "top1_accuracy": float(np.mean([a in r[:1] for a, r in zip(actuals, rankings)])),
        "top2_accuracy": float(np.mean([a in r[:2] for a, r in zip(actuals, rankings)])),
        "top3_accuracy": float(np.mean([a in r[:3] for a, r in zip(actuals, rankings)])),
    }


def make_report_rows(method_results, labels):
    rows = []
    for method, records in method_results.items():
        actuals = [record["actual"] for record in records]
        rankings = [record["ranking"] for record in records]
        overall = topk_metrics(actuals, rankings)
        for record in records:
            ranking = record["ranking"]
            rank_scores = record["scores"]
            rows.append({
                "record_type": "experiment",
                "method": method,
                "experiment_id": record["experiment_id"],
                "actual_link": record["actual"],
                "predicted_link": ranking[0],
                "rank1_link": ranking[0],
                "rank2_link": ranking[1],
                "rank3_link": ranking[2],
                "rank1_score": rank_scores[ranking[0]],
                "rank2_score": rank_scores[ranking[1]],
                "rank3_score": rank_scores[ranking[2]],
                "top1_hit": record["actual"] in ranking[:1],
                "top2_hit": record["actual"] in ranking[:2],
                "top3_hit": record["actual"] in ranking[:3],
                "class_label": "",
                "class_support": "",
                "class_precision": "",
                "class_top1_recall": "",
                "class_f1": "",
                "class_top2_recall": "",
                "class_top3_recall": "",
                "test_support": overall["support"],
                "top1_accuracy": overall["top1_accuracy"],
                "top2_accuracy": overall["top2_accuracy"],
                "top3_accuracy": overall["top3_accuracy"],
            })

        predicted = [ranking[0] for ranking in rankings]
        for label in LABELS:
            tp = sum(a == label and p == label for a, p in zip(actuals, predicted))
            fp = sum(a != label and p == label for a, p in zip(actuals, predicted))
            support = sum(a == label for a in actuals)
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / support if support else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if precision + recall
                else 0.0
            )
            class_records = [r for r in records if r["actual"] == label]
            rows.append({
                "record_type": "class_metric",
                "method": method,
                "experiment_id": "",
                "actual_link": "",
                "predicted_link": "",
                "rank1_link": "",
                "rank2_link": "",
                "rank3_link": "",
                "rank1_score": "",
                "rank2_score": "",
                "rank3_score": "",
                "top1_hit": "",
                "top2_hit": "",
                "top3_hit": "",
                "class_label": label,
                "class_support": support,
                "class_precision": precision,
                "class_top1_recall": recall,
                "class_f1": f1,
                "class_top2_recall": float(np.mean([label in r["ranking"][:2] for r in class_records])) if support else 0.0,
                "class_top3_recall": float(np.mean([label in r["ranking"][:3] for r in class_records])) if support else 0.0,
                "test_support": overall["support"],
                "top1_accuracy": overall["top1_accuracy"],
                "top2_accuracy": overall["top2_accuracy"],
                "top3_accuracy": overall["top3_accuracy"],
            })
        rows.append({
            "record_type": "overall_metric",
            "method": method,
            "experiment_id": "",
            "actual_link": "",
            "predicted_link": "",
            "rank1_link": "",
            "rank2_link": "",
            "rank3_link": "",
            "rank1_score": "",
            "rank2_score": "",
            "rank3_score": "",
            "top1_hit": "",
            "top2_hit": "",
            "top3_hit": "",
            "class_label": "",
            "class_support": "",
            "class_precision": "",
            "class_top1_recall": "",
            "class_f1": "",
            "class_top2_recall": "",
            "class_top3_recall": "",
            "test_support": overall["support"],
            "top1_accuracy": overall["top1_accuracy"],
            "top2_accuracy": overall["top2_accuracy"],
            "top3_accuracy": overall["top3_accuracy"],
        })
    return rows


def main():
    frame, sensor, labels = load_and_validate()
    train_ids, test_ids = make_split(labels)
    train_labels = labels.loc[sorted(train_ids)]
    test_labels = labels.loc[sorted(test_ids)]
    if set(train_labels.unique()) != set(LABELS) or set(test_labels.unique()) != set(LABELS):
        raise ValueError("Every link class must appear in both train and test")

    # Existing Random Forest baseline feature extraction and fit. Only the
    # training experiments and their normal rows fit the baseline and model.
    # Match train_rca.py's switch/timestamp aggregation before fitting its
    # normal baseline. The port-level frame is reserved for the link ranker.
    rf_sensor = (
        sensor.groupby(
            ["experiment_id", "timestamp", "switch", "phase"],
            as_index=False,
        )[METRICS]
        .mean()
    )
    rf_means, rf_stds = baseline_for_rf(rf_sensor, train_ids)
    rf_features = make_rf_features(
        rf_sensor, rf_means, rf_stds, set(labels.index.astype(int))
    )
    X_train = np.vstack([rf_features[eid] for eid in sorted(train_ids)])
    y_train = labels.loc[sorted(train_ids)].to_numpy()
    X_test = np.vstack([rf_features[eid] for eid in sorted(test_ids)])
    y_test = labels.loc[sorted(test_ids)].to_numpy()
    if X_train.shape[1] != len(SWITCHES) * len(RF_FEATURES):
        raise AssertionError("Unexpected RF feature vector width")
    if FORBIDDEN_PREDICTOR_COLUMNS & set(RF_FEATURES):
        raise AssertionError("RF model predictors contain forbidden metadata")

    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        random_state=42,
        class_weight="balanced",
    )
    rf.fit(X_train, y_train)
    probabilities = rf.predict_proba(X_test)
    rf_classes = list(rf.classes_)

    rf_records = []
    for exp_id, actual, probs in zip(sorted(test_ids), y_test, probabilities):
        order = np.argsort(probs)[::-1]
        ranking = [rf_classes[i] for i in order]
        scores = {rf_classes[i]: float(probs[i]) for i in range(len(rf_classes))}
        rf_records.append({
            "experiment_id": int(exp_id),
            "actual": str(actual),
            "ranking": ranking,
            "scores": scores,
        })

    # Topology anomaly baselines, active columns, and threshold use training
    # normal telemetry only. Fault labels are not included in scored frames.
    normal_train, active_metrics, constant_metrics = active_port_metrics(
        sensor, train_ids
    )
    port_means, port_stds = fit_port_baseline(normal_train, active_metrics)
    train_normal_scores = score_port_rows(
        normal_train, port_means, port_stds, active_metrics
    )
    threshold = float(
        train_normal_scores["anomaly_score"].quantile(
            NORMAL_THRESHOLD_QUANTILE
        )
    )
    scored = score_port_rows(sensor, port_means, port_stds, active_metrics)

    topology_records = []
    for exp_id in sorted(test_ids):
        ranked = topology_rank_for_experiment(scored, exp_id, threshold)
        ranking = ranked.index.tolist()
        if len(ranking) != len(LABELS) or set(ranking) != set(LABELS):
            raise AssertionError("Topology ranking omitted or duplicated candidate links")
        scores = ranked["rank_score"].to_dict()
        topology_records.append({
            "experiment_id": int(exp_id),
            "actual": str(labels.loc[exp_id]),
            "ranking": ranking,
            "scores": {key: float(value) for key, value in scores.items()},
        })

    # Sanity-check label isolation by confirming the ranker receives only
    # feature columns and grouping metadata, never fault_location/type.
    if "fault_location" in sensor.columns or "fault_type" in sensor.columns:
        raise AssertionError("Fault labels leaked into topology scoring frame")
    if set(r["experiment_id"] for r in rf_records) != test_ids:
        raise AssertionError("RF result experiments do not match held-out split")
    if set(r["experiment_id"] for r in topology_records) != test_ids:
        raise AssertionError("Topology result experiments do not match held-out split")

    method_results = {
        "rf_baseline": rf_records,
        "topology_link_ranker": topology_records,
    }
    report_rows = make_report_rows(method_results, labels)
    report = pd.DataFrame(report_rows)
    report.to_csv(OUTPUT, index=False, mode="x")

    print("SPLIT")
    print("-----")
    print("Training IDs:", sorted(train_ids))
    print("Testing IDs:", sorted(test_ids))
    print("Training class counts:", train_labels.value_counts().to_dict())
    print("Testing class counts:", test_labels.value_counts().to_dict())
    print("Active topology metrics:", active_metrics)
    print("Excluded constant metrics:", constant_metrics)
    print(f"Training-normal onset threshold ({NORMAL_THRESHOLD_QUANTILE:.0%}):", round(threshold, 6))
    print("Port mapping basis: Mininet link-add order + observed OpenFlow port IDs")
    print("Port mapping limitation: runtime OVS ofports are not recorded in this dataset")

    for method, records in method_results.items():
        actuals = [r["actual"] for r in records]
        rankings = [r["ranking"] for r in records]
        metrics = topk_metrics(actuals, rankings)
        print(f"\n{method}")
        print("-" * len(method))
        print(f"Top-1: {metrics['top1_accuracy']:.2%}")
        print(f"Top-2: {metrics['top2_accuracy']:.2%}")
        print(f"Top-3: {metrics['top3_accuracy']:.2%} (all three candidates)")
        print("Per-class Top-1 report:")
        print(classification_report(
            actuals,
            [r["ranking"][0] for r in records],
            labels=LABELS,
            zero_division=0,
        ))
        print("Per-class confusion matrix:")
        print(confusion_matrix(
            actuals,
            [r["ranking"][0] for r in records],
            labels=LABELS,
        ))
        for record in records:
            print(
                f"Experiment {record['experiment_id']}: actual={record['actual']}, "
                f"ranking={record['ranking']}"
            )

    print("\nSaved new results:", OUTPUT)


if __name__ == "__main__":
    main()
