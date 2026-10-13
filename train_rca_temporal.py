
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
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

FEATURES = [
    "mean_anomaly",
    "max_anomaly",
    "persistence",
    "first_anomaly",
    "first_switch_order"
]

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

train_ids, test_ids = train_test_split(
    labels.index.to_numpy(),
    test_size=0.30,
    random_state=42,
    stratify=labels.to_numpy()
)

train_ids, test_ids = set(train_ids), set(test_ids)

# Normal baseline from training experiments only.
normal = agg[
    agg["experiment_id"].isin(train_ids)
    & (agg["phase"] == "normal")
]

baseline = normal.groupby("switch")[METRICS].mean()
std = normal.groupby("switch")[METRICS].std()
std = std.fillna(0.0001).clip(lower=0.0001)

X_by_exp = {}

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

    # Compute anomaly measurements for each switch.
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

        switch_data[sw] = {
            "mean_anomaly": float(scores.mean()),
            "max_anomaly": float(scores.max()),
            "persistence": float(np.mean(scores > 1.0)),
            "first_anomaly": first_time
        }

        first_times[sw] = first_time

    if len(switch_data) != len(SWITCHES):
        continue

    # Earliest anomalous switch gets rank 1.
    # Ties receive the same average rank.
    ordered = pd.Series(first_times).rank(
        method="average", ascending=True
    )

    vector = []

    for sw in SWITCHES:
        vector.extend([
            switch_data[sw]["mean_anomaly"],
            switch_data[sw]["max_anomaly"],
            switch_data[sw]["persistence"],
            switch_data[sw]["first_anomaly"],
            float(ordered[sw])
        ])

    X_by_exp[exp_id] = np.array(vector, dtype=float)

usable_train = sorted(train_ids.intersection(X_by_exp))
usable_test = sorted(test_ids.intersection(X_by_exp))

X_train = np.array([X_by_exp[i] for i in usable_train])
y_train = labels.loc[usable_train].to_numpy()

X_test = np.array([X_by_exp[i] for i in usable_test])
y_test = labels.loc[usable_test].to_numpy()

print("Training experiments:", usable_train)
print("Testing experiments:", usable_test)
print("Features per experiment:", len(FEATURES) * len(SWITCHES))

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=5,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

pred = model.predict(X_test)
probabilities = model.predict_proba(X_test)

top2 = np.mean([
    actual in model.classes_[np.argsort(p)[::-1][:2]]
    for actual, p in zip(y_test, probabilities)
])

print("\nTEMPORAL RCA RESULTS")
print("====================")
print(f"Top-1 accuracy: {accuracy_score(y_test, pred):.2%}")
print(f"Top-2 accuracy: {top2:.2%}")

print("\nActual vs predicted:")
for exp_id, actual, predicted in zip(usable_test, y_test, pred):
    print(
        f"Experiment {exp_id}: "
        f"actual={actual}, predicted={predicted}"
    )
