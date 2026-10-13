
import pandas as pd

df = pd.read_csv("master_dataset.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"])

METRICS = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
]
SWITCHES = ["s1", "s2", "s3", "s4"]
FAULTS = ["s1-s2", "s2-s3", "s3-s4"]

results = []

for exp in sorted(df["experiment_id"].unique()):
    exp_df = df[df["experiment_id"] == exp]
    normal = exp_df[exp_df["phase"] == "normal"]
    fault = exp_df[exp_df["phase"] == "fault"]

    if normal.empty or fault.empty:
        continue

    actual_values = fault["fault_location"].unique()
    actual_values = [x for x in actual_values if x in FAULTS]

    if not actual_values:
        continue

    actual = actual_values[0]

    # Establish each switch's baseline using this experiment's normal phase.
    baseline = normal.groupby("switch")[METRICS].agg(["mean", "std"])

    t0 = fault["timestamp"].min()
    fault = fault[fault["timestamp"] <= t0 + pd.Timedelta(seconds=10)]

    first_times = {}

    for sw in SWITCHES:
        sw_data = fault[fault["switch"] == sw].sort_values("timestamp")

        if sw_data.empty or sw not in baseline.index:
            first_times[sw] = None
            continue

        b = baseline.loc[sw]
        detected_time = None

        for _, row in sw_data.iterrows():
            scores = []

            for metric in METRICS:
                mean = b[(metric, "mean")]
                std = b[(metric, "std")]

                if pd.isna(std) or std < 1e-4:
                    std = 1e-4

                scores.append(abs(row[metric] - mean) / std)

            if max(scores) > 2:
                detected_time = (row["timestamp"] - t0).total_seconds()
                break

        first_times[sw] = detected_time

    ordered = sorted(
        [(time, sw) for sw, time in first_times.items()
         if time is not None]
    )

    results.append({
        "experiment": exp,
        "actual_fault": actual,
        "first_anomaly_order": " -> ".join(
            sw for _, sw in ordered
        ) or "none detected",
        **{
            f"first_{sw}_sec": first_times[sw]
            for sw in SWITCHES
        },
    })

result = pd.DataFrame(results)

if result.empty:
    print("No experiments qualified. Check phase and fault_location values.")
else:
    print(result.to_string(index=False))
    result.to_csv("fault_pattern_analysis.csv", index=False)
    print(f"\nAnalyzed {len(result)} experiments.")
    print("Saved to fault_pattern_analysis.csv")
