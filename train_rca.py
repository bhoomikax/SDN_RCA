
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)
from sklearn.model_selection import train_test_split

INPUT = "master_dataset.csv"
METRICS = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps"
]
SWITCHES = ["s1", "s2", "s3", "s4"]
FEATURES = [
    "mean_anomaly",
    "max_anomaly",
    "persistence",
    "first_anomaly",
]
LABELS = ["s1-s2", "s2-s3", "s3-s4"]

df = pd.read_csv(INPUT)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Aggregate port telemetry to switch/timestamp.
agg = (
    df.groupby(
        ["experiment_id", "timestamp", "switch",
         "phase", "fault_location"],
        as_index=False
    )[METRICS].mean()
)

# Ground-truth link label for each experiment.
labels_by_exp = (
    df[df["phase"] == "fault"]
    .groupby("experiment_id")["fault_location"]
    .first()
)
labels_by_exp = labels_by_exp[
    labels_by_exp.isin(LABELS)
]

# Split experiments BEFORE fitting the normal baseline.
exp_ids = labels_by_exp.index.to_numpy()
y_all = labels_by_exp.to_numpy()

train_ids, test_ids = train_test_split(
    exp_ids,
    test_size=0.30,
    random_state=42,
    stratify=y_all
)

train_ids = set(train_ids)
test_ids = set(test_ids)

# Fit baseline only on normal data from training experiments.
normal_train = agg[
    agg["experiment_id"].isin(train_ids)
    & (agg["phase"] == "normal")
]

baseline = normal_train.groupby("switch")[METRICS].mean()
std = normal_train.groupby("switch")[METRICS].std()

std = std.fillna(0.0001).clip(lower=0.0001)

# Extract fault-period features for every experiment.
rows = []

for exp_id, exp in agg.groupby("experiment_id"):
    if exp_id not in labels_by_exp.index:
        continue

    fault = exp[exp["phase"] == "fault"]
    if fault.empty:
        continue

    start = fault["timestamp"].min()
    early = fault[
        fault["timestamp"] <= start + pd.Timedelta(seconds=10)
    ]

    for sw in SWITCHES:
        data = early[early["switch"] == sw]

        if data.empty or sw not in baseline.index:
            continue

        z = (
            (data[METRICS] - baseline.loc[sw, METRICS])
            .abs()
            / std.loc[sw, METRICS]
        )
        scores = z.mean(axis=1).to_numpy()
        indices = np.flatnonzero(scores > 1.0)

        rows.append({
    "experiment_id": exp_id,
    "switch": sw,
    "mean_anomaly": scores.mean(),
    "max_anomaly": scores.max(),
    "persistence": np.mean(scores > 1.0),
    "first_anomaly": (
        (data.iloc[indices[0]]["timestamp"] - start).total_seconds()
        if len(indices) else 999.0
    ),
    })
features = pd.DataFrame(rows)

# Build one feature vector per experiment in fixed switch order.
X_by_exp = {}
for exp_id, group in features.groupby("experiment_id"):
    group = group.set_index("switch")

    if not all(sw in group.index for sw in SWITCHES):
        continue

    X_by_exp[exp_id] = np.concatenate([
        group.loc[sw, FEATURES].to_numpy(dtype=float)
        for sw in SWITCHES
    ])

usable_train = sorted(train_ids.intersection(X_by_exp))
usable_test = sorted(test_ids.intersection(X_by_exp))

X_train = np.array([X_by_exp[i] for i in usable_train])
y_train = labels_by_exp.loc[usable_train].to_numpy()
X_test = np.array([X_by_exp[i] for i in usable_test])
y_test = labels_by_exp.loc[usable_test].to_numpy()

print("Training experiments:", usable_train)
print("Testing experiments:", usable_test)
print("Training class counts:")
print(pd.Series(y_train).value_counts().to_dict())
print("Testing class counts:")
print(pd.Series(y_test).value_counts().to_dict())

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=5,
    random_state=42,
    class_weight="balanced"
)
model.fit(X_train, y_train)

pred = model.predict(X_test)
probabilities = model.predict_proba(X_test)

top2_correct = sum(
    actual in model.classes_[np.argsort(p)[::-1][:2]]
    for actual, p in zip(y_test, probabilities)
)

print("\n========== RCA RESULTS ==========")
print(f"Top-1 accuracy: {accuracy_score(y_test, pred):.2%}")
print(f"Top-2 accuracy: {top2_correct / len(y_test):.2%}")

print("\nActual vs predicted:")
for exp_id, actual, predicted in zip(usable_test, y_test, pred):
    print(f"Experiment {exp_id}: actual={actual}, predicted={predicted}")

print("\nConfusion matrix:")
print(confusion_matrix(y_test, pred, labels=LABELS))

print("\nClassification report:")
print(classification_report(
    y_test, pred, labels=LABELS, zero_division=0
))
