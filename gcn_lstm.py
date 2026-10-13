import json
import random

import torch
import torch.nn as nn
import torch.nn.functional as F

from torch_geometric.nn import GCNConv


# ============================================================
# SETTINGS
# ============================================================

INPUT = "graph_dataset_multi.json"

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)

SEQUENCE_LENGTH = 5
HIDDEN_GCN = 32
EMBEDDING_SIZE = 16
LSTM_HIDDEN = 32

EPOCHS = 100
LEARNING_RATE = 0.001


# ============================================================
# LOAD DATA
# ============================================================

with open(INPUT, "r") as f:
    dataset = json.load(f)

snapshots = dataset["snapshots"]

print()
print("LOADED DATA")
print("-----------")
print("Snapshots:", len(snapshots))


# ============================================================
# GCN
# ============================================================

class GCN(nn.Module):

    def __init__(self):

        super().__init__()

        self.conv1 = GCNConv(
            4,
            HIDDEN_GCN
        )

        self.conv2 = GCNConv(
            HIDDEN_GCN,
            EMBEDDING_SIZE
        )

    def forward(
        self,
        x,
        edge_index
    ):

        x = self.conv1(
            x,
            edge_index
        )

        x = F.relu(x)

        x = self.conv2(
            x,
            edge_index
        )

        x = F.relu(x)

        # Convert node embeddings into one graph embedding
        graph_embedding = x.mean(
            dim=0
        )

        return graph_embedding


# ============================================================
# GCN + LSTM
# ============================================================

class GCN_LSTM(nn.Module):

    def __init__(self):

        super().__init__()

        self.gcn = GCN()

        self.lstm = nn.LSTM(
            input_size=EMBEDDING_SIZE,
            hidden_size=LSTM_HIDDEN,
            batch_first=True
        )

        self.classifier = nn.Linear(
            LSTM_HIDDEN,
            2
        )

    def forward(
        self,
        sequence
    ):

        embeddings = []

        for graph in sequence:

            embedding = self.gcn(
                graph["x"],
                graph["edge_index"]
            )

            embeddings.append(
                embedding
            )

        embeddings = torch.stack(
            embeddings
        )

        embeddings = embeddings.unsqueeze(0)

        lstm_output, _ = self.lstm(
            embeddings
        )

        final_output = lstm_output[
            :, -1, :
        ]

        return self.classifier(
            final_output
        )


# ============================================================
# CONVERT SNAPSHOT TO GRAPH
# ============================================================

def create_graph(snapshot):

    nodes = snapshot["nodes"]

    node_features = []

    for node in nodes:

        node_features.append(
            snapshot["node_features"][node]
        )

    x = torch.tensor(
        node_features,
        dtype=torch.float
    )

    node_to_id = {
        node: i
        for i, node in enumerate(nodes)
    }

    edge_list = []

    for source, target in snapshot["edges"]:

        s = node_to_id[source]
        t = node_to_id[target]

        edge_list.append([s, t])
        edge_list.append([t, s])

    edge_index = torch.tensor(
        edge_list,
        dtype=torch.long
    ).t().contiguous()

    return {
        "x": x,
        "edge_index": edge_index
    }


# ============================================================
# CREATE TEMPORAL SEQUENCES
# ============================================================

sequences = []

for experiment_id in sorted(
    set(
        s["experiment_id"]
        for s in snapshots
    )
):

    experiment_snapshots = [
        s for s in snapshots
        if s["experiment_id"] == experiment_id
    ]

    experiment_snapshots.sort(
        key=lambda x: x["timestamp"]
    )

    for i in range(
        SEQUENCE_LENGTH,
        len(experiment_snapshots)
    ):

        sequence_snapshots = (
            experiment_snapshots[
                i - SEQUENCE_LENGTH:i
            ]
        )

        target_snapshot = (
            experiment_snapshots[i]
        )

        sequence = [
            create_graph(s)
            for s in sequence_snapshots
        ]

        # Normal = 0
        # Fault = 1
        label = (
            0
            if target_snapshot["phase"] == "normal"
            else 1
        )

        sequences.append(
            (
                sequence,
                label,
                experiment_id
            )
        )


print()
print("TEMPORAL DATA")
print("-------------")
print("Sequences:", len(sequences))


# ============================================================
# SPLIT BY EXPERIMENT
# ============================================================

experiment_ids = sorted(
    set(
        experiment_id
        for _, _, experiment_id in sequences
    )
)

random.shuffle(experiment_ids)

split = int(
    len(experiment_ids) * 0.8
)

train_experiments = set(
    experiment_ids[:split]
)

test_experiments = set(
    experiment_ids[split:]
)

train_sequences = [
    item
    for item in sequences
    if item[2] in train_experiments
]

test_sequences = [
    item
    for item in sequences
    if item[2] in test_experiments
]


print()
print("EXPERIMENT SPLIT")
print("----------------")
print(
    "Training:",
    sorted(train_experiments)
)

print(
    "Testing:",
    sorted(test_experiments)
)

print(
    "Training sequences:",
    len(train_sequences)
)

print(
    "Testing sequences:",
    len(test_sequences)
)


# ============================================================
# MODEL
# ============================================================

device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print()
print("Device:", device)

model = GCN_LSTM().to(device)

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=LEARNING_RATE
)

criterion = nn.CrossEntropyLoss()


# ============================================================
# TRAIN
# ============================================================

for epoch in range(
    1,
    EPOCHS + 1
):

    model.train()

    random.shuffle(
        train_sequences
    )

    total_loss = 0

    for sequence, label, _ in train_sequences:

        sequence = [
            {
                "x": g["x"].to(device),
                "edge_index": g["edge_index"].to(device)
            }
            for g in sequence
        ]

        target = torch.tensor(
            [label],
            dtype=torch.long,
            device=device
        )

        optimizer.zero_grad()

        output = model(
            sequence
        )

        loss = criterion(
            output,
            target
        )

        loss.backward()

        optimizer.step()

        total_loss += loss.item()

    if epoch == 1 or epoch % 10 == 0:

        print(
            f"Epoch {epoch:03d} "
            f"Loss: {total_loss:.4f}"
        )


# ============================================================
# TEST
# ============================================================

model.eval()

correct = 0
total = 0

with torch.no_grad():

    for sequence, label, _ in test_sequences:

        sequence = [
            {
                "x": g["x"].to(device),
                "edge_index": g["edge_index"].to(device)
            }
            for g in sequence
        ]

        output = model(
            sequence
        )

        prediction = output.argmax(
            dim=1
        ).item()

        if prediction == label:
            correct += 1

        total += 1


accuracy = (
    correct / total
    if total > 0
    else 0
)

print()
print("==============================")
print("GCN + LSTM RESULTS")
print("==============================")

print(
    f"Test accuracy: "
    f"{accuracy * 100:.2f}%"
)

torch.save(
    model.state_dict(),
    "gcn_lstm.pth"
)

print()
print("Saved model: gcn_lstm.pth")