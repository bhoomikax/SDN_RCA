import pandas as pd
import matplotlib.pyplot as plt

INPUT = "final_dataset.csv"

df = pd.read_csv(INPUT)

# Convert timestamp
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Sort chronologically
df = df.sort_values("timestamp")

# Create relative time in seconds
df["time_sec"] = (
    df["timestamp"] - df["timestamp"].iloc[0]
).dt.total_seconds()

# -----------------------------
# 1. THROUGHPUT VS TIME
# -----------------------------

throughput = (
    df.groupby("time_sec")["tx_throughput_mbps"]
    .mean()
    .reset_index()
)

plt.figure(figsize=(10, 5))
plt.plot(
    throughput["time_sec"],
    throughput["tx_throughput_mbps"]
)

plt.xlabel("Time (seconds)")
plt.ylabel("Throughput (Mbps)")
plt.title("Network Throughput During Experiment")
plt.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig("review2_throughput.png", dpi=300)
plt.close()


# -----------------------------
# 2. LATENCY VS TIME
# -----------------------------

latency = (
    df.groupby("time_sec")["latency_ms"]
    .mean()
    .reset_index()
)

plt.figure(figsize=(10, 5))
plt.plot(
    latency["time_sec"],
    latency["latency_ms"]
)

plt.xlabel("Time (seconds)")
plt.ylabel("Latency (ms)")
plt.title("Network Latency During Experiment")
plt.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig("review2_latency.png", dpi=300)
plt.close()


# -----------------------------
# 3. PACKET LOSS VS TIME
# -----------------------------

loss = (
    df.groupby("time_sec")["packet_loss_percent"]
    .mean()
    .reset_index()
)

plt.figure(figsize=(10, 5))
plt.plot(
    loss["time_sec"],
    loss["packet_loss_percent"]
)

plt.xlabel("Time (seconds)")
plt.ylabel("Packet Loss (%)")
plt.title("Packet Loss During Experiment")
plt.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig("review2_packet_loss.png", dpi=300)
plt.close()


print("Review-2 graphs generated successfully!")
print()
print("Created:")
print("  review2_throughput.png")
print("  review2_latency.png")
print("  review2_packet_loss.png")