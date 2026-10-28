"""FastAPI application for the research demo dashboard.

Read-only endpoints serve saved results and VM state. Control endpoints
(preflight is read-only; verify-topology and start modify the isolated Mininet
environment) require an explicit ``confirm`` flag and, when configured, a
shared token. The service binds to loopback by default and allows CORS only
for the local frontend origin. There is no generic command or file endpoint:
every path is derived from validated integers and fixed directories.
"""

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Make the repository root importable (build_*, evaluate_*, linear_topology ...).
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from . import config, inference, runs, saved_results, vm  # noqa: E402
from .telemetry_parse import parse_metadata, parse_phase_events, parse_telemetry  # noqa: E402

app = FastAPI(title="SDN Fault Localisation — Research Demo API", version="0.1.0", docs_url="/api/docs", redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Dashboard-Token"],
)

_INFERENCE_LOCK = threading.Lock()
SwitchesQuery = Query(12, description="4, 8 or 12")
METHODS = ("rf_baseline", "topology_link_ranker", "graph_only", "temporal_only", "graph_temporal")


def require_token(x_dashboard_token: Optional[str] = Header(default=None)):
    if config.CONTROL_TOKEN and x_dashboard_token != config.CONTROL_TOKEN:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Dashboard-Token for a control endpoint")
    return True


def _switches(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="switches must be an integer")
    if value not in config.SUPPORTED_SWITCHES:
        raise HTTPException(status_code=422, detail="switches must be one of %s" % (config.SUPPORTED_SWITCHES,))
    return value


def _ids(switches, logical_id, physical_id):
    switches = _switches(switches)
    try:
        runs.validate_ids(switches, logical_id, physical_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return switches, int(logical_id), int(physical_id)


def _vm_guard(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except vm.VMError as exc:
        raise HTTPException(status_code=503, detail="VM unavailable: %s" % exc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class RunRequest(BaseModel):
    switches: int = Field(..., description="4, 8 or 12")
    logical_id: int = Field(..., ge=0, le=100000)
    physical_id: int = Field(..., ge=0, le=100000)
    confirm: bool = Field(False, description="must be true to deploy a topology and inject the configured fault")


class VerifyRequest(BaseModel):
    switches: int
    confirm: bool = False


class InferenceRequest(BaseModel):
    methods: List[str] = Field(default_factory=lambda: list(METHODS))


# --------------------------------------------------------------------------- health
@app.get("/api/health")
def health():
    checks = {"backend": {"status": "Connected", "time": datetime.now().astimezone().isoformat(timespec="seconds")}}
    checks["ssh_key"] = {"status": "Connected" if vm.key_available() else "Disconnected",
                         "detail": "key file present" if vm.key_available() else "SSH key not found (set SDN_VM_SSH_KEY)"}
    try:
        probe = vm.probe()
        checks["ssh"] = {"status": "Connected", "detail": "%s, %s" % (probe["hostname"], probe["python"])}
        checks["controller"] = {"status": "Connected" if probe["controller_listening"] else "Disconnected",
                                "detail": ("listening on %s:%d (tested from the VM)" % (config.VM_CONTROLLER_HOST, config.VM_CONTROLLER_PORT)
                                           if probe["controller_listening"] else "no listener on port %d inside the VM" % config.VM_CONTROLLER_PORT),
                                "process": probe["controller_process"]}
        checks["mininet_ovs"] = {"status": "Connected" if (probe["mininet_available"] and probe["ovs_available"]) else "Disconnected",
                                 "detail": "mn %s, ovs-vsctl %s, bridges: %s, busy processes: %d" % (
                                     "ok" if probe["mininet_available"] else "missing", "ok" if probe["ovs_available"] else "missing",
                                     ", ".join(probe["ovs_bridges"]) or "none", probe["busy_process_count"]),
                                 "sudo_nopasswd": probe["sudo_nopasswd"], "iperf": probe["iperf_available"]}
        checks["runner"] = {"status": "Connected" if probe["runner_sha256"] else "Disconnected",
                            "detail": "VM runner sha256 %s" % (probe["runner_sha256"][:12] or "missing"),
                            "matches_local": probe["runner_sha256"] == _local_runner_hash()}
        checks["vm_clock"] = {"status": "Unknown", "detail": "VM time %s, NTP synchronized: %s" % (probe["vm_time"], probe["ntp_synchronized"] or "unknown")}
    except vm.VMError as exc:
        checks["ssh"] = {"status": "Disconnected", "detail": str(exc)}
        for key in ("controller", "mininet_ovs", "runner", "vm_clock"):
            checks[key] = {"status": "Not Tested", "detail": "VM unreachable"}
    telemetry = []
    for switches, saved in config.SAVED_RESULTS.items():
        candidate = Path(saved["candidate_dir"]) / "candidate_dataset.csv"
        telemetry.append({"switch_count": switches, "candidate_present": candidate.is_file(),
                          "graph_present": Path(saved["graph"]).is_file(),
                          "rf_eval_present": (Path(saved["rf_eval_dir"]) / "grouped_evaluation.csv").is_file(),
                          "neural_eval_present": (Path(saved["neural_eval_dir"]) / "mean_seed_ensemble_predictions.csv").is_file(),
                          "checkpoints": len(list((Path(saved["neural_eval_dir"]) / "checkpoints").glob("*.pt"))) if (Path(saved["neural_eval_dir"]) / "checkpoints").is_dir() else 0,
                          "xai_present": (Path(saved["xai_dir"]) / "xai_summary.json").is_file()})
    all_files = all(t["candidate_present"] and t["rf_eval_present"] and t["neural_eval_present"] for t in telemetry)
    checks["saved_artifacts"] = {"status": "Connected" if all_files else "Disconnected", "topologies": telemetry}
    inference_ready = _inference_readiness()
    checks["inference"] = inference_ready
    checks["active_run"] = runs.active_run()
    checks["dashboard_runs_dir"] = str(config.DASHBOARD_RUNS_DIR)
    return checks


def _local_runner_hash():
    try:
        import hashlib
        return hashlib.sha256((ROOT / "experiment_runner_recollection.py").read_bytes()).hexdigest()
    except OSError:
        return None


def _inference_readiness():
    detail = {}
    try:
        import sklearn  # noqa: F401
        import torch  # noqa: F401
        import torch_geometric  # noqa: F401
        detail["libraries"] = "scikit-learn, torch, torch_geometric importable"
        ok = True
    except Exception as exc:  # noqa: BLE001
        detail["libraries"] = "import failure: %s" % exc
        ok = False
    try:
        import shap  # noqa: F401
        detail["shap"] = True
    except Exception:  # noqa: BLE001
        detail["shap"] = False
    live = {}
    for switches in config.SUPPORTED_SWITCHES:
        reg = runs.registry(switches)
        try:
            inference._checkpoint_fold(switches)
            ckpt = True
        except FileNotFoundError:
            ckpt = False
        live[switches] = {"new_runs_supported": reg is not None,
                          "methods": (["rf_baseline", "topology_link_ranker"] + (list(saved_results.NEURAL_METHODS) if ckpt else [])) if reg else [],
                          "note": None if reg else "registry exhausted; saved results and replay only"}
    detail["live_inference"] = live
    return {"status": "Connected" if ok else "Disconnected", **detail}


# --------------------------------------------------------------------------- topology
@app.get("/api/topology")
def topology(switches: int = SwitchesQuery):
    switches = _switches(switches)
    spec = saved_results.topology_spec(switches)
    reg = runs.registry(switches)
    spec["registry"] = None if reg is None else {
        "logical_range": [min(reg), max(reg)], "physical_offset": next(iter(reg.values()))["physical_run_id"] - min(reg)}
    return spec


# --------------------------------------------------------------------------- experiments
@app.get("/api/experiments/registry")
def experiment_registry(switches: int = SwitchesQuery):
    return _vm_guard(runs.id_availability, _switches(switches))


@app.get("/api/experiments/vm-runs")
def vm_runs(switches: int = SwitchesQuery):
    return {"switch_count": _switches(switches), "runs": _vm_guard(vm.list_runs, _switches(switches))}


@app.get("/api/experiments/local")
def local_runs():
    return {"runs": runs.local_runs(), "root": str(config.DASHBOARD_RUNS_DIR.relative_to(config.ROOT))}


@app.get("/api/experiments/active")
def active():
    return {"active": runs.active_run()}


@app.post("/api/experiments/preflight")
def preflight(req: RunRequest):
    _ids(req.switches, req.logical_id, req.physical_id)
    return _vm_guard(runs.preflight, req.switches, req.logical_id, req.physical_id)


@app.post("/api/experiments/verify-topology", dependencies=[Depends(require_token)])
def verify_topology(req: VerifyRequest):
    switches = _switches(req.switches)
    if not req.confirm:
        raise HTTPException(status_code=400, detail="verify-topology starts and stops the N-switch Mininet network inside the VM; confirm is required")
    if runs.active_run():
        raise HTTPException(status_code=409, detail="A run is active; verification is refused while it runs")
    ok, payload = _vm_guard(vm.verify_topology, switches)
    if not ok:
        raise HTTPException(status_code=502, detail=payload)
    return {"switch_count": switches, "result": payload, "writes_files": False, "injects_fault": False}


@app.post("/api/experiments/start", dependencies=[Depends(require_token)])
def start(req: RunRequest):
    _ids(req.switches, req.logical_id, req.physical_id)
    try:
        return runs.start(req.switches, req.logical_id, req.physical_id, req.confirm)
    except runs.RunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except vm.VMError as exc:
        raise HTTPException(status_code=503, detail="VM unavailable: %s" % exc)


@app.get("/api/experiments/{switches}/{logical_id}/{physical_id}/status")
def run_status(switches: int, logical_id: int, physical_id: int, telemetry: bool = False, log: bool = False):
    switches, logical_id, physical_id = _ids(switches, logical_id, physical_id)
    return _vm_guard(runs.status, switches, logical_id, physical_id, include_telemetry=telemetry, include_log=log)


@app.get("/api/experiments/{switches}/{logical_id}/{physical_id}/telemetry")
def run_telemetry(switches: int, logical_id: int, physical_id: int, source: str = "auto"):
    """Telemetry parsed from the VM run files (source=vm), from the local fetched
    copy (source=local), or local if present else VM (auto)."""
    switches, logical_id, physical_id = _ids(switches, logical_id, physical_id)
    if source not in ("auto", "vm", "local"):
        raise HTTPException(status_code=422, detail="source must be auto, vm or local")
    files = None
    used = None
    if source in ("auto", "local"):
        files = runs.local_run_files(switches, logical_id, physical_id)
        used = "local" if files else None
    if files is None and source in ("auto", "vm"):
        files = _vm_guard(vm.read_run_files, switches, logical_id, physical_id)
        if files is not None and not files.get("_exists"):
            files = None
        used = "vm" if files else None
    if files is None:
        return {"available": False, "source": None, "telemetry": parse_telemetry(None), "phase_events": {}}
    events, fault_link = parse_phase_events(files.get("phase_events.csv"))
    metadata = parse_metadata(files.get("run_metadata.json")) or {}
    return {"available": True, "source": used, "status": metadata.get("status"), "phase_events": events,
            "fault_link_from_events": fault_link, "telemetry": parse_telemetry(files.get("telemetry.csv"), events)}


@app.get("/api/experiments/{switches}/{logical_id}/{physical_id}/logs")
def run_logs(switches: int, logical_id: int, physical_id: int):
    switches, logical_id, physical_id = _ids(switches, logical_id, physical_id)
    return _vm_guard(runs.status, switches, logical_id, physical_id, include_telemetry=False, include_log=True)


@app.post("/api/experiments/{switches}/{logical_id}/{physical_id}/fetch")
def fetch_run(switches: int, logical_id: int, physical_id: int):
    switches, logical_id, physical_id = _ids(switches, logical_id, physical_id)
    try:
        return runs.fetch(switches, logical_id, physical_id)
    except runs.RunConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except vm.VMError as exc:
        raise HTTPException(status_code=503, detail="VM unavailable: %s" % exc)


@app.post("/api/experiments/{switches}/{logical_id}/{physical_id}/inference")
def run_inference(switches: int, logical_id: int, physical_id: int, req: InferenceRequest):
    switches, logical_id, physical_id = _ids(switches, logical_id, physical_id)
    unknown = [m for m in req.methods if m not in METHODS]
    if unknown or not req.methods:
        raise HTTPException(status_code=422, detail="methods must be a non-empty subset of %s" % (METHODS,))
    run_dir = runs.local_copy_path(switches, logical_id, physical_id)
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run is not fetched locally yet; call /fetch first")
    if not _INFERENCE_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another inference is in progress")
    try:
        started = time.monotonic()
        result = inference.run_inference(switches, run_dir, req.methods)
        result["elapsed_seconds"] = round(time.monotonic() - started, 2)
        result["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        result["kind"] = "live inference on a dashboard-collected run (not a saved evaluation result)"
        derived = Path(result["prepared"]["derived_dir"])
        derived.mkdir(parents=True, exist_ok=True)
        report = derived / ("inference_%s.json" % datetime.now().strftime("%Y%m%dT%H%M%S"))
        report.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        result["report_path"] = str(report.relative_to(config.ROOT))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        _INFERENCE_LOCK.release()


@app.get("/api/experiments/{switches}/{logical_id}/{physical_id}/inference")
def latest_inference(switches: int, logical_id: int, physical_id: int):
    switches, logical_id, physical_id = _ids(switches, logical_id, physical_id)
    run_dir = runs.local_copy_path(switches, logical_id, physical_id)
    derived = run_dir.parent / (run_dir.name + "_derived")
    reports = sorted(derived.glob("inference_*.json")) if derived.is_dir() else []
    if not reports:
        return {"available": False}
    payload = json.loads(reports[-1].read_text(encoding="utf-8"))
    payload["available"] = True
    payload["report_path"] = str(reports[-1].relative_to(config.ROOT))
    return payload


# --------------------------------------------------------------------------- saved results
@app.get("/api/results/comparison")
def comparison(switches: Optional[int] = None):
    data = saved_results.comparison()
    if switches is not None:
        switches = _switches(switches)
        data = {**data, "rows": [r for r in data["rows"] if r["switch_count"] == switches]}
    return data


@app.get("/api/results/evaluation")
def evaluation(switches: int = SwitchesQuery):
    try:
        return saved_results.evaluation(_switches(switches))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/results/xai")
def xai():
    return {"kind": "saved explanation reports", "topologies": saved_results.xai_index()}


@app.get("/api/results/xai/{switches}/{experiment_id}")
def xai_experiment(switches: int, experiment_id: int):
    try:
        return saved_results.xai_experiment(_switches(switches), experiment_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/results/history")
def history(include_vm: bool = True):
    out = {"saved": saved_results.history(), "dashboard_runs": runs.local_runs(), "vm": {}}
    if include_vm:
        for switches in (8, 12):
            try:
                out["vm"][str(switches)] = vm.list_runs(switches)
            except vm.VMError as exc:
                out["vm"][str(switches)] = {"error": str(exc)}
    return out
