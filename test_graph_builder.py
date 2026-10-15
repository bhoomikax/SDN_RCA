import tempfile
import unittest
from pathlib import Path

import pandas as pd

from build_graph_multi import build, build_snapshots


def frame(rows):
    base = {"experiment_id": 1, "timestamp": "2026-01-01 00:00:00", "switch": "s1",
            "phase": "fault", "fault_type": "link_failure", "fault_location": "s1-s2"}
    return pd.DataFrame([{**base, **row} for row in rows])


class GraphBuilderTests(unittest.TestCase):
    def test_aggregates_all_numbered_ports_and_excludes_local(self):
        data = frame([
            {"port": "LOCAL", "rx_packet_rate": 0, "tx_packet_rate": 0, "rx_throughput_mbps": 0, "tx_throughput_mbps": 0},
            {"port": 1, "rx_packet_rate": 2, "tx_packet_rate": 3, "rx_throughput_mbps": 4, "tx_throughput_mbps": 5},
            {"port": 2, "rx_packet_rate": 7, "tx_packet_rate": 11, "rx_throughput_mbps": 13, "tx_throughput_mbps": 17},
        ])
        snapshot = build_snapshots(data)[0]
        self.assertEqual(snapshot["node_features"]["s1"], [9.0, 14.0, 17.0, 22.0])
        self.assertEqual(snapshot["node_port_counts"]["s1"], 2)
        self.assertEqual(snapshot["node_port_counts"]["h1"], 0)

    def test_rejects_duplicate_port_timestamp_and_inconsistent_labels(self):
        one = {"port": 1, "rx_packet_rate": 1, "tx_packet_rate": 1,
               "rx_throughput_mbps": 1, "tx_throughput_mbps": 1}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            build_snapshots(frame([one, one]))
        changed = frame([one, {**one, "port": 2}])
        changed.loc[1, "phase"] = "normal"
        with self.assertRaisesRegex(ValueError, "Inconsistent phase"):
            build_snapshots(changed)

    def test_writer_preserves_existing_graph_output(self):
        data = frame([{"port": 1, "rx_packet_rate": 1, "tx_packet_rate": 2,
                       "rx_throughput_mbps": 3, "tx_throughput_mbps": 4}])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.csv"
            output = root / "graph.json"
            data.to_csv(source, index=False)
            output.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                build(source, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")


if __name__ == "__main__":
    unittest.main()
