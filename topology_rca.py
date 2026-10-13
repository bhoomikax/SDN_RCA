import pandas as pd
import numpy as np

INPUT = "master_dataset.csv"
OUTPUT = "temporal_rca_results.csv"

df = pd.read_csv(INPUT)
df["timestamp"] = pd.to_datetime(df["timestamp"])

metrics = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps"
]

switches = ["s1", "s2", "s3", "s4"]

links = {
    "s1-s2": ("s1", "s2"),
    "s2-s3": ("s2", "s3"),
    "s3-s4": ("s3", "s4")
}

# --------------------------------------------------
# 1. Aggregate port-level telemetry to switch level
# --------------------------------------------------

agg = (
    df.groupby(
        ["experiment_id", "timestamp", "switch", "phase", "fault_location"]
    )[metrics]
    .mean()
    .reset_index()
)

# --------------------------------------------------
# 2. Normal baseline for every switch
# --------------------------------------------------

normal = agg[agg["phase"] == "normal"]

baseline = normal.groupby("switch")[metrics].mean()
std = normal.groupby("switch")[metrics].std().fillna(0.0001)

# --------------------------------------------------
# 3. Calculate anomaly score at every timestamp
# --------------------------------------------------

def get_score(row):

    sw = row["switch"]

    if sw not in baseline.index:
        return 0.0

    values = []

    for metric in metrics:

        mean = baseline.loc[sw, metric]
        deviation = std.loc[sw, metric]

        if deviation < 0.0001:
            deviation = 0.0001

        z = abs(row[metric] - mean) / deviation
        values.append(z)

    return np.mean(values)


agg["anomaly_score"] = agg.apply(get_score, axis=1)

# --------------------------------------------------
# 4. Temporal RCA
# --------------------------------------------------

results = []

for experiment_id, exp in agg.groupby("experiment_id"):

    fault = exp[exp["phase"] == "fault"].copy()

    if fault.empty:
        continue

    actual_fault = fault["fault_location"].iloc[0]

    # Fault starts at first fault timestamp
    fault_start = fault["timestamp"].min()

    # Only consider early fault period.
    # Root cause should appear early, before downstream propagation.
    early_end = fault_start + pd.Timedelta(seconds=8)

    early = fault[
        fault["timestamp"] <= early_end
    ]

    switch_info = {}

    for sw in switches:

        sw_data = early[early["switch"] == sw]

        if sw_data.empty:
            switch_info[sw] = {
                "mean_anomaly": 0,
                "first_anomaly": 999,
                "persistence": 0
            }
            continue

        # Average anomaly
        mean_anomaly = sw_data["anomaly_score"].mean()

        # First significant anomaly
        significant = sw_data[
            sw_data["anomaly_score"] > 1.0
        ]

        if not significant.empty:
            first_time = (
                significant["timestamp"].min()
                - fault_start
            ).total_seconds()
        else:
            first_time = 999

        # Fraction of timestamps showing anomaly
        persistence = (
            (sw_data["anomaly_score"] > 1.0).mean()
        )

        switch_info[sw] = {
            "mean_anomaly": mean_anomaly,
            "first_anomaly": first_time,
            "persistence": persistence
        }

    # --------------------------------------------------
    # Score candidate links
    # --------------------------------------------------

    for link, (a, b) in links.items():

        A = switch_info[a]
        B = switch_info[b]

        endpoint_anomaly = (
            A["mean_anomaly"] +
            B["mean_anomaly"]
        ) / 2

        endpoint_persistence = (
            A["persistence"] +
            B["persistence"]
        ) / 2

        # Earlier anomaly gets higher score
        earliest = min(
            A["first_anomaly"],
            B["first_anomaly"]
        )

        if earliest == 999:
            temporal_score = 0
        else:
            temporal_score = 1 / (1 + earliest)

        # Endpoint with earlier anomaly gets additional weight
        if A["first_anomaly"] < B["first_anomaly"]:
            ordering_score = 1.0
        elif B["first_anomaly"] < A["first_anomaly"]:
            ordering_score = 1.0
        else:
            ordering_score = 0.5

        rca_score = (
            0.40 * endpoint_anomaly +
            0.25 * endpoint_persistence +
            0.25 * temporal_score +
            0.10 * ordering_score
        )

        results.append({
            "experiment_id": experiment_id,
            "actual_fault": actual_fault,
            "candidate_link": link,
            "endpoint_anomaly": endpoint_anomaly,
            "persistence": endpoint_persistence,
            "temporal_score": temporal_score,
            "rca_score": rca_score
        })

# --------------------------------------------------
# 5. Rank
# --------------------------------------------------

results = pd.DataFrame(results)

results = results.sort_values(
    ["experiment_id", "rca_score"],
    ascending=[True, False]
)

results["rca_rank"] = (
    results.groupby("experiment_id").cumcount() + 1
)

# --------------------------------------------------
# 6. Accuracy
# --------------------------------------------------

correct = 0
total = 0

print()
print("==============================")
print("TEMPORAL + TOPOLOGY RCA")
print("==============================")

for experiment_id, group in results.groupby("experiment_id"):

    top = group.iloc[0]

    actual = top["actual_fault"]
    predicted = top["candidate_link"]

    if actual == predicted:
        correct += 1

    total += 1

    print()
    print(f"Experiment {experiment_id}")
    print(f"Actual fault: {actual}")
    print(f"Predicted root cause: {predicted}")
    print(f"RCA score: {top['rca_score']:.3f}")

print()
print("==============================")
print(
    f"RCA ACCURACY: {correct}/{total} = "
    f"{100 * correct / total:.2f}%"
)
print("==============================")

results.to_csv(OUTPUT, index=False)

print()
print("Saved:", OUTPUT)