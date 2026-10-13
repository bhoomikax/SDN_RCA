import pandas as pd
import numpy as np

INPUT = "master_dataset.csv"
OUTPUT = "rca_results.csv"

df = pd.read_csv(INPUT)

# ------------------------------------------------------------
# Calculate anomaly scores
# ------------------------------------------------------------

metrics = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps"
]

# Calculate normal baseline for each switch
normal = df[df["phase"] == "normal"]

baselines = (
    normal.groupby("switch")[metrics]
    .mean()
)

stds = (
    normal.groupby("switch")[metrics]
    .std()
    .fillna(0.0001)
)

# ------------------------------------------------------------
# Calculate anomaly score for every telemetry row
# ------------------------------------------------------------

scores = []

for _, row in df.iterrows():

    switch = row["switch"]

    if switch not in baselines.index:
        scores.append(0.0)
        continue

    baseline = baselines.loc[switch]
    std = stds.loc[switch]

    z_scores = []

    for metric in metrics:

        value = row[metric]

        mean = baseline[metric]
        deviation = std[metric]

        if deviation < 0.0001:
            deviation = 0.0001

        z = abs(value - mean) / deviation

        z_scores.append(z)

    score = np.mean(z_scores)

    scores.append(score)


df["anomaly_score"] = scores

# ------------------------------------------------------------
# Rank switches during fault periods
# ------------------------------------------------------------

fault_data = df[
    df["phase"] == "fault"
].copy()

ranking = (
    fault_data
    .groupby(
        [
            "experiment_id",
            "fault_location",
            "switch"
        ]
    )["anomaly_score"]
    .mean()
    .reset_index()
)

ranking = ranking.sort_values(
    [
        "experiment_id",
        "anomaly_score"
    ],
    ascending=[True, False]
)

# ------------------------------------------------------------
# Assign RCA rank
# ------------------------------------------------------------

ranking["rca_rank"] = (
    ranking
    .groupby("experiment_id")
    .cumcount() + 1
)

# ------------------------------------------------------------
# Confidence score
# ------------------------------------------------------------

def calculate_confidence(group):

    scores = group["anomaly_score"].values

    if len(scores) == 0:
        return 0.0

    top = scores[0]

    if len(scores) > 1:
        second = scores[1]
    else:
        second = 0.0

    if top <= 0:
        return 0.0

    confidence = (
        (top - second) / top
    ) * 100

    return max(
        0.0,
        min(100.0, confidence)
    )


confidence = (
    ranking
    .groupby("experiment_id")
    .apply(calculate_confidence)
    .reset_index(
        name="confidence_percent"
    )
)

ranking = ranking.merge(
    confidence,
    on="experiment_id"
)

# ------------------------------------------------------------
# Save results
# ------------------------------------------------------------

ranking.to_csv(
    OUTPUT,
    index=False
)

print()
print("==============================")
print("RCA RESULTS")
print("==============================")

for experiment_id, group in ranking.groupby(
    "experiment_id"
):

    top = group.iloc[0]

    print()
    print(
        f"Experiment {experiment_id}"
    )

    print(
        f"Actual fault: "
        f"{top['fault_location']}"
    )

    print(
        f"Top suspected switch: "
        f"{top['switch']}"
    )

    print(
        f"Anomaly score: "
        f"{top['anomaly_score']:.3f}"
    )

    print(
        f"Confidence: "
        f"{top['confidence_percent']:.2f}%"
    )

print()
print("Saved:", OUTPUT)