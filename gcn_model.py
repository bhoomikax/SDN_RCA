import json
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv


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

    def __init__(self, input_features, hidden_features, output_features):

        super().__init__()

        self.conv1 = GCNConv(
            input_features,
            hidden_features
        )

        self.conv2 = GCNConv(
            hidden_features,
            output_features
        )

    def forward(self, x, edge_index):

        x = self.conv1(
            x,
            edge_index
        )

        x = F.relu(x)

        x = self.conv2(
            x,
            edge_index
        )

        return x


feature_names = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
    "latency_ms",
    "packet_loss_percent"
]


snapshot = dataset[0]

features = []

for node in nodes:

    values = snapshot["node_features"].get(
        node,
        [0.0] * len(feature_names)
    )

    features.append(values)


x = torch.tensor(
    features,
    dtype=torch.float
)


model = GCN(
    input_features=6,
    hidden_features=16,
    output_features=8
)


output = model(
    x,
    edge_index
)


print("GCN model created successfully")
print("Number of nodes:", x.shape[0])
print("Number of input features:", x.shape[1])
print("Number of edges:", edge_index.shape[1])
print("Embedding shape:", output.shape)
print("")
print("Node embeddings:")
print(output)