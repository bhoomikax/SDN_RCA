
import pandas as pd

df = pd.read_csv("master_dataset.csv")

metrics = [
    "rx_packets",
    "tx_packets",
    "rx_bytes",
    "tx_bytes",
    "rx_packet_rate",
    "tx_packet_rate",
    "rx_throughput_mbps",
    "tx_throughput_mbps",
]

for phase in ["normal", "fault", "recovery"]:
    part = df[df["phase"] == phase]
    print(f"\n===== {phase.upper()} =====")

    for metric in metrics:
        print(
            f"{metric:22s} "
            f"nonzero={(part[metric] != 0).sum():5d}/{len(part)} "
            f"min={part[metric].min():.4f} "
            f"max={part[metric].max():.4f}"
        )

print("\n===== BY SWITCH: RX/TX COUNTERS =====")
print(
    df.groupby(["phase", "switch"])[
        ["rx_packets", "tx_packets", "rx_bytes", "tx_bytes"]
    ].mean().round(2).to_string()
)
