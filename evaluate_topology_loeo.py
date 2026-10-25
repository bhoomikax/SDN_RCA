"""Grouped leave-one-experiment-out RF and topology-ranker evaluation for N-switch linear topologies.

Generalizes evaluate_grouped_rca_generalized.py to an arbitrary number of
switches and candidate links. The per-fold computation is unchanged: training
normal telemetry fits active metrics, switch/port baselines, and the ranker
threshold; the held-out experiment never enters any fit. Link endpoint ports
come from the candidate's recorded runtime mapping (link_port_mapping.csv) or,
for the historical four-switch data, from the setup-inferred static mapping.
Outputs are written to a new directory only.
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
import sklearn
from sklearn.ensemble import RandomForestClassifier

from linear_topology import LinearTopology


ROOT = Path(__file__).resolve().parent
METRICS = ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")
RF_STAT_NAMES = ("mean_anomaly", "max_anomaly", "persistence", "first_anomaly_seconds")
EARLY_SECONDS = 10.0
NORMAL_THRESHOLD_QUANTILE = 0.95
Z_SCORE_CLIP = 10.0
RF_PARAMS = {"n_estimators": 300, "max_depth": 5, "random_state": 42, "class_weight": "balanced"}
RANK_COMPONENTS = (
    ("link_anomaly", False), ("endpoint_imbalance", True),
    ("pair_onset_seconds", True), ("propagation_margin_seconds", False),
)
FORBIDDEN_PREDICTORS = {
    "experiment_id", "physical_run_id", "logical_experiment_id", "fault_location",
    "fault_type", "phase", "timestamp", "switch", "port", "interface_name", "target_link", "label",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson_interval(successes, total, z=1.959963984540054):
    if total <= 0:
        return [None, None]
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) / total) + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def static_link_ports(topology):
    """Setup-inferred ports for historical runs: port 1 faces the left neighbour, port 2 the right."""
    return {
        link: ((left, "2"), (right, "1"))
        for link, (left, right) in ((link, topology.link_endpoints(link)) for link in topology.candidate_links)
    }


def link_ports_from_mapping(mapping_rows, topology):
    """Candidate link endpoints from the recorded runtime mapping, ordered (left switch, right switch)."""
    by_link = {}
    for row in mapping_rows:
        link = row["link"]
        if topology.is_candidate(link):
            by_link.setdefault(link, {})[row["switch"]] = str(row["openflow_port"])
    result = {}
    for link in topology.candidate_links:
        left, right = topology.link_endpoints(link)
        ports = by_link.get(link, {})
        if set(ports) != {left, right}:
            raise ValueError("Mapping lacks both endpoints for %s: %s" % (link, sorted(ports)))
        result[link] = ((left, ports[left]), (right, ports[right]))
    return result


def load_link_ports(candidate_dir, topology, static=False):
    if static:
        return static_link_ports(topology), "static setup-inferred mapping (historical four-switch data)"
    path = Path(candidate_dir) / "link_port_mapping.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    return link_ports_from_mapping(rows, topology), "recorded runtime OVS mapping: %s" % path


def ordered_grouped_splits(experiment_ids):
    ids = sorted(map(int, experiment_ids))
    if len(ids) < 2 or len(ids) != len(set(ids)):
        raise ValueError("LOEO requires at least two unique experiment IDs")
    for held_out in ids:
        train = tuple(x for x in ids if x != held_out)
        if held_out in train or set(train) | {held_out} != set(ids):
            raise AssertionError("Experiment leakage in grouped split")
        yield held_out, train


def load_candidate(path, topology):
    frame = pd.read_csv(path)
    required = {"timestamp", "switch", "port", "experiment_id", "phase", "fault_type", "fault_location", *METRICS}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("Candidate is missing required columns: %s" % sorted(missing))
    frame = frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", format="mixed")
    if frame["timestamp"].isna().any():
        raise ValueError("Candidate has missing/unparseable timestamps")
    frame["experiment_id"] = pd.to_numeric(frame["experiment_id"], errors="raise").astype(int)
    frame["port"] = frame["port"].astype(str).str.strip()
    frame["switch"] = frame["switch"].astype(str).str.strip()
    for name in METRICS:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
        if not np.isfinite(frame[name].to_numpy(dtype=float)).all():
            raise ValueError("Invalid values in %s" % name)
    if frame.duplicated(["experiment_id", "timestamp", "switch", "port"]).any():
        raise ValueError("Candidate contains duplicate experiment/time/switch/port rows")
    unknown = set(frame["switch"]) - set(topology.switches)
    if unknown:
        raise ValueError("Candidate has switches outside the %d-switch topology: %s" % (topology.switch_count, sorted(unknown)))
    labels = {}
    for exp_id, rows in frame.loc[frame["phase"] == "fault"].groupby("experiment_id"):
        values = set(rows["fault_location"].astype(str))
        if len(values) != 1 or not topology.is_candidate(next(iter(values))):
            raise ValueError("Invalid or inconsistent fault label for experiment %s: %s" % (exp_id, values))
        labels[int(exp_id)] = next(iter(values))
    if set(frame["experiment_id"]) != set(labels):
        raise ValueError("Every experiment must have one fault phase and one link label")
    if set(frame["phase"]) - {"normal", "fault", "recovery"}:
        raise ValueError("Unexpected phase label")
    return frame, labels


def fit_active_metrics(sensor, train_ids):
    train_normal = sensor[sensor["experiment_id"].isin(train_ids) & (sensor["phase"] == "normal") & (sensor["port"] != "LOCAL")]
    if train_normal.empty:
        raise ValueError("No training-normal physical-port data")
    active = tuple(name for name in METRICS if train_normal[name].nunique(dropna=False) > 1)
    constant = tuple(name for name in METRICS if name not in active)
    if not active:
        raise ValueError("All training-normal physical-port metrics are constant")
    return train_normal, active, constant


def switch_level_frame(sensor, active):
    physical = sensor[sensor["port"] != "LOCAL"]
    return physical.groupby(["experiment_id", "timestamp", "switch", "phase"], as_index=False)[list(active)].mean()


def fit_switch_baseline(rf_sensor, train_ids, active, topology):
    normal = rf_sensor[rf_sensor["experiment_id"].isin(train_ids) & (rf_sensor["phase"] == "normal")]
    means = normal.groupby("switch")[list(active)].mean()
    stds = normal.groupby("switch")[list(active)].std().fillna(0.0001).clip(lower=0.0001)
    if set(topology.switches) - set(means.index):
        raise ValueError("Missing training-normal switch baseline")
    return means, stds


def make_rf_vector(rf_sensor, exp_id, means, stds, active, topology):
    exp = rf_sensor[rf_sensor["experiment_id"] == exp_id]
    fault = exp[exp["phase"] == "fault"]
    if fault.empty:
        raise ValueError("No oracle-selected fault window for experiment %s" % exp_id)
    start = fault["timestamp"].min()
    early = fault[fault["timestamp"] <= start + pd.Timedelta(seconds=EARLY_SECONDS)]
    vector = []
    for switch in topology.switches:
        data = early[early["switch"] == switch]
        if data.empty:
            raise ValueError("No early fault rows for %s/%s" % (exp_id, switch))
        z = (data[list(active)] - means.loc[switch, list(active)]).abs() / stds.loc[switch, list(active)]
        score = z.mean(axis=1).to_numpy(dtype=float)
        above = np.flatnonzero(score > 1.0)
        first = float((data.iloc[int(above[0])]["timestamp"] - start).total_seconds()) if len(above) else 999.0
        vector.extend((float(score.mean()), float(score.max()), float(np.mean(score > 1.0)), first))
    return np.asarray(vector, dtype=float)


def rf_feature_names(topology):
    return ["%s_%s" % (switch, stat) for switch in topology.switches for stat in RF_STAT_NAMES]


def fit_port_baseline(train_normal, active, link_ports):
    grouped = train_normal.groupby(["switch", "port"])[list(active)]
    means = grouped.mean()
    stds = grouped.std().fillna(0.0).clip(lower=0.0001)
    required = {key for endpoints in link_ports.values() for key in endpoints}
    missing = required - set(means.index)
    if missing:
        raise ValueError("Missing training baseline for candidate link endpoints: %s" % sorted(missing))
    return means, stds


def port_scores(sensor, means, stds, active, experiment_ids=None):
    physical = sensor[sensor["port"] != "LOCAL"]
    if experiment_ids is not None:
        physical = physical[physical["experiment_id"].isin(experiment_ids)]
    chunks = []
    for (switch, port), rows in physical.groupby(["switch", "port"], sort=False):
        key = (switch, port)
        if key not in means.index:
            raise ValueError("No training baseline for observed port %s" % (key,))
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


def rank_topology(scores, exp_id, threshold, topology, link_ports):
    """Rank every candidate link; returns the evidence table with rank components exposed."""
    exp = scores[(scores["experiment_id"] == exp_id) & (scores["phase"] == "fault")].copy()
    if exp.empty:
        raise ValueError("No fault-window data for experiment %s" % exp_id)
    start = exp["timestamp"].min()
    exp = exp[exp["timestamp"] <= start + pd.Timedelta(seconds=EARLY_SECONDS)].copy()
    evidence = {}
    for link in topology.candidate_links:
        endpoints = link_ports[link]
        endpoint_means, onset = [], []
        for switch, port in endpoints:
            rows = exp[(exp["switch"] == switch) & (exp["port"] == port)]
            if rows.empty:
                raise ValueError("Missing candidate endpoint telemetry: %s %s" % (link, (switch, port)))
            endpoint_means.append(float(rows["anomaly_score"].mean()))
            crossed = rows[rows["anomaly_score"] > threshold]
            onset.append(float((crossed["timestamp"].min() - start).total_seconds()) if not crossed.empty else None)
        joint = min(endpoint_means)
        imbalance = abs(endpoint_means[0] - endpoint_means[1])
        pair_onset = max(onset) if all(x is not None for x in onset) else 999.0
        remote_onsets = []
        for switch in topology.remote_switches(link):
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
            "endpoint_a": "%s:%s" % endpoints[0], "endpoint_a_anomaly": endpoint_means[0],
            "endpoint_a_onset_seconds": onset[0] if onset[0] is not None else 999.0,
            "endpoint_b": "%s:%s" % endpoints[1], "endpoint_b_anomaly": endpoint_means[1],
            "endpoint_b_onset_seconds": onset[1] if onset[1] is not None else 999.0,
        }
    table = pd.DataFrame.from_dict(evidence, orient="index")
    utilities = []
    for metric, ascending in RANK_COMPONENTS:
        ranks = table[metric].rank(method="average", ascending=ascending)
        utility = (len(table) + 1.0 - ranks) / len(table)
        table["utility_" + metric] = utility
        utilities.append(utility)
    table["rank_score"] = pd.concat(utilities, axis=1).mean(axis=1)
    table["candidate_link"] = table.index
    table = table.sort_values(["rank_score", "link_anomaly", "endpoint_mean_anomaly"],
                              ascending=[False, False, False], kind="mergesort")
    return table


def stable_rf_ranking(model, vector):
    probabilities = model.predict_proba(vector.reshape(1, -1))[0]
    pairs = sorted(zip(model.classes_, probabilities), key=lambda item: (-float(item[1]), str(item[0])))
    return [str(label) for label, _ in pairs], {str(label): float(prob) for label, prob in pairs}


def fold_inputs(frame, labels, held_out, train_ids, topology, link_ports):
    """Everything a fold needs; used by the evaluator and by the XAI module (identical fits)."""
    sensor = frame[["experiment_id", "timestamp", "switch", "port", "phase", *METRICS]].copy()
    train_ids = set(train_ids)
    if held_out in train_ids:
        raise AssertionError("Held-out experiment leaked into training")
    train_normal, active, constant = fit_active_metrics(sensor, train_ids)
    rf_sensor = switch_level_frame(sensor, active)
    switch_means, switch_stds = fit_switch_baseline(rf_sensor, train_ids, active, topology)
    ordered_train = sorted(train_ids)
    x_train = np.vstack([make_rf_vector(rf_sensor, exp, switch_means, switch_stds, active, topology) for exp in ordered_train])
    y_train = np.asarray([labels[exp] for exp in ordered_train])
    if x_train.shape[1] != len(topology.switches) * len(RF_STAT_NAMES):
        raise AssertionError("Unexpected RF feature dimension")
    x_test = make_rf_vector(rf_sensor, held_out, switch_means, switch_stds, active, topology)
    port_means, port_stds = fit_port_baseline(train_normal, active, link_ports)
    train_normal_scores = port_scores(train_normal, port_means, port_stds, active)
    threshold = float(train_normal_scores["anomaly_score"].quantile(NORMAL_THRESHOLD_QUANTILE))
    held_out_scores = port_scores(sensor, port_means, port_stds, active, {held_out})
    return {
        "active": active, "constant": constant, "train_ids": ordered_train,
        "x_train": x_train, "y_train": y_train, "x_test": x_test,
        "feature_names": rf_feature_names(topology),
        "threshold": threshold, "held_out_scores": held_out_scores,
        "switch_means": switch_means, "switch_stds": switch_stds,
    }


def fit_rf(x_train, y_train):
    model = RandomForestClassifier(**RF_PARAMS)
    model.fit(x_train, y_train)
    return model


def ranking_record(ranking, scores, actual, candidate_links):
    if len(ranking) != len(candidate_links) or set(ranking) != set(candidate_links):
        raise AssertionError("Ranking omitted or duplicated candidate links")
    rank = ranking.index(actual) + 1
    groups = {}
    for link in ranking:
        groups.setdefault(round(scores[link], 12), []).append(link)
    tied = [links for links in groups.values() if len(links) > 1]
    return {
        "rank": rank, "reciprocal_rank": 1.0 / rank,
        "rank1_link": ranking[0], "rank2_link": ranking[1] if len(ranking) > 1 else "",
        "rank3_link": ranking[2] if len(ranking) > 2 else "",
        "top1_hit": rank == 1, "top2_hit": rank <= 2, "top3_hit": rank <= 3,
        "ranking_json": json.dumps(ranking), "scores_json": json.dumps(scores, separators=(",", ":")),
        "score_ties": json.dumps(tied),
    }


def summarize(rows, candidate_links):
    """Experiment-level metrics for an arbitrary number of candidate links."""
    total = len(rows)
    if not total:
        raise ValueError("Cannot summarize an empty prediction set")
    ranks = [int(row["rank"]) for row in rows]
    actuals = [row["actual_link"] for row in rows]
    predicted = [row["rank1_link"] for row in rows]
    k = len(candidate_links)
    per_class = {}
    for link in candidate_links:
        support = sum(a == link for a in actuals)
        hits = sum(a == link and p == link for a, p in zip(actuals, predicted))
        predicted_count = sum(p == link for p in predicted)
        precision = hits / predicted_count if predicted_count else 0.0
        recall = hits / support if support else 0.0
        per_class[link] = {
            "support": support, "top1_precision": precision, "top1_recall": recall,
            "top1_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "top2_recall": sum(a == link and r <= 2 for a, r in zip(actuals, ranks)) / support if support else 0.0,
            "mean_rank": float(np.mean([r for a, r in zip(actuals, ranks) if a == link])) if support else None,
        }
    confusion = [[sum(a == actual and p == pred for a, p in zip(actuals, predicted)) for pred in candidate_links]
                 for actual in candidate_links]
    top1 = sum(r == 1 for r in ranks)
    top2 = sum(r <= 2 for r in ranks)
    top3 = sum(r <= 3 for r in ranks)
    errors = [{"experiment_id": row["experiment_id"], "actual_link": row["actual_link"], "rank1_link": row["rank1_link"],
               "rank": int(row["rank"]), "distance_in_links": abs(candidate_links.index(row["actual_link"]) - candidate_links.index(row["rank1_link"]))}
              for row in rows if row["rank1_link"] != row["actual_link"]]
    return {
        "support": total, "candidate_count": k,
        "top1_count": top1, "top1": top1 / total, "top1_wilson95": wilson_interval(top1, total),
        "top2_count": top2, "top2": top2 / total, "top2_wilson95": wilson_interval(top2, total),
        "top3_count": top3, "top3": top3 / total,
        "mean_rank": float(np.mean(ranks)), "mean_reciprocal_rank": float(np.mean([1.0 / r for r in ranks])),
        "chance_level": {"uniform_top1": 1.0 / k, "uniform_top2": min(1.0, 2.0 / k), "uniform_top3": min(1.0, 3.0 / k),
                         "uniform_mrr": sum(1.0 / r for r in range(1, k + 1)) / k,
                         "note": "Top-k and MRR chance levels fall as the candidate count grows; compare across topologies against these, not raw percentages."},
        "per_class": per_class,
        "confusion_matrix_rows_actual_cols_rank1": confusion, "confusion_labels": list(candidate_links),
        "top1_errors": errors,
        "adjacent_link_error_fraction": (sum(e["distance_in_links"] == 1 for e in errors) / len(errors)) if errors else None,
    }


def evaluate(candidate_dir, switch_count, output_dir, static_mapping=False, dataset=None):
    topology = LinearTopology(switch_count)
    candidate_dir = Path(candidate_dir)
    dataset = Path(dataset) if dataset is not None else candidate_dir / "candidate_dataset.csv"
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError("Refusing to overwrite evaluation directory: %s" % output_dir)
    if not dataset.is_file():
        raise FileNotFoundError(dataset)
    link_ports, mapping_basis = load_link_ports(candidate_dir, topology, static=static_mapping)
    frame, labels = load_candidate(dataset, topology)
    ids = sorted(labels)
    if len(ids) < 3:
        raise ValueError("At least three logical experiments are required, found %d" % len(ids))
    present_links = set(labels.values())
    absent_links = [link for link in topology.candidate_links if link not in present_links]
    predictor_fields = set(METRICS) | set(RF_STAT_NAMES)
    if predictor_fields & FORBIDDEN_PREDICTORS:
        raise AssertionError("Forbidden metadata entered predictor definitions")

    rows, split_rows, feature_rows, component_rows = [], [], [], []
    for fold, (held_out, train_ids) in enumerate(ordered_grouped_splits(ids), start=1):
        inputs = fold_inputs(frame, labels, held_out, train_ids, topology, link_ports)
        feature_rows.append({"fold": fold, "held_out_experiment_id": held_out,
                             "active_metrics": ";".join(inputs["active"]),
                             "excluded_constant_metrics": ";".join(inputs["constant"]),
                             "training_normal_experiments": ";".join(map(str, inputs["train_ids"]))})
        split_rows.append({"fold": fold, "test_experiment_id": held_out,
                           "train_experiment_ids": ";".join(map(str, inputs["train_ids"])),
                           "train_count": len(inputs["train_ids"]), "test_count": 1})
        model = fit_rf(inputs["x_train"], inputs["y_train"])
        rf_ranking, rf_scores = stable_rf_ranking(model, inputs["x_test"])
        # Classes absent from training cannot be ranked by RF; append them last with score 0.
        for link in topology.candidate_links:
            if link not in rf_scores:
                rf_ranking.append(link)
                rf_scores[link] = 0.0
        table = rank_topology(inputs["held_out_scores"], held_out, inputs["threshold"], topology, link_ports)
        topo_ranking = table.index.astype(str).tolist()
        topo_scores = {str(link): float(table.loc[link, "rank_score"]) for link in table.index}
        for position, link in enumerate(topo_ranking, start=1):
            record = {"fold": fold, "experiment_id": held_out, "candidate_link": link, "position": position}
            record.update({key: (float(value) if isinstance(value, (int, float, np.floating, np.integer)) else value)
                           for key, value in table.loc[link].items() if key != "candidate_link"})
            component_rows.append(record)
        actual = labels[held_out]  # label joined only after both rankings exist
        base = {"fold": fold, "experiment_id": held_out, "actual_link": actual,
                "train_experiment_ids": ";".join(map(str, inputs["train_ids"])),
                "active_metrics": ";".join(inputs["active"])}
        rows.append({**base, "method": "rf_baseline", "normal_threshold": "",
                     **ranking_record(rf_ranking, rf_scores, actual, topology.candidate_links)})
        rows.append({**base, "method": "topology_link_ranker", "normal_threshold": inputs["threshold"],
                     **ranking_record(topo_ranking, topo_scores, actual, topology.candidate_links)})
        print("fold %d/%d held out %d" % (fold, len(ids), held_out), file=sys.stderr, flush=True)

    output_dir.mkdir(parents=True, exist_ok=False)
    fields = ["fold", "experiment_id", "method", "actual_link", "rank", "reciprocal_rank", "rank1_link", "rank2_link",
              "rank3_link", "top1_hit", "top2_hit", "top3_hit", "ranking_json", "scores_json", "score_ties",
              "active_metrics", "train_experiment_ids", "normal_threshold"]
    with (output_dir / "grouped_evaluation.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    pd.DataFrame(split_rows).to_csv(output_dir / "split_assignments.csv", index=False, mode="x")
    pd.DataFrame(feature_rows).to_csv(output_dir / "fold_feature_policy.csv", index=False, mode="x")
    pd.DataFrame(component_rows).to_csv(output_dir / "topology_ranker_components.csv", index=False, mode="x")
    methods = {method: summarize([row for row in rows if row["method"] == method], topology.candidate_links)
               for method in ("rf_baseline", "topology_link_ranker")}
    label_counts = {link: sum(v == link for v in labels.values()) for link in topology.candidate_links}
    summary = {
        "protocol": "leave-one-logical-experiment-out (%d folds), grouped by experiment_id; each fold has %d train and 1 test experiment" % (len(ids), len(ids) - 1),
        "task": "conditional fault-window link localization with oracle phase boundaries; not online fault detection/localization",
        "oracle_information": "phase labels select the first 10 seconds from the annotated fault phase; recovery telemetry is excluded; ground-truth fault_location is joined only after predictions",
        "topology": topology.to_metadata(), "candidate_count": topology.candidate_count,
        "link_port_mapping_basis": mapping_basis,
        "link_ports": {link: [list(a), list(b)] for link, (a, b) in link_ports.items()},
        "experiment_ids": ids, "independent_test_experiments": len(ids),
        "class_support": label_counts, "candidate_links_without_experiments": absent_links,
        "dataset_path": str(dataset), "dataset_sha256": sha256(dataset),
        "predictors": {"raw_metrics": list(METRICS), "rf_features": rf_feature_names(topology),
                       "constant_feature_policy": "fit on training-normal non-LOCAL port telemetry only; exclude metrics with no variation in that fold",
                       "topology_features": "per-port absolute z-scores; candidate link endpoint mean, imbalance, threshold onset, and remote propagation margin; equal-weight rank aggregation over all candidates",
                       "forbidden_predictor_fields": sorted(FORBIDDEN_PREDICTORS)},
        "fit_scope": "Each fold's RF, means/stds, active-metric selection, topology threshold (training-normal 95th percentile), and port baselines use only the training experiments.",
        "score_semantics": "RF scores are RandomForest predict_proba outputs (vote fractions, uncalibrated). Topology scores are equal-weight rank utilities in (0, 1], not probabilities.",
        "methods": methods,
        "model": {"type": "RandomForestClassifier", **RF_PARAMS},
        "software": {"python": sys.version, "pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "outputs": {"predictions": "grouped_evaluation.csv", "splits": "split_assignments.csv",
                    "fold_feature_policy": "fold_feature_policy.csv", "ranker_components": "topology_ranker_components.csv"},
    }
    with (output_dir / "evaluation_summary.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    provenance = {"dataset_path": str(dataset), "dataset_sha256": summary["dataset_sha256"],
                  "evaluator_path": str(Path(__file__).resolve()), "evaluator_sha256": sha256(Path(__file__).resolve()),
                  "protocol": summary["protocol"], "task": summary["task"], "python": sys.version,
                  "switch_count": topology.switch_count, "candidate_count": topology.candidate_count,
                  "methods": {m: {k: v for k, v in methods[m].items() if k in ("support", "top1_count", "top2_count", "top3_count", "mean_reciprocal_rank")} for m in methods}}
    with (output_dir / "evaluation_provenance.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(provenance, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True,
                        help="directory with candidate_dataset.csv and link_port_mapping.csv")
    parser.add_argument("--dataset", type=Path, default=None, help="override candidate CSV path")
    parser.add_argument("--switches", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--static-four-switch-mapping", action="store_true",
                        help="use the setup-inferred port mapping (historical four-switch candidate)")
    args = parser.parse_args(argv)
    summary = evaluate(args.candidate_dir, args.switches, args.output_dir,
                       static_mapping=args.static_four_switch_mapping, dataset=args.dataset)
    print(json.dumps({m: {k: summary["methods"][m][k] for k in ("support", "top1_count", "top2_count", "mean_reciprocal_rank")}
                      for m in summary["methods"]}, indent=2))


if __name__ == "__main__":
    main()
