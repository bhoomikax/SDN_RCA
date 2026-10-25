"""Graph, temporal, and graph-temporal link localizers for N-switch linear topologies.

Same architectures, optimizer, seeds, and training loop as
evaluate_graph_temporal_link_rca.py, parameterized by the topology's node
count and candidate links. With the four-switch topology the parameter shapes
and construction order are identical to the original module, so fixed seeds
reproduce its results. Scores are softmax outputs: uncalibrated ranking scores,
not probabilities.
"""

import hashlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv

from linear_topology import LinearTopology


EARLY_SECONDS = 10
SEEDS = [17, 42, 2026]
EPOCHS = 100
EMBEDDING = 12
HIDDEN = 16
LSTM_HIDDEN = 24
LEARNING_RATE = 0.01
WEIGHT_DECAY = 1e-3


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_examples(graph_path, topology):
    """Oracle-window sequences per experiment: first ten seconds of the annotated fault phase."""
    payload = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise ValueError("Expected corrected graph snapshot schema_version 2")
    if payload.get("port_aggregation") != "sum over all numbered non-LOCAL ports per switch and timestamp":
        raise ValueError("Unexpected graph feature aggregation policy")
    feature_names = payload.get("feature_names")
    if not feature_names or any(not isinstance(name, str) for name in feature_names):
        raise ValueError("Graph feature names are missing or invalid")
    node_order = list(topology.nodes)
    links = list(topology.candidate_links)
    if payload.get("topology") is not None and payload["topology"].get("switch_count") != topology.switch_count:
        raise ValueError("Graph artifact was built for a different topology")
    grouped = {}
    for snapshot in payload.get("snapshots", []):
        if snapshot.get("nodes") != node_order or snapshot.get("edges") is None:
            raise ValueError("Graph nodes do not match the %d-switch topology" % topology.switch_count)
        stamp = datetime.fromisoformat(snapshot["timestamp"])
        grouped.setdefault(int(snapshot["experiment_id"]), []).append((stamp, snapshot))
    node_to_idx = {node: idx for idx, node in enumerate(node_order)}
    examples = {}
    for experiment_id, values in grouped.items():
        values.sort(key=lambda item: item[0])
        fault_values = [(stamp, snap) for stamp, snap in values if snap.get("phase") == "fault"]
        if not fault_values:
            raise ValueError("Experiment %d has no annotated fault window" % experiment_id)
        start = fault_values[0][0]
        selected = [(stamp, snap) for stamp, snap in fault_values if stamp <= start + timedelta(seconds=EARLY_SECONDS)]
        labels = {snap.get("fault_location") for _, snap in selected}
        if len(labels) != 1 or next(iter(labels)) not in links:
            raise ValueError("Experiment %d has missing/inconsistent link labels" % experiment_id)
        sequence = []
        for _, snapshot in selected:
            matrix = np.asarray([snapshot["node_features"][node] for node in node_order], dtype=np.float32)
            if matrix.shape != (len(node_order), len(feature_names)) or not np.isfinite(matrix).all():
                raise ValueError("Invalid graph feature matrix for experiment %d" % experiment_id)
            edge_index = []
            for source, target in snapshot["edges"]:
                if source not in node_to_idx or target not in node_to_idx:
                    raise ValueError("Topology edge references an unknown node")
                edge_index.extend([[node_to_idx[source], node_to_idx[target]], [node_to_idx[target], node_to_idx[source]]])
            sequence.append({"x": matrix, "edge_index": np.asarray(edge_index, dtype=np.int64).T})
        examples[experiment_id] = {"sequence": sequence, "label": links.index(next(iter(labels)))}
    return examples, feature_names, payload


def fit_feature_policy(examples, train_ids, topology):
    indices = topology.switch_indices
    stacked = np.concatenate([
        np.concatenate([graph["x"][indices] for graph in examples[experiment_id]["sequence"]], axis=0)
        for experiment_id in train_ids
    ], axis=0)
    means = stacked.mean(axis=0)
    stds = stacked.std(axis=0)
    active = [idx for idx, std in enumerate(stds) if std > 1e-12]
    if not active:
        raise ValueError("All graph features are constant in training fault-window telemetry")
    return active, means[active], stds[active]


def normalize_sequence(sequence, active, means, stds, topology):
    indices = topology.switch_indices
    normalized = []
    for graph in sequence:
        x = graph["x"][:, active].copy()
        x[indices] = (x[indices] - means) / stds
        normalized.append({"x": torch.tensor(x, dtype=torch.float32),
                           "edge_index": torch.tensor(graph["edge_index"], dtype=torch.long)})
    return normalized


class GraphEncoder(nn.Module):
    def __init__(self, input_dim, hidden=HIDDEN, embedding=EMBEDDING):
        super().__init__()
        self.conv1 = GCNConv(input_dim, hidden)
        self.conv2 = GCNConv(hidden, embedding)

    def forward(self, graph):
        x = torch.relu(self.conv1(graph["x"], graph["edge_index"]))
        x = torch.relu(self.conv2(x, graph["edge_index"]))
        return x.reshape(-1)


class GraphOnly(nn.Module):
    def __init__(self, input_dim, classes, num_nodes):
        super().__init__()
        self.encoder = GraphEncoder(input_dim)
        self.head = nn.Linear(num_nodes * EMBEDDING, classes)

    def forward(self, sequence):
        representation = torch.stack([self.encoder(graph) for graph in sequence]).mean(dim=0)
        return self.head(representation)


class TemporalOnly(nn.Module):
    def __init__(self, input_dim, classes, num_nodes):
        super().__init__()
        self.lstm = nn.LSTM(num_nodes * input_dim, LSTM_HIDDEN, batch_first=True)
        self.head = nn.Linear(LSTM_HIDDEN, classes)

    def forward(self, sequence):
        values = torch.stack([graph["x"].reshape(-1) for graph in sequence]).unsqueeze(0)
        output, _ = self.lstm(values)
        return self.head(output[:, -1, :]).squeeze(0)


class GraphTemporal(nn.Module):
    def __init__(self, input_dim, classes, num_nodes):
        super().__init__()
        self.encoder = GraphEncoder(input_dim)
        self.lstm = nn.LSTM(num_nodes * EMBEDDING, LSTM_HIDDEN, batch_first=True)
        self.head = nn.Linear(LSTM_HIDDEN, classes)

    def forward(self, sequence):
        embeddings = torch.stack([self.encoder(graph) for graph in sequence]).unsqueeze(0)
        output, _ = self.lstm(embeddings)
        return self.head(output[:, -1, :]).squeeze(0)


MODEL_FACTORIES = {"graph_only": GraphOnly, "temporal_only": TemporalOnly, "graph_temporal": GraphTemporal}
MODEL_LABELS = {"graph_only": "GCN", "temporal_only": "LSTM", "graph_temporal": "GCN+LSTM"}


def score_ranking(scores, actual, links):
    ranked = sorted(range(len(links)), key=lambda idx: (-float(scores[idx]), links[idx]))
    return ranked, ranked.index(actual) + 1


def build_model(model_name, input_dim, topology, seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    return MODEL_FACTORIES[model_name](input_dim, topology.candidate_count, len(topology.nodes))


def train_and_predict(examples, active, means, stds, seed, model_name, topology, train_ids, test_ids,
                      checkpoint_path=None):
    links = list(topology.candidate_links)
    model = build_model(model_name, len(active), topology, seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    criterion = nn.CrossEntropyLoss()
    train_data = [(normalize_sequence(examples[exp_id]["sequence"], active, means, stds, topology),
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
            sequence = normalize_sequence(examples[exp_id]["sequence"], active, means, stds, topology)
            scores = torch.softmax(model(sequence), dim=0).cpu().numpy()
            ranked, rank = score_ranking(scores, examples[exp_id]["label"], links)
            ranking = [links[idx] for idx in ranked]
            predictions.append({
                "seed": seed, "method": model_name, "experiment_id": exp_id,
                "actual_link": links[examples[exp_id]["label"]],
                "rank1_link": ranking[0], "rank2_link": ranking[1] if len(ranking) > 1 else "",
                "rank3_link": ranking[2] if len(ranking) > 2 else "", "rank": rank,
                "top1_hit": rank == 1, "top2_hit": rank <= 2, "ranking": ranking,
                "scores": scores.tolist(), "fault_window_snapshots": len(sequence),
            })
    checkpoint_hash = None
    if checkpoint_path is not None:
        checkpoint_path = Path(checkpoint_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "input_features": active,
                    "feature_means": np.asarray(means).tolist(), "feature_stds": np.asarray(stds).tolist(),
                    "seed": seed, "model": model_name, "switch_count": topology.switch_count,
                    "task": "conditional link localization", "train_experiment_ids": list(train_ids),
                    "test_experiment_ids": list(test_ids)}, checkpoint_path)
        checkpoint_hash = sha256(checkpoint_path)
    return predictions, checkpoint_hash, model


def load_checkpoint(path, topology):
    payload = torch.load(path, weights_only=False)
    if payload.get("switch_count") != topology.switch_count:
        raise ValueError("Checkpoint topology mismatch")
    model = build_model(payload["model"], len(payload["input_features"]), topology, payload["seed"])
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model, payload
