"""Sequentially collect registered runs for one linear topology size on the VM.

Runs one registered logical/physical ID pair at a time through
experiment_runner_recollection.py, never concurrently, never reusing an ID,
and never clearing OVS state on its own. The batch fails closed when stale
bridges or Mininet/iperf processes are present before a run. Python 3.8
compatible; launch as root inside the Mininet VM.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import experiment_runner_recollection as runner
from linear_topology import TARGET_VALID_EXPERIMENTS, topology_run_registry


PROJECT = Path(__file__).resolve().parent
RUN_TIMEOUT_SECONDS = 300


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def existing_status(run_dir):
    metadata_path = Path(run_dir) / "run_metadata.json"
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "UNREADABLE"
    status = metadata.get("status")
    if status == "COMPLETE":
        # Runs recorded before the offered-rate rule existed are re-checked here so
        # the batch does not count an under-paced run as valid.
        try:
            runner.validate_offered_rate(
                dict(metadata["iperf"]["summary_validation"]),
                metadata["traffic_profile"]["offered_rate_mbps"],
            )
        except (KeyError, TypeError, ValueError):
            return "COMPLETE_BUT_OFFERED_RATE_INVALID"
    return status


def environment_is_clean(switches):
    bridges = subprocess.run(["ovs-vsctl", "list-br"], check=True, capture_output=True, text=True)
    stale = sorted(set(bridges.stdout.split()).intersection(switches))
    processes = subprocess.run(["ps", "-eo", "pid,args"], check=True, capture_output=True, text=True)
    busy = [line for line in processes.stdout.splitlines()
            if (" mn " in line or line.rstrip().endswith(" mn") or "iperf " in line)
            and "run_topology_batch" not in line]
    return (not stale and not busy), {"stale_bridges": stale, "busy_processes": busy}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--switches", type=int, required=True)
    parser.add_argument("--target-valid", type=int, default=TARGET_VALID_EXPERIMENTS)
    parser.add_argument("--max-runs", type=int, default=None,
                        help="stop after this many new run attempts in this batch")
    parser.add_argument("--max-consecutive-failures", type=int, default=3)
    parser.add_argument("--pause-seconds", type=float, default=8.0)
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        raise PermissionError("The batch must run as root inside the Mininet VM")
    topology = runner.topology_for(args.switches)
    registry = topology_run_registry(topology.switch_count)
    log_path = args.log or (runner.RUN_ROOT / ("topology_%d_switches" % topology.switch_count)
                            / "batch_log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    valid = 0
    attempted = 0
    consecutive_failures = 0
    for entry in registry.values():
        logical, physical = entry["logical_experiment_id"], entry["physical_run_id"]
        run_dir = runner.run_directory(logical, physical, topology.switch_count)
        status = existing_status(run_dir)
        if run_dir.exists():
            if status == "COMPLETE":
                valid += 1
            print("skip %s: existing status %s (valid so far %d)" % (run_dir.name, status, valid), flush=True)
            continue
        if valid >= args.target_valid:
            break
        if args.max_runs is not None and attempted >= args.max_runs:
            break
        clean, detail = environment_is_clean(topology.switches)
        if not clean:
            print("STOP: environment not clean before %s: %s" % (run_dir.name, json.dumps(detail)), flush=True)
            return 3
        attempted += 1
        command = [
            sys.executable, "-B", str(PROJECT / "experiment_runner_recollection.py"),
            "--switches", str(topology.switch_count),
            "--logical-id", str(logical), "--physical-id", str(physical),
            "--normal-seconds", "20", "--fault-seconds", "20", "--recovery-seconds", "20",
            "--run",
        ]
        started = time.monotonic()
        record = {"logical_experiment_id": logical, "physical_run_id": physical,
                  "fault_link": entry["fault_link"], "started_at": now_iso(), "command": command}
        print("start %s fault=%s" % (run_dir.name, entry["fault_link"]), flush=True)
        try:
            completed = subprocess.run(command, cwd=str(PROJECT), capture_output=True, text=True,
                                       timeout=RUN_TIMEOUT_SECONDS)
            record["returncode"] = completed.returncode
            record["stderr_tail"] = completed.stderr[-2000:]
        except subprocess.TimeoutExpired as exc:
            record["returncode"] = None
            record["stderr_tail"] = "timeout after %ss: %s" % (RUN_TIMEOUT_SECONDS, exc)
        record["elapsed_seconds"] = round(time.monotonic() - started, 1)
        record["status"] = existing_status(run_dir)
        record["ended_at"] = now_iso()
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        if record["status"] == "COMPLETE" and record["returncode"] == 0:
            valid += 1
            consecutive_failures = 0
        else:
            consecutive_failures += 1
        print("done %s status=%s rc=%s elapsed=%ss valid=%d" % (
            run_dir.name, record["status"], record["returncode"], record["elapsed_seconds"], valid), flush=True)
        if consecutive_failures >= args.max_consecutive_failures:
            print("STOP: %d consecutive failures" % consecutive_failures, flush=True)
            return 2
        time.sleep(args.pause_seconds)
    print("batch finished: valid=%d attempted=%d" % (valid, attempted), flush=True)
    return 0 if valid >= args.target_valid else 1


if __name__ == "__main__":
    sys.exit(main())
