"""Tolerant parsing of the runner's incrementally written files.

Telemetry rows are appended roughly once per second while a run is in
progress, so the last line may be partial. Rows that do not parse are counted
and skipped, never fabricated.
"""

import csv
import io
import json
from datetime import datetime

from telemetry_pipeline import TELEMETRY_FIELDS

NUMERIC = ("rx_packets", "rx_bytes", "rx_dropped", "tx_packets", "tx_bytes", "tx_dropped",
           "rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")


def _parse_stamp(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is not None:
        # Phase events carry the VM offset; telemetry is naive VM-local wall time.
        stamp = stamp.replace(tzinfo=None)
    return stamp


def parse_phase_events(text):
    events = {}
    fault_link = None
    if not text:
        return events, fault_link
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        phase = (row.get("phase") or "").strip()
        stamp = (row.get("timestamp") or "").strip()
        if phase not in ("normal", "fault", "recovery") or not stamp:
            continue
        try:
            events[phase] = _parse_stamp(stamp).isoformat()
        except ValueError:
            continue
        if phase != "normal" and row.get("fault_location") not in (None, "", "none"):
            fault_link = row["fault_location"]
    return events, fault_link


def parse_metadata(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        # The runner rewrites the file atomically per update; a torn read is possible.
        return {"status": "UNREADABLE_PARTIAL"}


def parse_telemetry(text, phase_events=None):
    """Return {rows, skipped, switches, series} where series is a per-timestamp
    aggregate (sum over numbered ports per switch) suitable for charts, plus the
    raw per-port rows for the latest timestamp."""
    result = {"rows": 0, "skipped": 0, "schema_ok": None, "switches": [], "series": [], "latest": [],
              "first_timestamp": None, "last_timestamp": None}
    if not text:
        return result
    lines = text.splitlines()
    if not lines:
        return result
    header = lines[0].strip()
    result["schema_ok"] = tuple(header.split(",")) == TELEMETRY_FIELDS
    if not result["schema_ok"]:
        return result
    fault_at = recovery_at = None
    if phase_events:
        try:
            fault_at = datetime.fromisoformat(phase_events["fault"]) if phase_events.get("fault") else None
            recovery_at = datetime.fromisoformat(phase_events["recovery"]) if phase_events.get("recovery") else None
        except ValueError:
            fault_at = recovery_at = None
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    by_stamp = {}
    switches = set()
    valid_rows = []
    for row in reader:
        if row.get("experiment_id") is None or any(row.get(k) in (None, "") for k in ("timestamp", "switch", "port")):
            result["skipped"] += 1
            continue
        try:
            stamp = _parse_stamp(row["timestamp"].strip())
            values = {k: float(row[k]) for k in NUMERIC}
        except (ValueError, TypeError, KeyError):
            result["skipped"] += 1
            continue
        if any(v != v for v in values.values()):  # NaN
            result["skipped"] += 1
            continue
        result["rows"] += 1
        switch, port = row["switch"].strip(), row["port"].strip()
        switches.add(switch)
        valid_rows.append((stamp, switch, port, row.get("interface_name", ""), values))
        if port == "LOCAL":
            continue
        bucket = by_stamp.setdefault(stamp, {})
        agg = bucket.setdefault(switch, {k: 0.0 for k in ("rx_packet_rate", "tx_packet_rate", "rx_throughput_mbps", "tx_throughput_mbps")})
        for k in agg:
            agg[k] += values[k]
    if not valid_rows:
        return result
    stamps = sorted(by_stamp)
    result["first_timestamp"] = min(r[0] for r in valid_rows).isoformat()
    result["last_timestamp"] = max(r[0] for r in valid_rows).isoformat()
    result["switches"] = sorted(switches, key=lambda s: int(s[1:]) if s[1:].isdigit() else 0)
    for stamp in stamps:
        phase = "unknown"
        if fault_at is not None:
            phase = "normal" if stamp < fault_at else ("fault" if (recovery_at is None or stamp < recovery_at) else "recovery")
        elif phase_events and phase_events.get("normal"):
            phase = "normal"
        entry = {"timestamp": stamp.isoformat(), "phase": phase}
        for switch, agg in by_stamp[stamp].items():
            for k, v in agg.items():
                entry["%s.%s" % (switch, k)] = round(v, 4)
        result["series"].append(entry)
    last = max(r[0] for r in valid_rows)
    result["latest"] = [
        {"switch": s, "port": p, "interface_name": i, **{k: v for k, v in vals.items()}}
        for stamp, s, p, i, vals in valid_rows if stamp == last
    ]
    return result
