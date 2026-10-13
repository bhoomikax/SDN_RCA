
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

DATA = "master_dataset.csv"
METRICS = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
]
SWITCHES = ["s1", "s2", "s3", "s4"]
LINKS = {
    "s1-s2": ("s1", "s2"),
    "s2-s3": ("s2", "s3"),
    "s3-s4": ("s3", "s4"),
}

df = pd.read_csv(DATA)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Aggregate port telemetry into switch-level time snapshots.
agg = df.groupby(
    ["experiment_id", "timestamp", "switch", "phase", "fault_location"],
    as_index=False
)[METRICS].mean()

labels = (
    df[df["phase"] == "fault"]
    .groupby("experiment_id")["fault_location"]
    .first()
)
labels = labels[labels.isin(LINKS)]

train_ids, test_ids = train_test_split(
    labels.index.to_numpy(),
    test_size=0.30,
    random_state=42,
    stratify=labels.to_numpy()
)

train_ids, test_ids = set(train_ids), set(test_ids)

# Use only training experiments to estimate normal behavior.
normal = agg[
    agg["experiment_id"].isin(train_ids)
    & (agg["phase"] == "normal")
]
baseline = normal.groupby("switch")[METRICS].mean()
std = normal.groupby("switch")[METRICS].std().fillna(0.0001).clip(lower=0.0001)

def switch_scores(exp_id):
    exp = agg[agg["experiment_id"] == exp_id]
    fault = exp[exp["phase"] == "fault"]
    if fault.empty:
        return {}

    start = fault["timestamp"].min()
    early = fault[fault["timestamp"] <= start + pd.Timedelta(seconds=10)]
    result = {}

    for sw in SWITCHES:
        data = early[early["switch"] == sw]
        if data.empty or sw not in baseline.index:
            result[sw] = 0.0
            continue

        z = (
            (data[METRICS] - baseline.loc[sw, METRICS]).abs()
            / std.loc[sw, METRICS]
        )
        # Clip extreme z-scores so one noisy metric doesn't dominate.
        scores = z.mean(axis=1).clip(upper=20)
        result[sw] = float(scores.mean())

    return result

def rank_links(scores):
    ranked = []
    for link, (u, v) in LINKS.items():
        # A link is suspicious when both endpoints show anomalies.
        endpoint_score = (scores.get(u, 0) + scores.get(v, 0)) / 2

        # Add a small penalty when the anomaly difference is very large.
        mismatch = abs(scores.get(u, 0) - scores.get(v, 0))
        score = endpoint_score - 0.1 * mismatch
        ranked.append((link, score))

    return sorted(ranked, key=lambda item: item[1], reverse=True)

top1_hits = 0
top2_hits = 0
count = 0

print("TOPOLOGY-AWARE RCA")
print("==================")

for exp_id in sorted(test_ids):
    actual = labels.loc[exp_id]
    scores = switch_scores(exp_id)
    ranking = rank_links(scores)

    if not ranking:
        continue

    predicted = ranking[0][0]
    top_links = [link for link, _ in ranking]
    top1_hits += predicted == actual
    top2_hits += actual in top_links[:2]
    count += 1

    print(
        f"Experiment {exp_id}: actual={actual}, "
        f"predicted={predicted}, ranking={top_links}"
    )

if count:
    print("\nTop-1 accuracy:", f"{top1_hits / count:.2%}")
    print("Top-2 accuracy:", f"{top2_hits / count:.2%}")
    print("Test experiments:", count)
