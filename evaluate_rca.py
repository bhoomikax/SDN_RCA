
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

INPUT = "master_dataset.csv"

METRICS = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps"
]

SWITCHES = ["s1", "s2", "s3", "s4"]
LABELS = ["s1-s2", "s2-s3", "s3-s4"]

df = pd.read_csv(INPUT)
df["timestamp"] = pd.to_datetime(df["timestamp"])

agg = df.groupby(
    ["experiment_id", "timestamp", "switch", "phase", "fault_location"],
    as_index=False
)[METRICS].mean()

labels = (
    df[df["phase"] == "fault"]
    .groupby("experiment_id")["fault_location"]
    .first()
)
labels = labels[labels.isin(LABELS)]

def make_features(train_ids):
    normal = agg[
        agg["experiment_id"].isin(train_ids)
        & (agg["phase"] == "normal")
    ]

    baseline = normal.groupby("switch")[METRICS].mean()
    std = normal.groupby("switch")[METRICS].std()
    std = std.fillna(0.0001).clip(lower=0.0001)

    result = {}

    for exp_id, exp in agg.groupby("experiment_id"):
        if exp_id not in labels.index:
            continue

        fault = exp[exp["phase"] == "fault"]
        if fault.empty:
            continue

        start = fault["timestamp"].min()
        early = fault[
            fault["timestamp"] <= start + pd.Timedelta(seconds=10)
        ]

        switch_data = {}
        first_times = {}

        for sw in SWITCHES:
            data = early[early["switch"] == sw]

            if data.empty or sw not in baseline.index:
                continue

            z = (
                (data[METRICS] - baseline.loc[sw, METRICS]).abs()
                / std.loc[sw, METRICS]
            )
            scores = z.mean(axis=1).to_numpy()
            times = (
                data["timestamp"] - start
            ).dt.total_seconds().to_numpy()

            anomalous = np.flatnonzero(scores > 1.0)
            first_time = (
                float(times[anomalous[0]])
                if len(anomalous) else 999.0
            )

            switch_data[sw] = [
                float(scores.mean()),
                float(scores.max()),
                float(np.mean(scores > 1.0)),
                first_time
            ]
            first_times[sw] = first_time

        if len(switch_data) != len(SWITCHES):
            continue

        ranks = pd.Series(first_times).rank(method="average")

        original_vector = []
        temporal_vector = []

        for sw in SWITCHES:
            original_vector.extend(switch_data[sw])
            temporal_vector.extend(switch_data[sw] + [float(ranks[sw])])

        result[exp_id] = (
            np.array(original_vector, dtype=float),
            np.array(temporal_vector, dtype=float)
        )

    return result


def topk_accuracy(model, X, y, k):
    probs = model.predict_proba(X)
    correct = 0

    for actual, row in zip(y, probs):
        top = model.classes_[np.argsort(row)[::-1][:k]]
        correct += actual in top

    return correct / len(y)


original_top1 = []
original_top2 = []
temporal_top1 = []
temporal_top2 = []

for seed in range(10, 20):
    train_ids, test_ids = train_test_split(
        labels.index.to_numpy(),
        test_size=0.30,
        random_state=seed,
        stratify=labels.to_numpy()
    )

    features = make_features(set(train_ids))

    train_ids = [i for i in train_ids if i in features]
    test_ids = [i for i in test_ids if i in features]

    X_train = np.array([features[i][0] for i in train_ids])
    XT_train = np.array([features[i][1] for i in train_ids])
    y_train = labels.loc[train_ids].to_numpy()

    X_test = np.array([features[i][0] for i in test_ids])
    XT_test = np.array([features[i][1] for i in test_ids])
    y_test = labels.loc[test_ids].to_numpy()

    if len(test_ids) == 0:
        continue

    rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        random_state=42,
        class_weight="balanced"
    )
    temporal_rf = RandomForestClassifier(
        n_estimators=300,
        max_depth=5,
        random_state=42,
        class_weight="balanced"
    )

    rf.fit(X_train, y_train)
    temporal_rf.fit(XT_train, y_train)

    r1 = np.mean(rf.predict(X_test) == y_test)
    r2 = topk_accuracy(rf, X_test, y_test, 2)
    t1 = np.mean(temporal_rf.predict(XT_test) == y_test)
    t2 = topk_accuracy(temporal_rf, XT_test, y_test, 2)

    original_top1.append(r1)
    original_top2.append(r2)
    temporal_top1.append(t1)
    temporal_top2.append(t2)

    print(
        f"Seed {seed}: n={len(test_ids)} | "
        f"Original Top-1={r1:.2%}, Top-2={r2:.2%} | "
        f"Temporal Top-1={t1:.2%}, Top-2={t2:.2%}"
    )

print("\nMEAN ACROSS SPLITS")
print("==================")
print(f"Original RF Top-1: {np.mean(original_top1):.2%}")
print(f"Original RF Top-2: {np.mean(original_top2):.2%}")
print(f"Temporal RF Top-1: {np.mean(temporal_top1):.2%}")
print(f"Temporal RF Top-2: {np.mean(temporal_top2):.2%}")
print(f"Top-1 change: {(np.mean(temporal_top1) - np.mean(original_top1)) * 100:+.2f} percentage points")
print(f"Top-2 change: {(np.mean(temporal_top2) - np.mean(original_top2)) * 100:+.2f} percentage points")
