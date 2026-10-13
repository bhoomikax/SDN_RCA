import json
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv, global_mean_pool


with open("graph_dataset.json") as f:
    dataset = json.load(f)


nodes = dataset[0]["nodes"]

node_index = {
    node: i
    for i, node in enumerate(nodes)
}


edge_list = []

for source, target in dataset[0]["edges"]:

    edge_list.append([
        node_index[source],
        node_index[target]
    ])

    edge_list.append([
        node_index[target],
        node_index[source]
    ])


edge_index = torch.tensor(
    edge_list,
    dtype=torch.long
).t().contiguous()


class GCN(torch.nn.Module):

    def __init__(self, input_features, hidden_features, classes):

        super().__init__()

        self.conv1 = GCNConv(
            input_features,
            hidden_features
        )

        self.conv2 = GCNConv(
            hidden_features,
            hidden_features
        )

        self.classifier = torch.nn.Linear(
            hidden_features,
            classes
        )

    def forward(self, x, edge_index, batch):

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

        x = global_mean_pool(
            x,
            batch
        )

        return self.classifier(x)


graphs = []


for snapshot in dataset:

    features = []

    for node in nodes:

        values = snapshot["node_features"].get(
            node,
            [0.0] * 6
        )

        features.append(values)

    x = torch.tensor(
        features,
        dtype=torch.float
    )

    label = 0 if snapshot["phase"] == "normal" else 1

    graph = Data(
        x=x,
        edge_index=edge_index,
        y=torch.tensor([label])
    )

    graphs.append(graph)


split = int(len(graphs) * 0.8)

train_graphs = graphs[:split]
test_graphs = graphs[split:]


model = GCN(
    input_features=6,
    hidden_features=32,
    classes=2
)

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=0.01
)


for epoch in range(1, 101):

    model.train()

    total_loss = 0

    for graph in train_graphs:

        optimizer.zero_grad()

        batch = torch.zeros(
            graph.x.shape[0],
            dtype=torch.long
        )

        output = model(
            graph.x,
            graph.edge_index,
            batch
        )

        loss = F.cross_entropy(
            output,
            graph.y
        )

        loss.backward()

        optimizer.step()

        total_loss += loss.item()


    if epoch % 10 == 0:

        print(
            "Epoch:",
            epoch,
            "Loss:",
            round(
                total_loss / len(train_graphs),
                4
            )
        )


model.eval()

correct = 0

with torch.no_grad():

    for graph in test_graphs:

        batch = torch.zeros(
            graph.x.shape[0],
            dtype=torch.long
        )

        output = model(
            graph.x,
            graph.edge_index,
            batch
        )

        prediction = output.argmax(
            dim=1
        ).item()

        if prediction == graph.y.item():
            correct += 1


accuracy = correct / len(test_graphs)

print("")
print("GCN TRAINING COMPLETE")
print("Training graphs:", len(train_graphs))
print("Test graphs:", len(test_graphs))
print("Test accuracy:", round(accuracy, 4))