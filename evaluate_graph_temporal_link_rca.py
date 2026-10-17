"""Evaluate graph, temporal, and graph-temporal link classifiers on one fixed split.

This is conditional fault-window localization: the annotated fault phase selects
the first ten seconds of each fault segment. Labels and phase fields are kept
outside model inputs. It is not an online detector. Existing RF/topology results
are read for same-split comparison; all new outputs are written exclusively.
"""

import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv


ROOT = Path(__file__).resolve().parent
DEFAULT_GRAPH = ROOT / "derived_graphs" / "candidate_v2_portsum" / "graph_dataset.json"
DEFAULT_CANDIDATE = ROOT / "derived_datasets" / "candidate_with_reaudited_physical21_and_physical23_v2" / "candidate_dataset.csv"
DEFAULT_REFERENCE = ROOT / "evaluations" / "recollected_13_6_split_v4" / "topology_link_rca_results.csv"
DEFAULT_OUTPUT = ROOT / "evaluations" / "graph_temporal_link_localization_v1"
TRAIN_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 14, 17, 19]
TEST_IDS = [10, 11, 12, 15, 16, 18]
LINKS = ["s1-s2", "s2-s3", "s3-s4"]
NODE_ORDER = ["h1", "s1", "s2", "s3", "s4", "h2"]
SWITCH_INDICES = [1, 2, 3, 4]
EARLY_SECONDS = 10
SEEDS = [17, 42, 2026]
EPOCHS = 100


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_examples(graph_path):
    payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("Expected corrected graph snapshot schema_version 2")
    if payload.get("port_aggregation") != "sum over all numbered non-LOCAL ports per switch and timestamp":
        raise ValueError("Unexpected graph feature aggregation policy")
    feature_names = payload.get("feature_names")
    if not feature_names or any(not isinstance(name, str) for name in feature_names):
        raise ValueError("Graph feature names are missing or invalid")
    grouped = {}
    for snapshot in payload.get("snapshots", []):
        if snapshot.get("nodes") != NODE_ORDER or snapshot.get("edges") is None:
            raise ValueError("Unexpected graph nodes or missing topology edges")
        stamp = datetime.fromisoformat(snapshot["timestamp"])
        grouped.setdefault(int(snapshot["experiment_id"]), []).append((stamp, snapshot))
    examples = {}
    for experiment_id, values in grouped.items():
        values.sort(key=lambda item: item[0])
        fault_values = [(stamp, snap) for stamp, snap in values if snap.get("phase") == "fault"]
        if not fault_values:
            raise ValueError(f"Experiment {experiment_id} has no annotated fault window")
        start = fault_values[0][0]
        selected = [(stamp, snap) for stamp, snap in fault_values
                    if stamp <= start + timedelta(seconds=EARLY_SECONDS)]
        labels = {snap.get("fault_location") for _, snap in selected}
        if len(labels) != 1 or next(iter(labels)) not in LINKS:
            raise ValueError(f"Experiment {experiment_id} has missing/inconsistent link labels")
        sequence = []
        for _, snapshot in selected:
            matrix = np.asarray([snapshot["node_features"][node] for node in NODE_ORDER], dtype=np.float32)
            if matrix.shape != (len(NODE_ORDER), len(feature_names)) or not np.isfinite(matrix).all():
                raise ValueError(f"Invalid graph feature matrix for experiment {experiment_id}")
            edge_index = []
            node_to_idx = {node: idx for idx, node in enumerate(NODE_ORDER)}
            for source, target in snapshot["edges"]:
                if source not in node_to_idx or target not in node_to_idx:
                    raise ValueError("Topology edge references an unknown node")
                edge_index.extend([[node_to_idx[source], node_to_idx[target]],
                                   [node_to_idx[target], node_to_idx[source]]])
            sequence.append({"x": matrix, "edge_index": np.asarray(edge_index, dtype=np.int64).T})
        examples[experiment_id] = {"sequence": sequence, "label": LINKS.index(next(iter(labels)))}
    return examples, feature_names, payload


def fit_feature_policy(examples, train_ids=None):
    if train_ids is None:
        train_ids = TRAIN_IDS
    training = [examples[experiment_id] for experiment_id in train_ids]
    stacked = np.concatenate([
        np.concatenate([graph["x"][SWITCH_INDICES] for graph in item["sequence"]], axis=0)
        for item in training
    ], axis=0)
    means = stacked.mean(axis=0)
    stds = stacked.std(axis=0)
    active = [idx for idx, std in enumerate(stds) if std > 1e-12]
    if not active:
        raise ValueError("All graph features are constant in training fault-window telemetry")
    return active, means[active], stds[active]


def normalize_sequence(sequence, active, means, stds):
    normalized = []
    for graph in sequence:
        x = graph["x"][:, active].copy()
        # Hosts have no telemetry; keep their explicit zero/missing values at zero.
        x[SWITCH_INDICES] = (x[SWITCH_INDICES] - means) / stds
        normalized.append({"x": torch.tensor(x, dtype=torch.float32),
                           "edge_index": torch.tensor(graph["edge_index"], dtype=torch.long)})
    return normalized


class GraphEncoder(nn.Module):
    def __init__(self, input_dim, hidden=16, embedding=12):
        super().__init__()
        self.conv1 = GCNConv(input_dim, hidden)
        self.conv2 = GCNConv(hidden, embedding)

    def forward(self, graph):
        x = torch.relu(self.conv1(graph["x"], graph["edge_index"]))
        x = torch.relu(self.conv2(x, graph["edge_index"]))
        return x.reshape(-1)


class GraphOnly(nn.Module):
    def __init__(self, input_dim, classes):
        super().__init__()
        self.encoder = GraphEncoder(input_dim)
        self.head = nn.Linear(6 * 12, classes)

    def forward(self, sequence):
        representation = torch.stack([self.encoder(graph) for graph in sequence]).mean(dim=0)
        return self.head(representation)


class TemporalOnly(nn.Module):
    def __init__(self, input_dim, classes):
        super().__init__()
        self.lstm = nn.LSTM(6 * input_dim, 24, batch_first=True)
        self.head = nn.Linear(24, classes)

    def forward(self, sequence):
        values = torch.stack([graph["x"].reshape(-1) for graph in sequence]).unsqueeze(0)
        output, _ = self.lstm(values)
        return self.head(output[:, -1, :]).squeeze(0)


class GraphTemporal(nn.Module):
    def __init__(self, input_dim, classes):
        super().__init__()
        self.encoder = GraphEncoder(input_dim)
        self.lstm = nn.LSTM(6 * 12, 24, batch_first=True)
        self.head = nn.Linear(24, classes)

    def forward(self, sequence):
        embeddings = torch.stack([self.encoder(graph) for graph in sequence]).unsqueeze(0)
        output, _ = self.lstm(embeddings)
        return self.head(output[:, -1, :]).squeeze(0)


MODEL_FACTORIES = {"graph_only": GraphOnly, "temporal_only": TemporalOnly,
                   "graph_temporal": GraphTemporal}


def score_ranking(scores, actual):
    ranked = sorted(range(len(LINKS)), key=lambda idx: (-float(scores[idx]), LINKS[idx]))
    rank = ranked.index(actual) + 1
    return ranked, rank


def wilson_interval(successes, total, z=1.959963984540054):
    if total <= 0:
        return [None, None]
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * np.sqrt((proportion * (1 - proportion) / total) + z * z / (4 * total * total)) / denominator
    return [max(0.0, float(center - margin)), min(1.0, float(center + margin))]


def train_and_predict(
    examples, active, means, stds, seed, model_name, output_dir,
    train_ids=None, test_ids=None, *, save_checkpoint=True, checkpoint_name=None,
):
    if train_ids is None:
        train_ids = TRAIN_IDS
    if test_ids is None:
        test_ids = TEST_IDS
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    model = MODEL_FACTORIES[model_name](len(active), len(LINKS))
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-3)
    criterion = nn.CrossEntropyLoss()
    train_data = [(normalize_sequence(examples[exp_id]["sequence"], active, means, stds),
                   examples[exp_id]["label"]) for exp_id in train_ids]
    for _ in range(EPOCHS):
        model.train()
        order = list(range(len(train_data)))
        random.shuffle(order)
        for idx in order:
            sequence, label = train_data[idx]
            optimizer.zero_grad()
            loss = criterion(model(sequence), torch.tensor(label, dtype=torch.long))
            loss.backward()
            optimizer.step()
    model.eval()
    predictions = []
    with torch.no_grad():
        for exp_id in test_ids:
            sequence = normalize_sequence(examples[exp_id]["sequence"], active, means, stds)
            scores = torch.softmax(model(sequence), dim=0).cpu().numpy()
            ranked, rank = score_ranking(scores, examples[exp_id]["label"])
            predictions.append({"seed": seed, "method": model_name, "experiment_id": exp_id,
                                "actual_link": LINKS[examples[exp_id]["label"]],
                                "rank1_link": LINKS[ranked[0]], "rank2_link": LINKS[ranked[1]],
                                "rank3_link": LINKS[ranked[2]], "rank": rank,
                                "top1_hit": rank == 1, "top2_hit": rank <= 2,
                                "scores": scores.tolist(), "fault_window_snapshots": len(sequence)})
    checkpoint_hash = None
    if save_checkpoint:
        checkpoint = output_dir / (
            checkpoint_name or f"{model_name}_seed_{seed}.pt"
        )
        torch.save({"state_dict": model.state_dict(), "input_features": active,
                    "feature_means": means.tolist(), "feature_stds": stds.tolist(),
                    "seed": seed, "model": model_name, "task": "conditional link localization",
                    "train_experiment_ids": list(train_ids)}, checkpoint)
        checkpoint_hash = sha256(checkpoint)
    return predictions, checkpoint_hash


def evaluate(graph_path, candidate_path, reference_path, output_dir):
    graph_path, candidate_path, reference_path, output_dir = map(Path, (graph_path, candidate_path, reference_path, output_dir))
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation outputs: {output_dir}")
    if not all(path.is_file() for path in (graph_path, candidate_path, reference_path)):
        raise FileNotFoundError("Graph, candidate dataset, or fixed-split reference result is missing")
    graph_hash = sha256(graph_path)
    candidate_hash = sha256(candidate_path)
    with reference_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reference_rows = list(csv.DictReader(stream))
    for method in ("rf_baseline", "topology_link_ranker"):
        test_rows = [row for row in reference_rows if row["record_type"] == "experiment" and row["method"] == method]
        if [int(row["experiment_id"]) for row in test_rows] != TEST_IDS:
            raise ValueError(f"Reference {method} does not match the established six-experiment split")
    examples, feature_names, payload = prepare_examples(graph_path)
    if not set(TRAIN_IDS + TEST_IDS).issubset(examples):
        raise ValueError("The fixed split references experiments missing from graph data")
    if payload.get("source_sha256") != candidate_hash:
        raise ValueError("Graph snapshots were not built from the supplied candidate dataset")
    active, means, stds = fit_feature_policy(examples)
    output_dir.mkdir(parents=True, exist_ok=False)
    predictions, checkpoint_hashes = [], {}
    for method in MODEL_FACTORIES:
        for seed in SEEDS:
            rows, checkpoint_hashes[f"{method}_seed_{seed}"] = train_and_predict(
                examples, active, means, stds, seed, method, output_dir)
            predictions.extend(rows)
    predictions_path = output_dir / "graph_temporal_predictions.csv"
    fields = ["seed", "method", "experiment_id", "actual_link", "rank1_link", "rank2_link",
              "rank3_link", "rank", "top1_hit", "top2_hit", "fault_window_snapshots", "scores_json"]
    with predictions_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in predictions:
            writer.writerow({**{key: row[key] for key in fields if key != "scores_json"},
                             "scores_json": json.dumps(row["scores"], separators=(",", ":"))})
    methods_summary = {}
    for method in MODEL_FACTORIES:
        per_seed = []
        method_rows = [row for row in predictions if row["method"] == method]
        for seed in SEEDS:
            selected = [row for row in method_rows if row["seed"] == seed]
            top1_count = sum(row["top1_hit"] for row in selected)
            top2_count = sum(row["top2_hit"] for row in selected)
            per_seed.append({"seed": seed, "support": len(selected),
                             "top1": top1_count / len(selected),
                             "top1_wilson95": wilson_interval(top1_count, len(selected)),
                             "top2": top2_count / len(selected),
                             "top2_wilson95": wilson_interval(top2_count, len(selected)),
                             "mrr": sum(1 / row["rank"] for row in selected) / len(selected)})
        per_class = {}
        for link in LINKS:
            class_rows = [row for row in method_rows if row["actual_link"] == link]
            true_positive = sum(row["rank1_link"] == link for row in class_rows)
            predicted_positive = sum(row["rank1_link"] == link for row in method_rows)
            precision = true_positive / predicted_positive if predicted_positive else 0.0
            recall = true_positive / len(class_rows) if class_rows else 0.0
            per_class[link] = {
                "support_across_seeds": len(class_rows),
                "top1_precision": precision,
                "top1_recall": recall,
                "top1_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                "top2_recall": sum(row["rank"] <= 2 for row in class_rows) / len(class_rows) if class_rows else 0.0,
            }
        methods_summary[method] = {
            "per_seed": per_seed,
            "per_class_across_seed_predictions": per_class,
            "mean_top1": statistics.mean(row["top1"] for row in per_seed),
            "sd_top1": statistics.stdev(row["top1"] for row in per_seed),
            "mean_top2": statistics.mean(row["top2"] for row in per_seed),
            "mean_mrr": statistics.mean(row["mrr"] for row in per_seed),
            "confusion_matrix_across_seed_predictions_rows_actual_cols_rank1": [
                [sum(row["actual_link"] == actual and row["rank1_link"] == predicted for row in method_rows)
                 for predicted in LINKS] for actual in LINKS
            ],
        }
    training_counts = {link: sum(examples[exp_id]["label"] == idx for exp_id in TRAIN_IDS)
                       for idx, link in enumerate(LINKS)}
    majority_order = sorted(LINKS, key=lambda link: (-training_counts[link], link))
    majority_top1 = sum(examples[exp_id]["label"] == LINKS.index(majority_order[0]) for exp_id in TEST_IDS) / len(TEST_IDS)
    majority_top2 = sum(LINKS[examples[exp_id]["label"]] in majority_order[:2] for exp_id in TEST_IDS) / len(TEST_IDS)
    reference_methods = {}
    for method in ("rf_baseline", "topology_link_ranker"):
        method_rows = [row for row in reference_rows if row["record_type"] == "experiment" and row["method"] == method]
        top1_count = sum(row["top1_hit"].lower() == "true" for row in method_rows)
        top2_count = sum(row["top2_hit"].lower() == "true" for row in method_rows)
        reference_methods[method] = {
            "top1": top1_count / len(method_rows), "top1_wilson95": wilson_interval(top1_count, len(method_rows)),
            "top2": top2_count / len(method_rows), "top2_wilson95": wilson_interval(top2_count, len(method_rows)),
            "confusion_matrix_rows_actual_cols_rank1": [
                [sum(row["actual_link"] == actual and row["rank1_link"] == predicted for row in method_rows)
                 for predicted in LINKS] for actual in LINKS
            ],
        }
    summary = {
        "task": "conditional fault-window link localization; annotated phase selects first 10 seconds",
        "online_detection": False,
        "train_experiment_ids": TRAIN_IDS, "test_experiment_ids": TEST_IDS,
        "class_support_test": {link: sum(examples[exp_id]["label"] == idx for exp_id in TEST_IDS)
                               for idx, link in enumerate(LINKS)},
        "candidate_dataset_sha256": candidate_hash, "graph_snapshot_sha256": graph_hash,
        "graph_schema_version": payload["schema_version"], "feature_names": feature_names,
        "active_training_features": [feature_names[idx] for idx in active],
        "constant_training_features_excluded": [name for idx, name in enumerate(feature_names) if idx not in active],
        "normalization_fit": "training fault-window switch-node values only; host zero/missing values left at zero",
        "methods": methods_summary,
        "simple_baselines": {
            "training_majority_link_order": majority_order,
            "majority_top1": majority_top1,
            "majority_top2": majority_top2,
            "uniform_random_expected_top1": 1 / 3,
            "uniform_random_expected_top2": 2 / 3,
            "uniform_random_expected_mrr": 11 / 18,
        },
        "reference_same_split_results": reference_methods,
        "configuration": {"seeds": SEEDS, "epochs": EPOCHS, "learning_rate": 0.01,
                          "weight_decay": 0.001, "window_seconds": EARLY_SECONDS},
        "checkpoint_sha256": checkpoint_hashes,
        "feature_label_separation": "fault location used only as target; excluded from tensors; phase used only to select the oracle-assisted fault window",
        "limitations": ["13 training and 6 test experiments; exploratory neural results",
                        "same fixed split is small and results are uncertain",
                        "Wilson intervals use six independent test experiments, not seed repeats",
                        "conditional localization only; not phase-blind online RCA",
                        "no test-label tuning; three seeds are initialization sensitivity, not independent data replications"],
        "python": sys.version,
        "torch": torch.__version__,
    }
    with (output_dir / "evaluation_summary.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    summary = evaluate(args.graph, args.candidate, args.reference, args.output_dir)
    print(json.dumps(summary["methods"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
