"""Fair grouped comparison of the existing RF and fixed topology ranker.

This is conditional fault-window localization: the known phase log selects the
first 10 seconds of each fault window. It is not an online detector.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "candidate_master_dataset.csv"
RESULTS = ROOT / "grouped_evaluation.csv"
SUMMARY = ROOT / "evaluation_summary.json"
SPLITS = ROOT / "split_assignments.csv"
FEATURES_OUT = ROOT / "fold_feature_policy.csv"
LABELS = ("s1-s2", "s2-s3", "s3-s4")
SWITCHES = ("s1", "s2", "s3", "s4")
LINK_PORTS = {
    "s1-s2": (("s1", "2"), ("s2", "1")),
    "s2-s3": (("s2", "2"), ("s3", "1")),
    "s3-s4": (("s3", "2"), ("s4", "1")),
}
METRICS = ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")
RF_STAT_NAMES = ("mean_anomaly", "max_anomaly", "persistence", "first_anomaly_seconds")
EARLY_SECONDS = 10.0
NORMAL_THRESHOLD_QUANTILE = 0.95
Z_SCORE_CLIP = 10.0
FORBIDDEN_PREDICTORS = {
    "experiment_id", "physical_run_id", "logical_experiment_id", "fault_location",
    "fault_type", "phase", "timestamp", "switch", "port", "interface_name",
    "target_link", "label",
}


def ordered_grouped_splits(experiment_ids):
    ids = sorted(map(int, experiment_ids))
    if len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError("LOEO requires at least two unique experiment IDs")
    for held_out in ids:
        train = tuple(x for x in ids if x != held_out)
        if set(train) & {held_out} or set(train) | {held_out} != set(ids):
            raise AssertionError("Experiment leakage in grouped split")
        yield held_out, train


def load_candidate(path=None):
    # Resolve at call time so wrappers can select a versioned dataset without
    # a definition-time default capturing an older file.
    if path is None:
        path = DATA
    frame = pd.read_csv(path)
    required = {"timestamp", "switch", "port", "experiment_id", "phase", "fault_type", "fault_location", *METRICS}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Candidate is missing required columns: {sorted(missing)}")
    frame = frame.copy()
    # Candidate files combine historical and recollected ISO timestamps with
    # differing fractional-second precision; parse each ISO value explicitly.
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", format="mixed")
    if frame["timestamp"].isna().any():
        raise ValueError("Candidate has missing/unparseable timestamps")
    frame["experiment_id"] = pd.to_numeric(frame["experiment_id"], errors="raise").astype(int)
    for name in METRICS:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
        if not np.isfinite(frame[name].to_numpy(dtype=float)).all():
            raise ValueError(f"Invalid values in {name}")
    if frame.duplicated(["experiment_id", "timestamp", "switch", "port"]).any():
        raise ValueError("Candidate contains duplicate experiment/time/switch/port rows")
    labels = {}
    fault = frame.loc[frame["phase"] == "fault"]
    for exp_id, rows in fault.groupby("experiment_id"):
        values = set(rows["fault_location"].astype(str))
        if len(values) != 1 or next(iter(values)) not in LABELS:
            raise ValueError(f"Invalid or inconsistent fault label for experiment {exp_id}: {values}")
        labels[int(exp_id)] = next(iter(values))
    if set(frame["experiment_id"]) != set(labels):
        raise ValueError("Every experiment must have one fault phase and one link label")
    if set(frame["phase"]) - {"normal", "fault", "recovery"}:
        raise ValueError("Unexpected phase label")
    return frame, labels


def fit_active_metrics(sensor, train_ids):
    train_normal = sensor[
        sensor["experiment_id"].isin(train_ids)
        & (sensor["phase"] == "normal")
        & (sensor["port"] != "LOCAL")
    ]
    if train_normal.empty:
        raise ValueError("No training-normal physical-port data")
    active = tuple(name for name in METRICS if train_normal[name].nunique(dropna=False) > 1)
    constant = tuple(name for name in METRICS if name not in active)
    if not active:
        raise ValueError("All training-normal physical-port metrics are constant")
    return train_normal, active, constant


def switch_level_frame(sensor, active):
    physical = sensor[sensor["port"] != "LOCAL"]
    return physical.groupby(
        ["experiment_id", "timestamp", "switch", "phase"], as_index=False
    )[list(active)].mean()


def fit_switch_baseline(rf_sensor, train_ids, active):
    normal = rf_sensor[
        rf_sensor["experiment_id"].isin(train_ids) & (rf_sensor["phase"] == "normal")
    ]
    means = normal.groupby("switch")[list(active)].mean()
    stds = normal.groupby("switch")[list(active)].std().fillna(0.0001).clip(lower=0.0001)
    if set(SWITCHES) - set(means.index):
        raise ValueError("Missing training-normal switch baseline")
    return means, stds


def make_rf_vector(rf_sensor, exp_id, means, stds, active):
    exp = rf_sensor[rf_sensor["experiment_id"] == exp_id]
    fault = exp[exp["phase"] == "fault"]
    if fault.empty:
        raise ValueError(f"No oracle-selected fault window for experiment {exp_id}")
    start = fault["timestamp"].min()
    early = fault[fault["timestamp"] <= start + pd.Timedelta(seconds=EARLY_SECONDS)]
    vector = []
    for switch in SWITCHES:
        data = early[early["switch"] == switch]
        if data.empty:
            raise ValueError(f"No early fault rows for {exp_id}/{switch}")
        z = ((data[list(active)] - means.loc[switch, list(active)]).abs() / stds.loc[switch, list(active)])
        score = z.mean(axis=1).to_numpy(dtype=float)
        above = np.flatnonzero(score > 1.0)
        first = float((data.iloc[int(above[0])]["timestamp"] - start).total_seconds()) if len(above) else 999.0
        vector.extend((float(score.mean()), float(score.max()), float(np.mean(score > 1.0)), first))
    return np.asarray(vector, dtype=float)


def fit_port_baseline(train_normal, active):
    grouped = train_normal.groupby(["switch", "port"])[list(active)]
    means = grouped.mean()
    stds = grouped.std().fillna(0.0).clip(lower=0.0001)
    required = {key for endpoints in LINK_PORTS.values() for key in endpoints}
    missing = required - set(means.index)
    if missing:
        raise ValueError(f"Missing training baseline for candidate link endpoints: {sorted(missing)}")
    return means, stds


def port_scores(sensor, means, stds, active, experiment_ids=None):
    physical = sensor[sensor["port"] != "LOCAL"]
    if experiment_ids is not None:
        physical = physical[physical["experiment_id"].isin(experiment_ids)]
    chunks = []
    for (switch, port), rows in physical.groupby(["switch", "port"], sort=False):
        key = (switch, port)
        if key not in means.index:
            raise ValueError(f"No training baseline for observed port {key}")
        z = ((rows[list(active)] - means.loc[key, list(active)]).abs() / stds.loc[key, list(active)]).clip(upper=Z_SCORE_CLIP)
        part = rows[["experiment_id", "timestamp", "switch", "port", "phase"]].copy()
        part["anomaly_score"] = z.mean(axis=1).to_numpy(dtype=float)
        chunks.append(part)
    if not chunks:
        raise ValueError("No physical port telemetry to score")
    scores = pd.concat(chunks, ignore_index=True)
    if not np.isfinite(scores["anomaly_score"].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite port anomaly scores")
    return scores


def rank_topology(scores, exp_id, threshold):
    exp = scores[(scores["experiment_id"] == exp_id) & (scores["phase"] == "fault")].copy()
    if exp.empty:
        raise ValueError(f"No fault-window data for experiment {exp_id}")
    start = exp["timestamp"].min()
    exp = exp[exp["timestamp"] <= start + pd.Timedelta(seconds=EARLY_SECONDS)].copy()
    exp["fault_start"] = start
    evidence = {}
    for link, endpoints in LINK_PORTS.items():
        endpoint_means, onset = [], []
        for switch, port in endpoints:
            rows = exp[(exp["switch"] == switch) & (exp["port"] == port)]
            if rows.empty:
                raise ValueError(f"Missing candidate endpoint telemetry: {link} {(switch, port)}")
            endpoint_means.append(float(rows["anomaly_score"].mean()))
            crossed = rows[rows["anomaly_score"] > threshold]
            onset.append(float((crossed["timestamp"].min() - start).total_seconds()) if not crossed.empty else None)
        joint = min(endpoint_means)
        imbalance = abs(endpoint_means[0] - endpoint_means[1])
        pair_onset = max(onset) if all(x is not None for x in onset) else 999.0
        remote_switches = set(SWITCHES) - {endpoints[0][0], endpoints[1][0]}
        remote_onsets = []
        for switch in remote_switches:
            rows = exp[exp["switch"] == switch]
            crossed = rows[rows["anomaly_score"] > threshold]
            remote_onsets.append(float((crossed["timestamp"].min() - start).total_seconds()) if not crossed.empty else EARLY_SECONDS + 1.0)
        remote_onset = min(remote_onsets) if remote_onsets else EARLY_SECONDS + 1.0
        margin = remote_onset - pair_onset if pair_onset < 999.0 else -EARLY_SECONDS
        evidence[link] = {
            "link_anomaly": joint,
            "endpoint_mean_anomaly": float(np.mean(endpoint_means)),
            "endpoint_imbalance": imbalance,
            "pair_onset_seconds": pair_onset,
            "remote_onset_seconds": remote_onset,
            "propagation_margin_seconds": margin,
        }
    table = pd.DataFrame.from_dict(evidence, orient="index")
    utilities = []
    for metric, ascending in (("link_anomaly", False), ("endpoint_imbalance", True), ("pair_onset_seconds", True), ("propagation_margin_seconds", False)):
        ranks = table[metric].rank(method="average", ascending=ascending)
        utilities.append((len(table) + 1.0 - ranks) / len(table))
    table["rank_score"] = pd.concat(utilities, axis=1).mean(axis=1)
    table["candidate_link"] = table.index
    # Preserve the existing evaluator's score/anomaly/endpoint tie-break rule.
    table = table.sort_values(
        ["rank_score", "link_anomaly", "endpoint_mean_anomaly"],
        ascending=[False, False, False], kind="mergesort",
    )
    return table


def _stable_rf_ranking(model, vector):
    probabilities = model.predict_proba(vector.reshape(1, -1))[0]
    pairs = sorted(zip(model.classes_, probabilities), key=lambda item: (-float(item[1]), str(item[0])))
    return [str(label) for label, _ in pairs], {str(label): float(prob) for label, prob in pairs}


def evaluate():
    for path in (RESULTS, SUMMARY, SPLITS, FEATURES_OUT):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite evaluation output: {path}")
    frame, label_by_id = load_candidate()
    ids = sorted(label_by_id)
    if len(ids) < 3:
        raise ValueError(f"At least three logical experiments are required, found {len(ids)}")
    if set(label_by_id.values()) != set(LABELS):
        raise ValueError("All candidate link classes must be present")

    # Separate label table from sensor frame. Fault label/type never enter any
    # feature calculation. ID/time/phase remain selection/grouping metadata.
    sensor = frame[["experiment_id", "timestamp", "switch", "port", "phase", *METRICS]].copy()
    predictor_fields = set(METRICS) | set(RF_STAT_NAMES)
    if predictor_fields & FORBIDDEN_PREDICTORS:
        raise AssertionError("Forbidden metadata entered predictor definitions")
    all_predictions = []
    split_rows, feature_rows = [], []
    for fold, (held_out, train_ids) in enumerate(ordered_grouped_splits(ids), start=1):
        train_ids = set(train_ids)
        if held_out in train_ids:
            raise AssertionError("Held-out experiment leaked into training")
        train_normal, active, constant = fit_active_metrics(sensor, train_ids)
        feature_rows.append({
            "fold": fold, "held_out_experiment_id": held_out,
            "active_metrics": ";".join(active), "excluded_constant_metrics": ";".join(constant),
            "training_normal_experiments": ";".join(map(str, sorted(train_ids))),
        })
        split_rows.append({
            "fold": fold, "test_experiment_id": held_out,
            "train_experiment_ids": ";".join(map(str, sorted(train_ids))),
            "train_count": len(train_ids), "test_count": 1,
        })

        rf_sensor = switch_level_frame(sensor, active)
        switch_means, switch_stds = fit_switch_baseline(rf_sensor, train_ids, active)
        X_train = np.vstack([make_rf_vector(rf_sensor, exp, switch_means, switch_stds, active) for exp in sorted(train_ids)])
        y_train = np.asarray([label_by_id[exp] for exp in sorted(train_ids)])
        if X_train.shape[1] != len(SWITCHES) * len(RF_STAT_NAMES):
            raise AssertionError("Unexpected RF feature dimension")
        rf_model = RandomForestClassifier(
            n_estimators=300, max_depth=5, random_state=42, class_weight="balanced",
        )
        rf_model.fit(X_train, y_train)
        x_test = make_rf_vector(rf_sensor, held_out, switch_means, switch_stds, active)
        rf_ranking, rf_scores = _stable_rf_ranking(rf_model, x_test)

        # Topology thresholds and baselines are fit exclusively on this fold's
        # normal training telemetry. Test labels are joined only after ranking.
        port_means, port_stds = fit_port_baseline(train_normal, active)
        train_normal_scores = port_scores(train_normal, port_means, port_stds, active)
        threshold = float(train_normal_scores["anomaly_score"].quantile(NORMAL_THRESHOLD_QUANTILE))
        held_out_scores = port_scores(sensor, port_means, port_stds, active, {held_out})
        topo = rank_topology(held_out_scores, held_out, threshold)
        topo_ranking = topo.index.astype(str).tolist()
        topo_scores = {str(link): float(topo.loc[link, "rank_score"]) for link in topo.index}

        # Label join occurs after both model rankings have been computed.
        actual = label_by_id[held_out]
        all_predictions.append({
            "fold": fold, "experiment_id": held_out, "actual_link": actual,
            "rf_ranking": rf_ranking, "rf_scores": rf_scores,
            "topology_ranking": topo_ranking, "topology_scores": topo_scores,
            "threshold": threshold, "active_metrics": list(active),
        })

    result_rows = []
    for pred in all_predictions:
        actual = pred["actual_link"]
        for method, ranking_key, score_key in (
            ("rf_baseline", "rf_ranking", "rf_scores"),
            ("topology_link_ranker", "topology_ranking", "topology_scores"),
        ):
            ranking = pred[ranking_key]
            scores = pred[score_key]
            top_groups = {}
            for link in ranking:
                top_groups.setdefault(round(scores[link], 12), []).append(link)
            tied = [links for links in top_groups.values() if len(links) > 1]
            result_rows.append({
                "fold": pred["fold"], "experiment_id": pred["experiment_id"],
                "method": method, "actual_link": actual,
                "rank1_link": ranking[0], "rank2_link": ranking[1], "rank3_link": ranking[2],
                "rank1_score": scores[ranking[0]], "rank2_score": scores[ranking[1]], "rank3_score": scores[ranking[2]],
                "top1_hit": actual in ranking[:1], "top2_hit": actual in ranking[:2], "top3_hit": actual in ranking[:3],
                "score_ties": json.dumps(tied), "active_metrics": ";".join(pred["active_metrics"]),
                "train_experiment_ids": next(x["train_experiment_ids"] for x in split_rows if x["fold"] == pred["fold"]),
                "normal_threshold": pred["threshold"] if method == "topology_link_ranker" else "",
            })

    result = pd.DataFrame(result_rows)
    summaries = {}
    for method in ("rf_baseline", "topology_link_ranker"):
        rows = result[result["method"] == method]
        actuals = [x["actual_link"] for x in all_predictions]
        predictions = [x["rank1_link"] for _, x in rows.sort_values("experiment_id").iterrows()]
        class_metrics = {}
        for label in LABELS:
            selected = rows[rows["actual_link"] == label]
            support = len(selected)
            tp = int(((selected["rank1_link"] == label)).sum())
            predicted_as_class = int((rows["rank1_link"] == label).sum())
            precision = tp / predicted_as_class if predicted_as_class else 0.0
            recall = tp / support if support else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            class_metrics[label] = {
                "support": support, "top1_precision": precision, "top1_recall": recall, "top1_f1": f1,
                "top2_recall": float(selected["top2_hit"].mean()) if support else 0.0,
                "top3_recall": float(selected["top3_hit"].mean()) if support else 0.0,
            }
        summaries[method] = {
            "support": len(rows),
            "top1_accuracy": float(rows["top1_hit"].mean()),
            "top2_accuracy": float(rows["top2_hit"].mean()),
            "top3_accuracy": float(rows["top3_hit"].mean()),
            "per_class": class_metrics,
            "confusion_matrix_rows_actual_cols_predicted": confusion_matrix(actuals, predictions, labels=list(LABELS)).tolist(),
        }

    # No output exists before this point. Use exclusive-create writes.
    result.to_csv(RESULTS, index=False, mode="x")
    pd.DataFrame(split_rows).to_csv(SPLITS, index=False, mode="x")
    pd.DataFrame(feature_rows).to_csv(FEATURES_OUT, index=False, mode="x")
    summary = {
        "protocol": f"leave-one-logical-experiment-out ({len(ids)} folds), grouped by experiment_id; each fold has {len(ids) - 1} train and 1 test experiment",
        "task": "conditional fault-window link localization with oracle phase boundaries; not online fault detection/localization",
        "oracle_information": "phase labels select the first 10 seconds from the annotated fault phase; recovery telemetry is excluded; ground-truth fault_location is joined only after predictions for metrics",
        "predictors": {
            "raw_metrics_active_per_fold": list(METRICS),
            "constant_feature_policy": "fit on training-normal non-LOCAL port telemetry only; exclude metrics with no variation in that fold",
            "rf_features": [f"{switch}_{stat}" for switch in SWITCHES for stat in RF_STAT_NAMES],
            "topology_features": "per-port absolute z-scores; candidate link endpoint mean, imbalance, threshold onset, and remote propagation margin; equal-weight rank aggregation retained",
            "forbidden_predictor_fields": sorted(FORBIDDEN_PREDICTORS),
        },
        "fit_scope": f"Each fold's RF, means/stds, active-metric selection, topology threshold (training-normal 95th percentile), and port baselines use only the {len(ids) - 1} training experiments. No held-out labels tune features, thresholds, or weights.",
        "topology_mapping": "Added physical runs 21 and 23-29 carry independently validated captured runtime OVS switch-port mappings. Historical source runs have no captured runtime mapping and retain setup-inferred port assignments. Physical run 20 is invalid and run 22 remains provisional; neither is included.",
        "ranking_weights": "Existing four-component equal-weight rank aggregation; unchanged.",
        "tie_rule": "RF probability ties use lexical link order. Topology reproduces score, link-anomaly, endpoint-mean tie-breaks and stable candidate insertion order. score_ties reports exact score ties; top-k is membership in the first k ranked candidates.",
        "top3_note": "All three configured candidate links are ranked, so Top-3 is necessarily 100% when no candidate is missing; report it for completeness, but it is not discriminative.",
        "methods": summaries,
        "per_experiment_predictions": [
            {"fold": p["fold"], "experiment_id": p["experiment_id"], "actual_link": p["actual_link"],
             "rf_ranking": p["rf_ranking"], "rf_scores": p["rf_scores"],
             "topology_ranking": p["topology_ranking"], "topology_scores": p["topology_scores"],
             "threshold": p["threshold"], "active_metrics": p["active_metrics"]}
            for p in all_predictions
        ],
        "software": {"python": __import__("sys").version, "pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "random_seed": 42,
        "model": {"type": "RandomForestClassifier", "n_estimators": 300, "max_depth": 5, "class_weight": "balanced"},
        "outputs": {"predictions": str(RESULTS), "splits": str(SPLITS), "fold_feature_policy": str(FEATURES_OUT)},
    }
    with SUMMARY.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"results": str(RESULTS), "summary": str(SUMMARY), "methods": summaries}, indent=2))


if __name__ == "__main__":
    evaluate()
