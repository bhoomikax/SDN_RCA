"""Collect Open vSwitch port counters into an exclusive per-experiment CSV."""

import argparse
import csv
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from telemetry_pipeline import TELEMETRY_FIELDS


SWITCHES = ("s1", "s2", "s3", "s4")
INTERVAL = 1
DURATION = 60


def parse_port_interfaces(output):
    """Parse the runtime OpenFlow port-number to interface-name crosswalk."""
    interfaces = {}
    for line in output.splitlines():
        match = re.match(r"\s*(LOCAL|\d+)\(([^)]+)\):", line)
        if not match:
            continue
        port, interface_name = match.groups()
        if port in interfaces and interfaces[port] != interface_name:
            raise ValueError(f"Conflicting interface names for OpenFlow port {port}")
        interfaces[port] = interface_name
    return interfaces


def get_port_stats(switch):
    description = subprocess.run(
        ["ovs-ofctl", "-O", "OpenFlow13", "show", switch],
        capture_output=True,
        text=True,
        check=True,
    )
    interfaces = parse_port_interfaces(description.stdout)
    result = subprocess.run(
        ["ovs-ofctl", "-O", "OpenFlow13", "dump-ports", switch],
        capture_output=True,
        text=True,
        check=True,
    )

    stats = {}
    current_port = None
    for line in result.stdout.splitlines():
        line = line.strip()
        counter_text = line
        if line.startswith("port "):
            current_port = line.split()[1].rstrip(":")
            stats[current_port] = {
                "rx_packets": 0,
                "rx_bytes": 0,
                "rx_dropped": 0,
                "tx_packets": 0,
                "tx_bytes": 0,
                "tx_dropped": 0,
            }
            # ovs-ofctl commonly puts the RX counters on the port header line.
            counter_text = line.split(":", 1)[1].strip()
        if current_port and counter_text.startswith(("rx", "tx")):
            direction = "rx" if counter_text.startswith("rx") else "tx"
            for part in counter_text.split():
                if part.startswith("pkts="):
                    stats[current_port][f"{direction}_packets"] = int(
                        part.split("=", 1)[1].rstrip(",")
                    )
                elif part.startswith("bytes="):
                    stats[current_port][f"{direction}_bytes"] = int(
                        part.split("=", 1)[1].rstrip(",")
                    )
                elif part.startswith("drop="):
                    stats[current_port][f"{direction}_dropped"] = int(
                        part.split("=", 1)[1].rstrip(",")
                    )
    for port, values in stats.items():
        if port not in interfaces:
            raise ValueError(
                f"No runtime interface mapping for {switch} OpenFlow port {port}"
            )
        values["interface_name"] = interfaces[port]
    return stats


def collect(
    output_path,
    experiment_id,
    *,
    duration=DURATION,
    interval=INTERVAL,
    switches=SWITCHES,
    stats_reader=get_port_stats,
    clock=time.monotonic,
    sleep=time.sleep,
):
    """Collect port snapshots. Existing output files are never overwritten."""
    if duration < 0:
        raise ValueError("duration must be non-negative")
    if interval <= 0:
        raise ValueError("interval must be positive")
    experiment_id = int(experiment_id)
    if experiment_id < 1:
        raise ValueError("experiment_id must be positive")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    sample_count = 0

    # Exclusive creation protects experimental evidence on reruns.
    with output_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=TELEMETRY_FIELDS)
        writer.writeheader()
        start = clock()

        while clock() - start < duration:
            timestamp = datetime.now().isoformat()
            for switch in switches:
                stats = stats_reader(switch)
                for port, values in stats.items():
                    key = (switch, str(port))
                    old = previous.get(key)
                    if old is None:
                        rx_packet_rate = tx_packet_rate = 0.0
                        rx_throughput = tx_throughput = 0.0
                    else:
                        rx_packet_rate = max(
                            0, values["rx_packets"] - old["rx_packets"]
                        ) / interval
                        tx_packet_rate = max(
                            0, values["tx_packets"] - old["tx_packets"]
                        ) / interval
                        rx_throughput = max(
                            0, values["rx_bytes"] - old["rx_bytes"]
                        ) * 8 / interval / 1_000_000
                        tx_throughput = max(
                            0, values["tx_bytes"] - old["tx_bytes"]
                        ) * 8 / interval / 1_000_000

                    writer.writerow({
                        "timestamp": timestamp,
                        "switch": switch,
                        "port": str(port),
                        **values,
                        "interface_name": values.get(
                            "interface_name", "UNVERIFIED"
                        ),
                        "rx_packet_rate": rx_packet_rate,
                        "tx_packet_rate": tx_packet_rate,
                        "rx_throughput_mbps": rx_throughput,
                        "tx_throughput_mbps": tx_throughput,
                        "experiment_id": experiment_id,
                    })
                    previous[key] = values.copy()
                    sample_count += 1
            stream.flush()
            sleep(interval)

    if sample_count == 0:
        raise ValueError(f"Collector produced no telemetry rows: {output_path}")
    return sample_count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        help="unique telemetry CSV path supplied by the experiment runner",
    )
    parser.add_argument("--experiment-id", type=int, required=True)
    parser.add_argument("--switches", default=",".join(SWITCHES),
                        help="comma-separated switch names to poll (default: the four-switch topology)")
    args = parser.parse_args(argv)
    switches = tuple(name.strip() for name in args.switches.split(",") if name.strip())
    if not switches:
        raise ValueError("At least one switch name is required")
    rows = collect(args.output, args.experiment_id, switches=switches)
    print(f"Collected {rows} port rows; saved to {args.output}", flush=True)


if __name__ == "__main__":
    main()
