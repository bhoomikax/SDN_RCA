
import pandas as pd
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix

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

experiments = sorted(labels.index.tolist())


def build_features(train_ids):
    normal = agg[
        agg["experiment_id"].isin(train_ids)
        & (agg["phase"] == "normal")
    ]

    baseline = normal.groupby("switch")[METRICS].mean()
    std = normal.groupby("switch")[METRICS].std()
    std = std.fillna(0.0001).clip(lower=0.0001)

    features = {}

    for exp_id in experiments:
        exp = agg[agg["experiment_id"] == exp_id]
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
                break

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
            temporal_vector.extend(
                switch_data[sw] + [float(ranks[sw])]
            )

        features[exp_id] = (
            np.array(original_vector, dtype=float),
            np.array(temporal_vector, dtype=float)
        )

    return features


def top_k_correct(model, x, actual, k):
    probabilities = model.predict_proba(x.reshape(1, -1))[0]
    top_classes = model.classes_[np.argsort(probabilities)[::-1][:k]]
    return actual in top_classes


results = []

for held_out in experiments:
    train_ids = [i for i in experiments if i != held_out]

    # Recompute normal baselines without the held-out experiment.
    features = build_features(train_ids)

    train_ids = [i for i in train_ids if i in features]

    if held_out not in features or len(train_ids) == 0:
        print(f"Skipping experiment {held_out}: missing features")
        continue

    X_train = np.array([features[i][0] for i in train_ids])
    XT_train = np.array([features[i][1] for i in train_ids])
    y_train = labels.loc[train_ids].to_numpy()

    x_test, xt_test = features[held_out]
    actual = labels.loc[held_out]

    predictions = []

    for X, x in [(X_train, x_test), (XT_train, xt_test)]:
        model = RandomForestClassifier(
            n_estimators=300,
            max_depth=5,
            random_state=42,
            class_weight="balanced"
        )
        model.fit(X, y_train)

        predicted = model.predict(x.reshape(1, -1))[0]
        top2 = top_k_correct(model, x, actual, 2)
        predictions.append((predicted, top2))

    original_pred, original_top2 = predictions[0]
    temporal_pred, temporal_top2 = predictions[1]

    results.append({
        "experiment": held_out,
        "actual": actual,
        "original_pred": original_pred,
        "temporal_pred": temporal_pred,
        "original_top1": original_pred == actual,
        "temporal_top1": temporal_pred == actual,
        "original_top2": original_top2,
        "temporal_top2": temporal_top2
    })

    print(
        f"Experiment {held_out}: actual={actual} | "
        f"Original={original_pred} "
        f"(Top-2 {'hit' if original_top2 else 'miss'}) | "
        f"Temporal={temporal_pred} "
        f"(Top-2 {'hit' if temporal_top2 else 'miss'})"
    )

if not results:
    raise RuntimeError("No experiments were evaluated.")

out = pd.DataFrame(results)

print("\nLEAVE-ONE-EXPERIMENT-OUT RESULTS")
print("================================")
print(f"Experiments evaluated: {len(out)}")
print(f"Original Top-1: {out['original_top1'].mean():.2%}")
print(f"Original Top-2: {out['original_top2'].mean():.2%}")
print(f"Temporal Top-1: {out['temporal_top1'].mean():.2%}")
print(f"Temporal Top-2: {out['temporal_top2'].mean():.2%}")

print("\nConfusion matrix: Original RF")
print(confusion_matrix(
    out["actual"], out["original_pred"], labels=LABELS
))

print("\nConfusion matrix: Temporal RF")
print(confusion_matrix(
    out["actual"], out["temporal_pred"], labels=LABELS
))

out.to_csv("rca_loeo_results.csv", index=False)
print("\nSaved per-experiment results to rca_loeo_results.csv")
