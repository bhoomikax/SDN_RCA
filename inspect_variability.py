
import pandas as pd

df = pd.read_csv("master_dataset.csv")
metrics = [
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
]

normal = df[df["phase"] == "normal"]

stats = normal.groupby("switch")[metrics].agg(["mean", "std", "min", "max"])

for sw in stats.index:
    print(f"\n===== {sw} =====")
    print(stats.loc[sw].to_string())

print("\n===== FAULT PHASE SAMPLE =====")
fault = df[df["phase"] == "fault"]
print(fault.groupby("fault_location")[metrics].mean().round(3))
