"""Experiment lifecycle: validation, locking, launch, status, telemetry, fetch.

A run is identified by (switches, logical_id, physical_id). Only registered
pairs from ``linear_topology.topology_run_registry`` are accepted for the 8-
and 12-switch topologies. The four-switch registry is exhausted (all authorised
physical IDs were consumed by the research collection), so new four-switch
runs are not offered.

Progress is derived from the runner's own files (metadata status, phase event
timestamps, telemetry row count) and from whether the runner process is still
alive on the VM. Nothing is simulated.
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

from linear_topology import TOPOLOGY_ID_REGISTRY, topology_run_registry

from . import config, vm
from .telemetry_parse import parse_metadata, parse_phase_events, parse_telemetry

_LOCK = threading.Lock()
_ACTIVE_PATH = config.STATE_DIR / "active_run.json"
PHASE_SECONDS = {"normal": 20, "fault": 20, "recovery": 20}


class RunConflict(RuntimeError):
    """Another run is active, or the requested IDs are not usable."""


def _load_active():
    if _ACTIVE_PATH.is_file():
        try:
            return json.loads(_ACTIVE_PATH.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


def _save_active(record):
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    if record is None:
        if _ACTIVE_PATH.exists():
            _ACTIVE_PATH.unlink()
        return
    _ACTIVE_PATH.write_text(json.dumps(record, indent=2), encoding="utf-8")


def registry(switches):
    switches = int(switches)
    if switches not in TOPOLOGY_ID_REGISTRY:
        return None
    return topology_run_registry(switches)


def validate_ids(switches, logical_id, physical_id):
    """Pure validation (no VM access): registered pair, configured fault link."""
    switches = int(switches)
    if switches not in config.SUPPORTED_SWITCHES:
        raise ValueError("switches must be one of %s" % (config.SUPPORTED_SWITCHES,))
    reg = registry(switches)
    if reg is None:
        raise ValueError("The %d-switch run registry is exhausted; no new live runs are authorised for it. "
                         "Saved results and replay remain available." % switches)
    logical_id, physical_id = int(logical_id), int(physical_id)
    entry = reg.get(logical_id)
    if entry is None or entry["physical_run_id"] != physical_id:
        spec = TOPOLOGY_ID_REGISTRY[switches]
        raise ValueError("Only registered pairs are allowed for %d switches: logical %d-%d with physical = logical + %d"
                         % (switches, spec["logical_start"], spec["logical_start"] + spec["slots"] - 1,
                            spec["physical_start"] - spec["logical_start"]))
    return entry


def id_availability(switches):
    """Registered pairs with their VM status; suggests the first unused pair."""
    switches = int(switches)
    reg = registry(switches)
    if reg is None:
        return {"switch_count": switches, "registry": None, "used": [], "next_free": None,
                "note": "four-switch registry exhausted; no live runs"}
    existing = {r["name"]: r for r in vm.list_runs(switches)}
    rows, next_free = [], None
    for logical, entry in reg.items():
        name = "physical_%d_logical_%d" % (entry["physical_run_id"], logical)
        status = existing.get(name, {}).get("status")
        rows.append({"logical_experiment_id": logical, "physical_run_id": entry["physical_run_id"],
                     "fault_link": entry["fault_link"], "slot": entry["slot"], "vm_status": status})
        if status is None and next_free is None:
            next_free = {"logical_experiment_id": logical, "physical_run_id": entry["physical_run_id"],
                         "fault_link": entry["fault_link"]}
    return {"switch_count": switches, "registry": rows, "next_free": next_free,
            "used_count": sum(1 for r in rows if r["vm_status"] is not None)}


def preflight(switches, logical_id, physical_id):
    """Read-only: ID validation, VM probe, and the runner's own preflight. Never
    creates a run directory or starts Mininet."""
    entry = validate_ids(switches, logical_id, physical_id)
    probe = vm.probe()
    ok, payload = vm.preflight(switches, logical_id, physical_id)
    result = {
        "switch_count": int(switches), "logical_experiment_id": int(logical_id), "physical_run_id": int(physical_id),
        "registry_fault_link": entry["fault_link"], "vm": probe, "runner_preflight_ok": ok, "runner_preflight": payload,
        "active_run": _load_active(), "mutates_environment": False,
    }
    blockers = []
    if not probe["sudo_nopasswd"]:
        blockers.append("passwordless sudo is not available on the VM")
    if not probe["controller_listening"]:
        blockers.append("no controller listening on %s:%d inside the VM" % (config.VM_CONTROLLER_HOST, config.VM_CONTROLLER_PORT))
    if probe["ovs_bridges"]:
        blockers.append("OVS bridges already exist: %s" % ", ".join(probe["ovs_bridges"]))
    if probe["busy_process_count"]:
        blockers.append("Mininet/iperf/runner processes are already running on the VM")
    if not ok:
        blockers.append("runner preflight failed: %s" % payload.get("error"))
    if result["active_run"]:
        blockers.append("a dashboard-launched run is already recorded as active")
    result["blockers"] = blockers
    result["ready"] = not blockers
    return result


def start(switches, logical_id, physical_id, confirmed):
    """Launch the real runner. Requires explicit confirmation and a clean preflight."""
    if not confirmed:
        raise ValueError("Starting an experiment deploys a topology and injects a link fault inside the Mininet VM; "
                         "confirmation is required")
    with _LOCK:
        active = _load_active()
        if active:
            raise RunConflict("Run %s is already active; wait for it to finish" % active.get("name"))
        check = preflight(switches, logical_id, physical_id)
        if not check["ready"]:
            raise RunConflict("Preflight blockers: " + "; ".join(check["blockers"]))
        launch = vm.start_run(switches, logical_id, physical_id)
        record = {
            "name": "physical_%d_logical_%d" % (int(physical_id), int(logical_id)),
            "switch_count": int(switches), "logical_experiment_id": int(logical_id), "physical_run_id": int(physical_id),
            "registry_fault_link": check["registry_fault_link"],
            "remote_pid": launch["remote_pid"], "log_path": launch["log_path"],
            "launched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "launched_monotonic": time.time(),
        }
        _save_active(record)
        return record


def active_run():
    return _load_active()


def _phase_from_events(events, now_vm=None):
    """Which phase the run is in according to its own event timestamps."""
    order = [p for p in ("normal", "fault", "recovery") if p in events]
    if not order:
        return None, None
    current = order[-1]
    started = datetime.fromisoformat(events[current])
    elapsed = None
    if now_vm:
        try:
            now = datetime.fromisoformat(now_vm).replace(tzinfo=None)
            elapsed = max(0.0, (now - started).total_seconds())
        except ValueError:
            elapsed = None
    return current, elapsed


def status(switches, logical_id, physical_id, include_telemetry=False, include_log=False):
    """Live status from the VM files. Works for any registered run, not only
    dashboard-launched ones."""
    switches, logical_id, physical_id = int(switches), int(logical_id), int(physical_id)
    name = "physical_%d_logical_%d" % (physical_id, logical_id)
    active = _load_active()
    is_active = bool(active and active.get("name") == name and active.get("switch_count") == switches)
    files = vm.read_run_files(switches, logical_id, physical_id)  # one SSH session: files + VM clock + runner PIDs
    exists = bool(files and files.get("_exists"))
    pids = list((files or {}).get("_pids") or [])
    vm_now = (files or {}).get("_now")
    out = {"name": name, "switch_count": switches, "logical_experiment_id": logical_id, "physical_run_id": physical_id,
           "dashboard_launched": is_active, "run_dir_exists": exists, "active_record": active if is_active else None,
           "runner_process_pids": pids, "vm_time": vm_now}
    if not exists:
        files = None
        out.update({"state": "not_started", "status": None, "phase": None, "phase_events": {}, "telemetry_rows": 0})
        if pids:
            out["state"] = "starting"
        if is_active and not pids and time.time() - active.get("launched_monotonic", 0) > 60:
            out["state"] = "failed_to_start"
            out["error"] = "The runner exited before creating its run directory; see the log."
            _save_active(None)
        return _attach_extras(out, files, include_telemetry, include_log, active if is_active else None)
    metadata = parse_metadata(files.get("run_metadata.json")) or {}
    events, fault_link = parse_phase_events(files.get("phase_events.csv"))
    if not events and isinstance(metadata.get("phase_events"), dict):
        events = {k: v for k, v in metadata["phase_events"].items() if v}
    meta_status = metadata.get("status")
    phase, elapsed = _phase_from_events(events, vm_now)
    if meta_status == "COMPLETE":
        state = "complete"
    elif meta_status == "FAILED_INVALID":
        state = "failed"
    elif pids:
        state = "running"
    elif meta_status == "RUNNING_INVALID_UNTIL_COMPLETE":
        state = "stale_running_no_process"
    else:
        state = "unknown"
    if is_active and state in ("complete", "failed", "stale_running_no_process"):
        _save_active(None)
    out.update({
        "state": state, "status": meta_status, "phase": phase, "phase_elapsed_seconds": elapsed,
        "phase_durations_seconds": metadata.get("phase_durations_seconds") or PHASE_SECONDS,
        "phase_events": events, "fault_link_from_events": fault_link,
        "configured_fault_link": metadata.get("fault_link"),
        "failure": metadata.get("failure"), "started_at": metadata.get("started_at"),
        "completed_at": metadata.get("completed_at"), "failed_at": metadata.get("failed_at"),
        "vm_time": vm_now, "iperf_completion_valid": (metadata.get("iperf") or {}).get("completion_valid"),
        "iperf_sender_mbps": ((metadata.get("iperf") or {}).get("summary_validation") or {}).get("client_sender_reported_mbps"),
        "controller": metadata.get("controller"),
    })
    return _attach_extras(out, files, include_telemetry, include_log, active if is_active else None)


def _attach_extras(out, files, include_telemetry, include_log, active):
    if include_telemetry:
        telemetry = parse_telemetry((files or {}).get("telemetry.csv"), out.get("phase_events"))
        out["telemetry"] = telemetry
        out["telemetry_rows"] = telemetry["rows"]
    elif files is not None:
        text = files.get("telemetry.csv") or ""
        out["telemetry_rows"] = max(0, text.count("\n") - 1) if text else 0
    if include_log:
        # Dashboard-launched runs always log to a deterministic path, so the log
        # stays readable after the run finished and the lock was released.
        log_path = (active or {}).get("log_path") or "%s/run_%d_switches_physical_%d_logical_%d.log" % (
            config.VM_LOG_DIR, out["switch_count"], out["physical_run_id"], out["logical_experiment_id"])
        try:
            log_text = vm.read_log(log_path)
        except (vm.VMError, ValueError) as exc:
            log_text = "(log unavailable: %s)" % exc
        out["log"] = log_text
        out["log_path"] = log_path
        out["iperf_client_log"] = (files or {}).get("iperf_client.log")
        out["iperf_server_log"] = (files or {}).get("iperf_server.log")
    return out


def local_copy_path(switches, logical_id, physical_id):
    name = "physical_%d_logical_%d" % (int(physical_id), int(logical_id))
    return config.DASHBOARD_RUNS_DIR / ("topology_%d_switches" % int(switches)) / name


def fetch(switches, logical_id, physical_id):
    """Copy a completed run into the isolated dashboard_runs/ directory."""
    validate_ids(switches, logical_id, physical_id)
    target = local_copy_path(switches, logical_id, physical_id)
    if target.is_dir():
        return {"path": str(target), "fetched": False, "note": "already present locally"}
    files = vm.read_run_files(switches, logical_id, physical_id)
    if not files or not files.get("_exists"):
        raise FileNotFoundError("Run directory does not exist on the VM")
    metadata = parse_metadata(files.get("run_metadata.json")) or {}
    if metadata.get("status") not in ("COMPLETE", "FAILED_INVALID"):
        raise RunConflict("Run is not finished (status %s); fetch only completed or failed runs" % metadata.get("status"))
    path = vm.fetch_run(switches, logical_id, physical_id, target.parent)
    return {"path": str(path), "fetched": True, "status": metadata.get("status")}


def local_runs():
    """Dashboard-fetched runs (isolated from the research datasets)."""
    out = []
    root = config.DASHBOARD_RUNS_DIR
    if not root.is_dir():
        return out
    for topo_dir in sorted(root.iterdir()):
        if not topo_dir.is_dir() or not topo_dir.name.startswith("topology_"):
            continue
        switches = int(topo_dir.name.split("_")[1])
        for run_dir in sorted(topo_dir.iterdir()):
            if not run_dir.is_dir() or run_dir.name.endswith("_derived") or not run_dir.name.startswith("physical_"):
                continue
            meta_path = run_dir / "run_metadata.json"
            meta = {}
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except ValueError:
                    meta = {"status": "UNREADABLE"}
            derived = run_dir.parent / (run_dir.name + "_derived")
            out.append({
                "switch_count": switches, "name": run_dir.name, "path": str(run_dir.relative_to(config.ROOT)),
                "logical_experiment_id": meta.get("logical_experiment_id"), "physical_run_id": meta.get("physical_run_id"),
                "status": meta.get("status"), "fault_link": meta.get("fault_link"), "started_at": meta.get("started_at"),
                "completed_at": meta.get("completed_at"), "failure": meta.get("failure"),
                "derived_candidate": (derived / "candidate" / "candidate_dataset.csv").is_file(),
                "inference_reports": sorted(p.name for p in derived.glob("inference_*.json")) if derived.is_dir() else [],
            })
    return out


def local_run_files(switches, logical_id, physical_id):
    path = local_copy_path(switches, logical_id, physical_id)
    if not path.is_dir():
        return None
    files = {}
    for name in ("run_metadata.json", "phase_events.csv", "telemetry.csv", "iperf_client.log", "iperf_server.log"):
        p = path / name
        files[name] = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
    return files
