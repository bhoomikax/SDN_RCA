# SDN RCA end-to-end runbook

This runbook separates the supported offline v3 reproduction/demo from
physical experiments. The offline pipeline is reproducible from the preserved
candidate and evaluation artifacts. One isolated live run (logical 41 /
physical 45) was carried end to end to held-out inference; its derived
artifacts are reproducible offline from preserved evidence (section 4). **No
further physical run is authorized**: every registered ID pair is consumed,
and the proposed 12-run low-load cohort still needs a normal-only mode and
phase-attributed receiver intervals. Do not reuse an ID.

What the outputs mean:

- **Retrospective localization (implemented):** given the annotated fault
  phase, rank the three inter-switch links for the first 10 seconds of that
  phase. All Top-k numbers in this project are of this kind.
- **Online detection (not working):** finding the fault onset without phase
  labels. The phase-blind q99 baseline detected 0/25 fault windows.
- **Causal root-cause discovery (not implemented):** no model infers causal
  structure. Telemetry deltas are descriptive associations only.

## 1. Machine responsibilities and current state

- **Windows checkout:** source, Python ML environment, frozen candidate,
  graph artifacts, evaluation, and demo.
- **Ubuntu Mininet VM:** Ryu controller, Mininet/OVS, iperf2, and the
  recollection runner. The runner starts/stops its own Mininet topology,
  traffic, and telemetry collector; it expects the Ryu controller to be
  running already.
- The verified Windows environment is Python 3.13.7 with CPU PyTorch. Its
  direct dependencies are in `requirements-windows.txt`.
- The VM was verified as Python 3.8.5 with Mininet, OVS 2.13.1, Ryu, and
  iperf2 2.0.13. SSH is forwarded to `127.0.0.1:2222`. Select the existing
  key explicitly; do not copy or disclose the private key:

  ```powershell
  $VmKey = Join-Path $env:USERPROFILE ".ssh\mininet_vm_ed25519"
  ssh -i $VmKey -p 2222 -o IdentitiesOnly=yes -o BatchMode=yes mininet@127.0.0.1 "hostname; python3 --version; command -v mn; command -v ovs-vsctl; command -v ryu-manager; command -v iperf"
  ```

  On the audited VM this returned `mininet-vm`, Python 3.8.5, and all four
  commands. Without `-i`, key authentication failed because the SSH config
  does not select the non-default key.
- The Ryu process was already running as
  `/home/mininet/.local/bin/ryu-manager controller.py`, listening on 6633 and
  6653. Its `controller.py` is on the VM and is not in this Windows checkout.
  Thus controller deployment is an external VM prerequisite, not a component
  reproducibly built from this repository.

## 2. Prepare Windows

For a new Windows environment, from the repository root:

```powershell
py -3.13 -m venv venv
.\venv\Scripts\python.exe -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-windows.txt
.\venv\Scripts\python.exe -m pip check
```

The checked-in environment was verified with:

```powershell
.\venv\Scripts\python.exe --version
.\venv\Scripts\python.exe -c "import numpy,pandas,sklearn,torch,torch_geometric; print(numpy.__version__, pandas.__version__, sklearn.__version__, torch.__version__, torch_geometric.__version__)"
.\venv\Scripts\python.exe -m unittest discover -v
```

The last command passed 82 tests on the current source (2026-10-19). No Python
dependencies are required on Windows for a live Mininet network; live network
operations run inside the VM.

## 3. Verify the VM before touching the network

After starting the VM in its normal hypervisor, check the services and state:

```powershell
$VmKey = Join-Path $env:USERPROFILE ".ssh\mininet_vm_ed25519"
ssh -i $VmKey -p 2222 -o IdentitiesOnly=yes mininet@127.0.0.1 "ss -lnt; sudo -n ovs-vsctl list-br; ps -eo pid,stat,args | grep -E '[r]yu-manager|[m]n --|[i]perf'; timedatectl show -p NTPSynchronized --value"
```

Required before a new collection: the intended Ryu listener must be present,
no stale Mininet run or OVS bridge may conflict, the exact runner source and
profile hashes must be recorded, and the allocated ID pair must be unused.
The audited VM had the Ryu listener, no OVS bridges or active Mininet/iperf
processes, passwordless sudo, and `NTPSynchronized=no`. The clock state means
only within-run ordering is supportable; do not claim Windows/VM clock
alignment.

If the controller is stopped, the previously deployed VM command is:

```sh
cd /home/mininet/sdn_project
/home/mininet/.local/bin/ryu-manager controller.py
```

Run it in a dedicated VM terminal only if no controller is already listening.
This VM-side controller file is absent from the repository. Stop only a
controller process started for this run (Ctrl+C in its terminal, or verify
the exact PID/command before sending it SIGTERM); never use a broad `pkill`.

Do not run `mn -c` automatically. The runner fails closed when bridges or
occupied IDs are found. If stale resources appear, identify their owner first
and remove only resources belonging to a confirmed abandoned run.

## 4. Live collection: completed demo and safe contract

The live runner is `experiment_runner_recollection.py`. Its default invocation
is a read-only preflight. The `--run` flag creates an isolated run directory,
starts the linear two-host/four-switch Mininet topology, captures runtime
port-to-interface/peer mappings, collects port telemetry, sends the frozen
6 Mbps UDP profile, injects the registered link outage, records phases, and
stops its own network/processes in `finally`. It does **not** start or stop
Ryu.

Do not run the older `experiment_runner.py` for a new study: it uses a 25 Mbps
offered load and writes to legacy `experiments/`.

The current registry is explicit: logical/physical pairs are
`3/23`, `10/21`, `20/24`, `21/25`, `22/26`, `23/27`, `24/28`, `25/29`,
`26/30`, `27/31`, and the isolated-demo pairs `40/44` and `41/45`. All are
consumed. Physical run 44 was
attempted once with logical experiment 40, faulting `s2-s3` under the existing
6 Mbps 20/20/20-second profile. It is `FAILED_INVALID`, preserved separately,
and must not be rerun or admitted to a candidate. It is not part of v3 or the
repeatability cohort. The prospective logical 28–39 / physical 32–43
assignments in `TRAFFIC_PROFILE_REPEATABILITY_PROTOCOL.md` remain unreserved.
The runner still lacks normal-only controls and one-second receiver interval
parsing; implement those before calling any collection a repeatability cohort.

The runner source was staged separately at
`/home/mininet/sdn_project/live_demo_20261018_40_44`, so the existing
deployment and prior evidence were not overwritten. Use `sudo -n` for any
future runner preflight or execution: the VM's OVS database socket is
root-only, and unprivileged `ovs-vsctl list-br` fails with `Permission denied`.

Run 44's preserved evidence is under
`/home/mininet/sdn_project/live_demo_20261018_40_44/recollection_runs/physical_44_logical_40/`
and mirrored read-only to
`live_evidence_physical44_logical40/`. All six source files have a local
SHA-256 manifest there. The attempt produced 636 finite telemetry rows across
four switches, ordered phase events, and the expected reciprocal runtime
mapping `s2-eth2/ofport 2 ↔ s3-eth1/ofport 1`. Both iperf processes exited 0
and client/server packet summaries agree, but the receiver summary spans only
57.3 seconds versus the requested 60 seconds and violates the frozen ±2
second validity tolerance. Metadata therefore correctly remains
`FAILED_INVALID`; 11,864/32,100 sequence-accounted datagrams were reported
lost. This whole-run loss includes the intentional outage and is not a
baseline-loss estimate. The candidate builder refuses this status, so no
candidate, graph, or model inference was generated from run 44.

After the failed run, OVS had no bridges and no `mn` or `iperf` processes
remained; Ryu was left running. The VM clock reported
`NTPSynchronized=no`. Do not rerun physical ID 44 or change its preserved
status.

**Duration fix.** Run 44 showed that iperf2's receiver interval ends at the
last received datagram, so it can be shorter than the sender's 60 s when
packets are lost. The runner now requires the **sender** duration to be within
60 ± 2 s, both receiver reports (client Server Report and server log) to agree
within 0.25 s, both to report identical lost/total datagram counts, and a
positive delivered count. It records the receiver-to-sender gap rather than rejecting on it. Regression
test: `test_receiver_interval_may_be_shorter_than_sender_duration`.

**Run 45 (final authorized attempt, valid).** Staged separately at
`/home/mininet/sdn_project/live_demo_20261018_41_45` and run with
`sudo -n python3 -B experiment_runner_recollection.py --logical-id 41 --physical-id 45 --normal-seconds 20 --fault-seconds 20 --recovery-seconds 20 --run`.
Metadata `COMPLETE`; sender 60.0 s, receivers 58.3 s (agreeing); 11,378/32,099
datagrams lost over the whole run, including the outage. Its receiver span
would also have passed the old rule, so the fix did not decide the outcome.
The six raw files are mirrored to `live_evidence_physical45_logical41/`;
VM originals hash-match `SHA256SUMS.txt`. After the run, OVS had no bridges
and no Mininet/iperf processes; Ryu was left running.

Reproduce its candidate, graph, and held-out inference offline (no VM needed;
choose unused output paths, existing ones are refused):

```powershell
.\venv\Scripts\python.exe build_validated_candidate.py --run-dir live_evidence_physical45_logical41 --output-dir derived_datasets\NEW_LIVE_CANDIDATE
.\venv\Scripts\python.exe build_graph_multi.py --input derived_datasets\NEW_LIVE_CANDIDATE\candidate_dataset.csv --output derived_graphs\NEW_LIVE_GRAPH\graph_dataset.json
.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 41 --method rf_baseline --dataset derived_datasets\live_demo_physical45_logical41\candidate_dataset.csv
```

Expected: candidate SHA-256 `bf8e6154…2cb1f0c` (12,240 rows; the clean-17
historical candidate plus run 41), 1,020 graph snapshots, and ranking
`s2-s3 > s1-s2 > s3-s4` with experiment 41 absent from the 17 training IDs.
The retrospective label is `s2-s3` (Top-1 hit). The preserved outputs and a
SHA-256 manifest are in `reports/live_demo_physical45_logical41/`. The
candidate builder rejects run 44 because of its `FAILED_INVALID` status. Runs
30/31 are not inputs. A single-run prediction is demonstration output, not a
validation estimate.

## 5. Reproduce the supported data-to-graph-to-ranking path

The committed candidate is
`derived_datasets/balanced_recollection_20261015_v3/candidate_dataset.csv`
(16,956 rows, 25 experiments). Its master and candidate hashes are recorded in
`project_inventory.json`. The committed graph snapshot contains 1,413
snapshots, and its source hash matches the candidate. A graph rebuild has been
tested in a temporary directory; use an unused output path if rebuilding:

```powershell
.\venv\Scripts\python.exe build_graph_multi.py --input derived_datasets\balanced_recollection_20261015_v3\candidate_dataset.csv --output derived_graphs\NEW_GRAPH_DIR\graph_dataset.json
```

Do not use a path that already exists. The validated 25-fold RF/topology and
grouped neural outputs are already preserved; do not overwrite or rerun them
for a demo. Fresh single-experiment RF inference refits its model and
preprocessing on the other 24 experiments:

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 20 --method rf_baseline
```

The current verified output ranks `s2-s3 > s3-s4 > s1-s2`; the retrospective
fault label is `s1-s2`, missed at Top-2. This is a held-out, phase-oracle
localization demo, not inference on a newly collected run. To store the JSON
report, choose a new output file and check the process exit code:

```powershell
$Report = ".\demo_outputs\fresh_inference_experiment20.json"
if (Test-Path $Report) { throw "Refusing to overwrite $Report" }
New-Item -ItemType Directory -Force (Split-Path $Report) | Out-Null
& .\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 20 --method rf_baseline | Tee-Object -FilePath $Report
if ($LASTEXITCODE -ne 0) { throw "Fresh inference failed with exit code $LASTEXITCODE" }
```

Saved replay is a separate operation and does not train or predict:

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --mode saved-replay --experiment-id 20 --method rf_baseline
```

The graph-temporal LOEO evaluator compares all three neural paths on the same
25 held-out experiments; it is a full evaluation, not a single-run inference
command. Its verified package is
`evaluations/graph_temporal_v3_grouped_loeo_verified/`. No online detector or
causal explanation is validated.

## 6. Shutdown and troubleshooting

- The recollection runner owns Mininet and its collector/iperf processes and
  runs bounded cleanup. Let it finish; retain metadata and logs if it fails.
- Leave the shared Ryu process running unless you started that exact process
  for this session. Stop your own foreground Ryu process with Ctrl+C.
- After an interrupted run, inspect process ownership and
  `sudo -n ovs-vsctl list-br`. Do not kill unrelated processes or clear OVS
  state blindly.
- If SSH fails, verify the VM is running and port 2222 is forwarded, then use
  the explicit key path above. Never paste or replace private-key contents.
- If controller port 6633 is absent, do not launch a second controller;
  inspect the existing PID and the VM-side `controller.py` first.
- If preflight reports a used ID or existing bridge, stop. Select no new IDs
  until the run registry/protocol is formally extended.
- `sha256sum -c` on Git Bash may report `FAILED open or read` for evidence
  manifests that have CRLF line endings. Use
  `tr -d '\r' < SHA256SUMS.txt | sha256sum -c -` inside the evidence folder.
- If `demo_rca_v3.py` reports a hash mismatch, the candidate or a saved
  evaluation file has changed; restore it from Git rather than regenerating.
- If a live run completes but has inadequate telemetry, loss, mapping, or
  process evidence, preserve it as invalid/provisional and do not feed it into
  model evaluation.

## 7. Verified state and research limits

On 2026-10-19, Windows passed 82 unit tests; saved replay and fresh
inference for experiment 20 ran successfully; the run-45 candidate,
graph, and inference were reproduced in a scratch directory (candidate and
inference byte-identical; graph/provenance differ only in recorded paths);
and all frozen dataset/evaluation hashes in `project_inventory.json` matched.
On the VM, the deployed 41/45 runner and tests hash-match the Windows source;
compilation and 41 runner tests passed under Python 3.8.5. Read-only VM
inspection found Ryu active, no OVS bridges or active Mininet/iperf process,
and an unsynchronized clock.

Physical 45 is a single exploratory engineering run and so is the earlier
physical-31 pilot. Neither is a repeatability study or part of v3. Its whole-run loss cannot separate
normal from outage loss, cleanup lacks an independent post-run snapshot, and
cross-machine timing is not established. The online detector remains a failed
baseline (0/25 fault windows detected). Conditional localization and the
exploratory neural results do not establish causal RCA or model superiority.
