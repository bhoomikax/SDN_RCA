import pandas as pd
import json

INPUT = "master_dataset.csv"
OUTPUT = "graph_dataset_multi.json"

df = pd.read_csv(INPUT)
df["timestamp"] = pd.to_datetime(df["timestamp"])

nodes = ["h1", "s1", "s2", "s3", "s4", "h2"]

edges = [
    ["h1", "s1"],
    ["s1", "s2"],
    ["s2", "s3"],
    ["s3", "s4"],
    ["s4", "h2"]
]

feature_columns = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps"
]

snapshots = []

for experiment_id, exp_df in df.groupby("experiment_id"):

    exp_df = exp_df.sort_values("timestamp")

    for timestamp, time_df in exp_df.groupby("timestamp"):

        node_features = {}

        for node in nodes:

            node_df = time_df[
                time_df["switch"] == node
            ]

            if len(node_df) > 0:

                row = node_df.iloc[0]

                features = [
                    float(row[col])
                    if pd.notna(row[col])
                    else 0.0
                    for col in feature_columns
                ]

            else:
                features = [0.0] * len(feature_columns)

            node_features[node] = features

        phase = time_df["phase"].iloc[0]
        fault_type = time_df["fault_type"].iloc[0]
        fault_location = time_df["fault_location"].iloc[0]

        snapshots.append({
            "experiment_id": int(experiment_id),
            "timestamp": str(timestamp),
            "nodes": nodes,
            "edges": edges,
            "node_features": node_features,
            "phase": phase,
            "fault_type": fault_type,
            "fault_location": fault_location
        })

output = {
    "feature_names": feature_columns,
    "snapshots": snapshots
}

with open(OUTPUT, "w") as f:
    json.dump(output, f, indent=2)

print()
print("GRAPH DATASET CREATED")
print("---------------------")
print("Experiments:", df["experiment_id"].nunique())
print("Snapshots:", len(snapshots))
print("Nodes:", len(nodes))
print("Edges:", len(edges))
print()
print("Phase counts:")
print(df["phase"].value_counts())
print()
print("Saved:", OUTPUT)