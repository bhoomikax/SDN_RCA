# SDN Fault Localisation — Research Demo dashboard

A web frontend and a small API for demonstrating the existing research pipeline:
live experiment runs on the Mininet VM, live telemetry, five-model faulty-link
inference on a newly collected run, and the saved, audited evaluation and
explainability results. Nothing in the research pipeline was changed; the
dashboard calls the repository's own modules and the VM runner.

## Architecture

```
browser (Next.js 15, Tailwind 4, Recharts)  http://localhost:3000
        |  fetch / polling (2 s for live state)
        v
FastAPI service  http://127.0.0.1:8765  (dashboard/backend, runs in the repo venv on Windows)
        |  imports: build_topology_candidate, build_graph_multi, evaluate_topology_loeo,
        |           graph_temporal_topology, linear_topology, telemetry_pipeline
        |  reads:   results/, derived_datasets/, raw_evidence/ (read-only)
        |  writes:  dashboard_runs/ (fetched runs + derived candidate/graph/inference reports),
        |           dashboard/backend/state/active_run.json (run lock)
        |  ssh -i <key> -o BatchMode=yes -p 2222 mininet@127.0.0.1   (fixed argument lists, timeouts)
        v
Ubuntu Mininet VM: /home/mininet/sdn_project/topology_scaling_20261023
        sudo -n python3 -B experiment_runner_recollection.py --switches N --logical-id L --physical-id P [--run | --verify-topology]
        run files: recollection_runs/topology_N_switches/physical_P_logical_L/{run_metadata.json, phase_events.csv, telemetry.csv, ...}
        dashboard log: dashboard_logs/run_N_switches_physical_P_logical_L.log
```

Why the backend lives on Windows: the VM has Python 3.8 and no PyTorch; all
analysis code and checkpoints are on the host. The VM is only ever driven
through the existing runner. The runner writes its metadata, phase events and
telemetry incrementally, so the dashboard shows progress by reading those files
(through `sudo -n cat`, because run directories are root-owned) and by checking
whether the runner process is alive. No timers are simulated.

## Prerequisites

- The repository venv (`venv/`, Python 3.13) with the pinned research
  dependencies, plus `fastapi` and `uvicorn` (installed into the venv for this dashboard).
- Node.js 22 and npm (verified with Node v22.18.0, npm 10.9.3).
- The Mininet VM running, SSH forwarded to `127.0.0.1:2222`, the key at
  `%USERPROFILE%\.ssh\mininet_vm_ed25519`, passwordless `sudo -n` for `mininet`,
  the Ryu controller listening on `127.0.0.1:6633` inside the VM, and the runner
  staged in `/home/mininet/sdn_project/topology_scaling_20261023` (see
  `docs/TOPOLOGY_SCALING_RUNBOOK.md`, section 3). The dashboard checks that the
  VM runner's SHA-256 equals the local source.
- Port 8765 free on the host (8000 is used by Docker Desktop on this machine).

## Installation

From the repository root (PowerShell):

```powershell
.\venv\Scripts\python.exe -m pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.30,<1"
cd dashboard\frontend
npm install
cd ..\..
```

## Starting

Terminal 1 — backend (binds to 127.0.0.1:8765; API docs at http://127.0.0.1:8765/api/docs):

```powershell
.\venv\Scripts\python.exe dashboard\backend\serve.py
```

Terminal 2 — frontend:

```powershell
cd dashboard\frontend
npm run dev          # development server on http://localhost:3000
# or: npm run build; npm run start
```

Optional environment variables (backend): `SDN_VM_SSH_KEY`, `SDN_VM_HOST`,
`SDN_VM_PORT`, `SDN_VM_USER`, `SDN_VM_PROJECT_DIR`, `SDN_DASHBOARD_PORT`,
`SDN_DASHBOARD_ORIGIN` (CORS origin, default `http://localhost:3000`),
`SDN_DASHBOARD_TOKEN` (when set, control endpoints require the
`X-Dashboard-Token` header; store it in the browser with
`localStorage.setItem("sdn.dashboard.token", "<token>")`). Frontend:
`NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8765`).

## Verifying connectivity

Open **System Health**. Every row is tested at request time: backend
reachability, SSH key file, SSH login, controller listener on 6633 (tested from
inside the VM with `ss`), Mininet / OVS / iperf availability and passwordless
sudo, runner hash match, VM clock (not NTP-synchronised), saved artifacts,
checkpoints and inference libraries. Labels are Connected / Disconnected /
Unknown / Not Tested; a configured address alone never shows green.

Equivalent command-line check:

```powershell
ssh -i "$HOME\.ssh\mininet_vm_ed25519" -o IdentitiesOnly=yes -o BatchMode=yes -p 2222 mininet@127.0.0.1 "ss -ltn | grep 6633; sudo -n ovs-vsctl list-br"
```

## Running the 12-switch demonstration

1. **Live Demo** → topology `12 switches`. The form is prepopulated with
   logical 248 / physical 1248. That pair was already executed on the VM
   (status COMPLETE, fault `s4-s5`), so the preflight will report the conflict
   ("Refusing to reuse run directory"); click **Use next free pair** (the
   dashboard reads the VM and offers the first unused registered pair; the
   fault link follows the registry's round-robin schedule) or pick any unused
   registered pair. Registered pairs are logical 201–260 with physical =
   logical + 1000; IDs outside the registry are rejected by both the dashboard
   and the runner. Phase durations are fixed at 20/20/20 s by the frozen
   traffic profile.
2. **Run preflight (read-only)**: ID validation, VM probe (controller, bridges,
   busy processes, sudo) and the runner's own preflight. Nothing is created.
3. Optional **Verify topology**: after confirmation, starts and stops the
   12-switch network and reports 11 observed links and ping loss. No run
   directory, no fault.
4. **Start experiment**: enabled only after a clean preflight. The confirmation
   explains that the topology is deployed and the configured link is brought
   down for 20 s. The dashboard locks (one run at a time), launches the real
   runner with `--run` in the background on the VM and selects the run.
5. Watch **Experiment lifecycle** (phase events + VM clock), the topology
   diagram (the configured link is drawn as "DOWN (live)" only while the
   runner's phase events say the fault phase is in progress), and the live
   charts. A run takes about 100 s (60 s traffic plus setup/teardown).
6. When the state is `complete`, click **Fetch run and rank candidate links**.
   The six raw files are copied into `dashboard_runs/topology_12_switches/`,
   admitted by `build_topology_candidate` (the research admission rules,
   including the ±10 % offered-rate rule), converted to graph snapshots, and
   ranked by all five models. A run that fails admission is reported with the
   recorded reason and cannot be ranked.
7. **Live Telemetry**, **Saved Experiments** (logs) and **XAI** complete the tour.

The already completed run 248/1248 can be selected from the "Select VM run"
list and ranked immediately without running anything (its result on this
machine: all four learned models ranked `s4-s5` first; the topology ranker put
it 6th of 11). Verification runs made through the dashboard on 2026-10-28:
249/1249 failed inside the runner (iperf server did not exit within its
bounded wait, a known intermittent VM failure mode) and is shown as
FAILED_INVALID with that reason; 250/1250 completed (fault `s6-s7`) and all
four learned models ranked `s6-s7` first, the topology ranker last.

## Where files go

| What | Where |
|---|---|
| VM run directories | `/home/mininet/sdn_project/topology_scaling_20261023/recollection_runs/topology_N_switches/physical_P_logical_L/` (root-owned) |
| Runner console log of dashboard-launched runs | `.../topology_scaling_20261023/dashboard_logs/run_N_switches_physical_P_logical_L.log` |
| Fetched copies | `dashboard_runs/topology_N_switches/physical_P_logical_L/` |
| Derived candidate, graph, inference reports | `dashboard_runs/topology_N_switches/physical_P_logical_L_derived/{candidate,graph,inference_<timestamp>.json}` |
| Run lock | `dashboard/backend/state/active_run.json` |
| Saved research results (read-only) | `results/`, `results/xai/`, `results/comparison_4_8_12/`, `derived_datasets/balanced_recollection_20261015_v3/` |

`dashboard_runs/` is separate from `raw_evidence/` and from every research
candidate; nothing is merged automatically. To admit a dashboard run into the
research data, use the documented offline pipeline in
`docs/TOPOLOGY_SCALING_RUNBOOK.md` deliberately.

## Which features are live and which show saved results

Live (read from the VM or computed now):

- System Health rows; registry availability and VM run listing.
- Preflight, verify-topology, start, run status, phase timeline, live telemetry
  charts and per-port table (parsed from the runner's `telemetry.csv`).
- Inference on a fetched run: Random Forest and topology ranker refit on the
  saved admitted candidate of the same topology (26 experiments for 12 switches,
  24 for 8); GCN / LSTM / GCN+LSTM scored with the saved LOEO fold-1 checkpoints
  (three seeds, mean softmax; each checkpoint was trained on 25 of the 26
  research experiments and never saw the new run). TreeSHAP attributions for the
  live RF prediction.

Saved (labelled "SAVED EVALUATION RESULTS" / "saved explanation report"):

- Model Results, Model Comparison (`results/comparison_4_8_12/comparison.json`
  with exact counts; the Markdown table is rounded for display only), XAI
  reports (`results/xai/topology_N_switches/experiments/experiment_<id>.{json,md}`),
  admitted research experiments and exclusions.

## Known limitations and troubleshooting

- **Conditional localisation only.** The fault window is the first 10 s of the
  run's own annotated fault phase. The dashboard does not detect faults online
  and does not claim causal root-cause identification; scores are uncalibrated
  ranking scores.
- **No stop button.** The runner has no safe cancellation path; killing it would
  leave Mininet state behind. Runs clean up on their own (about 100 s).
- **Four-switch live runs are not offered**: the four-switch ID registry is
  exhausted. Saved four-switch results and explanations are available.
- **Neural live inference uses saved fold checkpoints**, not a fresh fit on all
  26 experiments (a fresh three-seed fit per model takes minutes on CPU). The
  report records which checkpoints and training IDs were used.
- **Keep the host idle during a run.** The VM has one vCPU; host CPU load has
  caused iperf under-pacing (~3 Mbps) and the run is then rejected by the
  offered-rate rule. Keep the laptop on mains and awake.
- **"Refusing to reuse run directory"**: the ID pair is used; pick the next free pair.
- **"OVS bridges already exist" / busy processes**: a previous run did not clean
  up; follow the runbook (`cleanup_abandoned_run.py`, never `mn -c` blindly).
- **"VM unavailable: VM command timed out"**: SSH commands are serialised and
  short probes are cached, because concurrent ssh sessions from this host were
  observed to stall. If it still appears, the VM itself is saturated (a run in
  progress on one vCPU) or asleep; wait for the run to finish and retry. Restart
  the backend after pulling code changes.
- **Backend unreachable**: start `serve.py`; if port 8765 is taken set
  `SDN_DASHBOARD_PORT` and `NEXT_PUBLIC_API_BASE`.
- **SSH Disconnected**: check the VM is running, port 2222 is forwarded and the
  key path (`SDN_VM_SSH_KEY`).
- The VM clock is not NTP-synchronised; elapsed times use the VM clock and only
  within-run ordering is meaningful.

## Tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s dashboard\backend\tests -v   # backend (offline; SSH is faked)
.\venv\Scripts\python.exe -m unittest discover -v                               # research suite (unchanged)
cd dashboard\frontend; npx tsc --noEmit; npm run build                          # frontend type check and production build
```
