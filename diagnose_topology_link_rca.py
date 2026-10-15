"""Explain the existing topology-aware link ranking on selected test cases.

This is a read-only diagnostic except for creating a new CSV with exclusive
creation mode. It does not alter the evaluator, datasets, models, or results.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_topology_link_rca import (
    EARLY_SECONDS,
    EXPECTED_TEST_IDS,
    LABELS,
    LINK_PORTS,
    METRICS,
    NORMAL_THRESHOLD_QUANTILE,
    OUTPUT as EVALUATOR_OUTPUT,
    PORT_TO_INTERFACE,
    REQUIRED_COLUMNS,
    active_port_metrics,
    candidate_evidence,
    fit_port_baseline,
    make_split,
    normalize_port,
    score_port_rows,
)


INPUT = Path("master_dataset.csv")
OUTPUT = Path("diagnose_topology_link_rca_results.csv")
TARGET_EXPERIMENTS = {10, 15, 16, 18}
RANK_COMPONENTS = [
    ("link_anomaly", False),
    ("endpoint_imbalance", True),
    ("pair_onset_seconds", True),
    ("propagation_margin_seconds", False),
]


def load_diagnostic_data():
    if not INPUT.is_file():
        raise FileNotFoundError(f"Required dataset not found: {INPUT}")
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {OUTPUT}")

    frame = pd.read_csv(INPUT)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")
    if frame.empty:
        raise ValueError("Dataset contains no rows")

    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    if frame["timestamp"].isna().any():
        raise ValueError("Dataset contains missing or invalid timestamps")
    for column in METRICS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise ValueError(f"Dataset contains invalid values in {column}")

    frame["experiment_id"] = pd.to_numeric(
        frame["experiment_id"], errors="raise"
    ).astype(int)
    for column in ["experiment_id", "switch", "phase", "fault_location"]:
        if frame[column].isna().any():
            raise ValueError(f"Dataset contains missing values in {column}")
    frame["switch"] = frame["switch"].astype(str).str.strip()
    frame["phase"] = frame["phase"].astype(str).str.strip().str.lower()
    frame["fault_location"] = (
        frame["fault_location"].astype(str).str.strip().str.lower()
    )
    frame["port"] = frame["port"].map(normalize_port)

    fault = frame[frame["phase"] == "fault"]
    label_counts = fault.groupby("experiment_id")["fault_location"].nunique()
    inconsistent = label_counts[label_counts != 1]
    if not inconsistent.empty:
        raise ValueError(
            "Expected one fault-link label per experiment; inconsistent IDs: "
            f"{inconsistent.index.tolist()}"
        )
    labels = fault.groupby("experiment_id")["fault_location"].first()
    labels = labels[labels.isin(LABELS)]

    # Keep labels separate from this sensor frame. Phase is retained as oracle
    # information for selecting the labeled evaluation window, not a feature.
    sensor = frame[
        ["experiment_id", "timestamp", "switch", "port", "phase", *METRICS]
    ].copy()
    sensor = (
        sensor.groupby(
            ["experiment_id", "timestamp", "switch", "port", "phase"],
            as_index=False,
        )[METRICS]
        .mean()
    )
    if "fault_location" in sensor.columns or "fault_type" in sensor.columns:
        raise AssertionError("Fault labels entered the diagnostic sensor frame")
    return frame, sensor, labels


def onset_for_rows(rows, fault_start, threshold):
    anomalous = rows[rows["anomaly_score"] > threshold]
    if anomalous.empty:
        return np.nan
    return float(
        (anomalous["timestamp"].min() - fault_start).total_seconds()
    )


def diagnose_one_experiment(scored, exp_id, threshold):
    # The phase column and first timestamp in the annotated fault phase select
    # the evaluation window. This is oracle event information; it is not a
    # deployable online event detector.
    fault = scored[
        (scored["experiment_id"] == exp_id) & (scored["phase"] == "fault")
    ].copy()
    if fault.empty:
        raise ValueError(f"No annotated fault-phase rows for experiment {exp_id}")
    fault_start = fault["timestamp"].min()
    early = fault[
        fault["timestamp"] <= fault_start + pd.Timedelta(seconds=EARLY_SECONDS)
    ].copy()
    if early.empty:
        raise ValueError(f"No rows in the evaluation window for experiment {exp_id}")
    early["fault_start"] = fault_start

    evidence = {}
    for link in LABELS:
        endpoint_details = []
        endpoints = LINK_PORTS[link]
        for switch, port in endpoints:
            rows = early[
                (early["switch"] == switch) & (early["port"] == port)
            ]
            if rows.empty:
                raise ValueError(
                    f"Missing mapped endpoint telemetry for {exp_id}, {link}, "
                    f"{switch} port {port}"
                )
            endpoint_details.append({
                "switch": switch,
                "port": port,
                "interface": PORT_TO_INTERFACE[(switch, port)],
                "mean_anomaly": float(rows["anomaly_score"].mean()),
                "onset_seconds": onset_for_rows(rows, fault_start, threshold),
            })

        remote_switches = sorted(
            set(scored["switch"].unique())
            - {endpoints[0][0], endpoints[1][0]}
        )
        remote_times = []
        for switch in remote_switches:
            rows = early[early["switch"] == switch]
            if not rows.empty:
                time_value = onset_for_rows(rows, fault_start, threshold)
                if np.isfinite(time_value):
                    remote_times.append(float(time_value))
        remote_onset = min(remote_times) if remote_times else EARLY_SECONDS + 1.0

        endpoint_means = [d["mean_anomaly"] for d in endpoint_details]
        endpoint_onsets = [d["onset_seconds"] for d in endpoint_details]
        pair_onset = (
            max(endpoint_onsets)
            if all(np.isfinite(value) for value in endpoint_onsets)
            else 999.0
        )
        propagation_margin = (
            remote_onset - pair_onset if pair_onset < 999.0 else -EARLY_SECONDS
        )
        current = {
            "link_anomaly": min(endpoint_means),
            "endpoint_mean_anomaly": float(np.mean(endpoint_means)),
            "endpoint_imbalance": abs(endpoint_means[0] - endpoint_means[1]),
            "pair_onset_seconds": pair_onset,
            "remote_onset_seconds": remote_onset,
            "propagation_margin_seconds": propagation_margin,
        }

        # Confirm diagnostic raw fields reproduce the evaluator's exact score
        # evidence before adding the extra endpoint-onset breakdown.
        evaluator_evidence = candidate_evidence(early, link, endpoints, threshold)
        for key in current:
            if not np.isclose(
                current[key], evaluator_evidence[key], rtol=1e-10, atol=1e-10
            ):
                raise AssertionError(
                    f"Diagnostic/evaluator mismatch for {exp_id} {link} {key}: "
                    f"{current[key]} != {evaluator_evidence[key]}"
                )
        current["endpoint_a"] = endpoint_details[0]
        current["endpoint_b"] = endpoint_details[1]
        evidence[link] = current

    table = pd.DataFrame.from_dict(evidence, orient="index")
    table.index.name = "candidate_link"
    component_rank_columns = {
        "link_anomaly": "rank_link_anomaly",
        "endpoint_imbalance": "rank_endpoint_imbalance",
        "pair_onset_seconds": "rank_pair_onset",
        "propagation_margin_seconds": "rank_propagation_margin",
    }
    utilities = []
    for component, ascending in RANK_COMPONENTS:
        ranks = table[component].rank(method="average", ascending=ascending)
        table[component_rank_columns[component]] = ranks
        utilities.append((len(table) + 1.0 - ranks) / len(table))
    table["final_aggregate_score"] = pd.concat(utilities, axis=1).mean(axis=1)
    table = table.sort_values(
        ["final_aggregate_score", "link_anomaly", "endpoint_mean_anomaly"],
        ascending=[False, False, False],
        kind="mergesort",
    )
    table["final_rank"] = np.arange(1, len(table) + 1)
    for candidate in table.index:
        tied = [
            other for other in table.index
            if other != candidate
            and np.isclose(
                table.loc[candidate, "final_aggregate_score"],
                table.loc[other, "final_aggregate_score"],
                rtol=0.0,
                atol=1e-12,
            )
        ]
        table.loc[candidate, "final_score_tied"] = bool(tied)
        table.loc[candidate, "tied_candidate_links"] = ";".join(tied)

    result = []
    for link, row in table.iterrows():
        a = row["endpoint_a"]
        b = row["endpoint_b"]
        result.append({
            "experiment_id": exp_id,
            "candidate_link": link,
            "endpoint_a_switch": a["switch"],
            "endpoint_a_port": a["port"],
            "endpoint_a_interface_inferred": a["interface"],
            "endpoint_a_mean_anomaly": a["mean_anomaly"],
            "endpoint_a_onset_seconds": a["onset_seconds"],
            "endpoint_b_switch": b["switch"],
            "endpoint_b_port": b["port"],
            "endpoint_b_interface_inferred": b["interface"],
            "endpoint_b_mean_anomaly": b["mean_anomaly"],
            "endpoint_b_onset_seconds": b["onset_seconds"],
            "endpoint_imbalance": row["endpoint_imbalance"],
            "remote_onset_seconds": row["remote_onset_seconds"],
            "propagation_margin_seconds": row["propagation_margin_seconds"],
            "rank_link_anomaly": row["rank_link_anomaly"],
            "rank_endpoint_imbalance": row["rank_endpoint_imbalance"],
            "rank_pair_onset": row["rank_pair_onset"],
            "rank_propagation_margin": row["rank_propagation_margin"],
            "final_aggregate_score": row["final_aggregate_score"],
            "final_rank": int(row["final_rank"]),
            "final_score_tied": bool(row["final_score_tied"]),
            "tied_candidate_links": row["tied_candidate_links"],
        })
    return result


def main():
    _, sensor, labels = load_diagnostic_data()
    train_ids, test_ids = make_split(labels)
    if not TARGET_EXPERIMENTS.issubset(test_ids):
        raise ValueError(
            f"Requested experiments {sorted(TARGET_EXPERIMENTS)} are not all "
            f"in the reproduced held-out set {sorted(test_ids)}"
        )
    if test_ids != EXPECTED_TEST_IDS:
        raise AssertionError("Unexpected held-out experiment IDs")

    normal_train, active, constant = active_port_metrics(sensor, train_ids)
    means, stds = fit_port_baseline(normal_train, active)
    train_normal_scores = score_port_rows(
        normal_train, means, stds, active
    )
    threshold = float(
        train_normal_scores["anomaly_score"].quantile(
            NORMAL_THRESHOLD_QUANTILE
        )
    )
    scored = score_port_rows(sensor, means, stds, active)

    # Correlations use training-normal physical-port rows only. LOCAL is
    # excluded because it is not a topology link endpoint.
    corr_frame = normal_train[normal_train["port"] != "LOCAL"][
        ["tx_packet_rate", "tx_throughput_mbps"]
    ]
    pearson = float(corr_frame.corr(method="pearson").iloc[0, 1])
    spearman = float(corr_frame.corr(method="spearman").iloc[0, 1])

    diagnostic_rows = []
    for exp_id in sorted(TARGET_EXPERIMENTS):
        diagnostic_rows.extend(
            diagnose_one_experiment(scored, exp_id, threshold)
        )

    # Actual labels are joined only after all features, component ranks,
    # aggregate scores, and ties have been calculated.
    for row in diagnostic_rows:
        actual = str(labels.loc[row["experiment_id"]])
        row["actual_fault_link_diagnostic_only"] = actual
        row["candidate_matches_actual_diagnostic_only"] = (
            row["candidate_link"] == actual
        )
        row["training_normal_tx_pearson"] = pearson
        row["training_normal_tx_spearman"] = spearman
        row["active_metrics_training_normal"] = ";".join(active)
        row["excluded_constant_metrics_training_normal"] = ";".join(constant)
        row["normal_onset_threshold"] = threshold
        row["mapping_status"] = "inferred from setup order; not runtime-verified"
        row["window_basis"] = (
            "oracle phase=fault label; start=first timestamp annotated fault"
        )

    output = pd.DataFrame(diagnostic_rows)
    output.to_csv(OUTPUT, index=False, mode="x")

    print("Split train IDs:", sorted(train_ids))
    print("Split test IDs:", sorted(test_ids))
    print("Diagnostic test IDs:", sorted(TARGET_EXPERIMENTS))
    print("Active metrics:", active)
    print("Excluded constant metrics:", constant)
    print(f"Training-normal onset threshold: {threshold:.6f}")
    print(f"Training-normal tx Pearson correlation: {pearson:.6f}")
    print(f"Training-normal tx Spearman correlation: {spearman:.6f}")
    print("Mapping is inferred from Mininet link order; runtime OVS mapping is not verified.")
    print("Window selection uses oracle fault-phase labels and annotated phase start.")
    print("Evaluator source:", EVALUATOR_OUTPUT)
    print("Saved diagnostic CSV:", OUTPUT)
    print("\nDiagnostic rows:")
    print(output[[
        "experiment_id",
        "candidate_link",
        "endpoint_a_mean_anomaly",
        "endpoint_b_mean_anomaly",
        "endpoint_imbalance",
        "endpoint_a_onset_seconds",
        "endpoint_b_onset_seconds",
        "remote_onset_seconds",
        "propagation_margin_seconds",
        "rank_link_anomaly",
        "rank_endpoint_imbalance",
        "rank_pair_onset",
        "rank_propagation_margin",
        "final_aggregate_score",
        "final_score_tied",
        "tied_candidate_links",
        "actual_fault_link_diagnostic_only",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
