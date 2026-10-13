import json
import random

import torch
import torch.nn as nn
import torch.nn.functional as F

from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
from torch_geometric.nn import GCNConv


# ============================================================
# SETTINGS
# ============================================================

INPUT = "graph_dataset_multi.json"

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)

EPOCHS = 100
BATCH_SIZE = 16
LEARNING_RATE = 0.001


# ============================================================
# LOAD GRAPH DATA
# ============================================================

with open(INPUT, "r") as f:
    dataset = json.load(f)

snapshots = dataset["snapshots"]

print()
print("LOADED GRAPH DATA")
print("-----------------")
print("Snapshots:", len(snapshots))


# ============================================================
# CONVERT JSON → PYTORCH GEOMETRIC GRAPHS
# ============================================================

graphs = []

for snapshot in snapshots:

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

        # Undirected graph
        edge_list.append([s, t])
        edge_list.append([t, s])

    edge_index = torch.tensor(
        edge_list,
        dtype=torch.long
    ).t().contiguous()

    # Normal = 0
    # Fault = 1
    label = 0 if snapshot["phase"] == "normal" else 1

    graph = Data(
        x=x,
        edge_index=edge_index,
        y=torch.tensor([label], dtype=torch.long)
    )

    graphs.append(graph)


# ============================================================
# SPLIT BY EXPERIMENT
# ============================================================

# Get experiment IDs
experiment_ids = sorted(
    set(
        snapshot["experiment_id"]
        for snapshot in snapshots
    )
)

random.shuffle(experiment_ids)

split = int(len(experiment_ids) * 0.8)

train_experiments = set(
    experiment_ids[:split]
)

test_experiments = set(
    experiment_ids[split:]
)

train_graphs = []
test_graphs = []

for snapshot, graph in zip(snapshots, graphs):

    exp_id = snapshot["experiment_id"]

    if exp_id in train_experiments:
        train_graphs.append(graph)
    else:
        test_graphs.append(graph)


print()
print("EXPERIMENT SPLIT")
print("----------------")
print("Training experiments:", sorted(train_experiments))
print("Testing experiments:", sorted(test_experiments))
print("Training graphs:", len(train_graphs))
print("Testing graphs:", len(test_graphs))


train_loader = DataLoader(
    train_graphs,
    batch_size=BATCH_SIZE,
    shuffle=True
)

test_loader = DataLoader(
    test_graphs,
    batch_size=BATCH_SIZE,
    shuffle=False
)


# ============================================================
# GCN MODEL
# ============================================================

class GCN(nn.Module):

    def __init__(self):

        super().__init__()

        self.conv1 = GCNConv(
            4,
            32
        )

        self.conv2 = GCNConv(
            32,
            16
        )

        self.fc = nn.Linear(
            16,
            2
        )

    def forward(
        self,
        x,
        edge_index,
        batch
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

        # Graph-level representation
        graph_embedding = torch.zeros(
            batch.max().item() + 1,
            x.size(1),
            device=x.device
        )

        graph_embedding.index_add_(
            0,
            batch,
            x
        )

        counts = torch.bincount(batch)

        graph_embedding = (
            graph_embedding /
            counts.unsqueeze(1)
        )

        return self.fc(
            graph_embedding
        )


# ============================================================
# TRAIN
# ============================================================

device = torch.device(
    "cuda" if torch.cuda.is_available()
    else "cpu"
)

print()
print("Device:", device)

model = GCN().to(device)

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=LEARNING_RATE
)

criterion = nn.CrossEntropyLoss()


for epoch in range(1, EPOCHS + 1):

    model.train()

    total_loss = 0

    for batch in train_loader:

        batch = batch.to(device)

        optimizer.zero_grad()

        output = model(
            batch.x,
            batch.edge_index,
            batch.batch
        )

        loss = criterion(
            output,
            batch.y
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

    for batch in test_loader:

        batch = batch.to(device)

        output = model(
            batch.x,
            batch.edge_index,
            batch.batch
        )

        predictions = output.argmax(
            dim=1
        )

        correct += (
            predictions == batch.y
        ).sum().item()

        total += batch.y.size(0)


accuracy = (
    correct / total
    if total > 0
    else 0
)

print()
print("==============================")
print("GCN RESULTS")
print("==============================")
print(
    f"Test accuracy: "
    f"{accuracy * 100:.2f}%"
)

# Save model
torch.save(
    model.state_dict(),
    "gcn_multi.pth"
)

print()
print("Saved model: gcn_multi.pth")