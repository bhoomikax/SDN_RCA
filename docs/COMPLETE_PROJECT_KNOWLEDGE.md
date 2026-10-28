# SDN Root-Cause Analysis: complete project knowledge and viva reference

Written 2026-10-25 from the current repository state (HEAD `2f687b3` plus the
uncommitted topology-scaling work). Every statement below is tagged where it
matters: **[source]** means read from code, **[artifact]** means read from a
generated dataset, log, or evaluation output, **[doc]** means stated in
project documentation but not independently re-measured here, and
**[interpretation]** means the author's reading of the evidence. Paths are
repository-relative; the VM paths are under `/home/mininet/sdn_project/`.

---

## 1. Project overview

### 1.1 Title and problem statement

**Topology-aware, temporally informed root-cause analysis for software-defined
networks: conditional faulty-link localization on linear Mininet topologies
with Random Forest, a topology heuristic, GCN, LSTM, and GCN+LSTM, with an
explainability layer.**

A software-defined network (SDN) separates the control plane (a controller
program that decides how packets are forwarded) from the data plane (switches
that forward packets according to flow rules installed by the controller).
Here the controller is Ryu, the switches are Open vSwitch (OVS) instances
emulated by Mininet, and the only measurements are the per-port packet and
byte counters that every OpenFlow switch exposes.

The problem solved: **given per-port telemetry from all switches during a
known fault window, rank the inter-switch links by how likely each one is the
link that failed.** The output is an ordered list of candidate links with a
score for each. On a chain of N switches there are N-1 candidate links: 3, 7,
and 11 for the 4-, 8-, and 12-switch topologies **[source: `linear_topology.py`]**.

### 1.2 Why faulty-link localization matters

When a link goes down, traffic downstream of it disappears everywhere at
once, so every switch past the fault looks "anomalous". An operator sees many
symptoms and needs the origin. Automating "which link?" shortens repair time.
In an SDN the controller already has the topology and can collect counters,
so the method needs no extra probes.

### 1.3 Exact scope and what is out of scope

In scope **[source + doc]**:

- Conditional localization: the annotated fault phase selects the first ten
  seconds of each fault; models rank candidate links within that window.
- One fault type: link failure (both interface ends set administratively
  down for 20 s, then up) on one inter-switch link per experiment.
- Three linear topologies (4, 8, 12 switches), one UDP flow h1 -> h2 at
  6 Mbps, one 10 Mbps / 5 ms bottleneck on the middle link.
- Leave-one-experiment-out (LOEO) evaluation grouped by experiment.
- Explanations for each model's ranking with validation checks.

Out of scope (explicitly stated in the project's own documents and verified
by the code paths that exist):

- **Online detection** (finding *when* a fault starts without phase labels).
  A phase-blind q99 anomaly detector exists (`evaluate_online_fault_detection.py`)
  and detected 0/25 fault windows on the four-switch data **[doc:
  `docs/RESULTS_BALANCED_V3.md`]**; it is a documented negative result.
- **Causal root-cause discovery.** No module infers causal structure.
- **Probability calibration.** Scores are vote fractions, softmax outputs, or
  rank utilities, never calibrated probabilities.
- Non-linear topologies, multiple simultaneous faults, other fault types,
  other traffic profiles.

### 1.4 Inputs, pipeline, outputs, users

- **Inputs:** OVS port counters sampled about once per second
  (`ovs-ofctl dump-ports`), phase event timestamps written by the runner,
  the runtime OpenFlow-port-to-interface mapping (`ovs-ofctl show`), and
  iperf client/server logs.
- **Pipeline:** collect raw run -> admit/reject -> candidate dataset ->
  (graph snapshots) -> per-fold features/normalization -> model -> ranking
  -> metrics -> explanation.
- **Outputs:** per-experiment rankings and scores, Top-1/Top-2/MRR with
  intervals, per-experiment explanation reports, comparison tables and a
  plot, an audit report.
- **Users:** the research project itself (a student thesis/project). A
  practical analogue would be an operator dashboard that lists the most likely
  failed links after an alarm; that dashboard is **not** built here.

### 1.5 Novelty and implemented-versus-proposed

Implemented and measured: the five-model comparison under grouped LOEO on
three topology sizes with real Mininet runs; a generalized collection and
evaluation pipeline parameterized by switch count; a validated XAI layer; an
independent audit script that recomputes every reported number.

Proposed or partially explored but **not** delivered as validated results:
online fault detection (negative result), a repeatability cohort for traffic
profiles (`docs/TRAFFIC_PROFILE_REPEATABILITY_PROTOCOL.md`), causal analysis.
The novelty claim the evidence supports is modest: **a careful, leak-free,
auditable comparison showing that learned models localize link failures far
above chance on 4-, 8-, and 12-switch chains, while a hand-built topology
heuristic does not transfer beyond 4 switches.** No model is shown superior to
another learned model.

---

## 2. Complete system architecture

### 2.1 Components and roles

| Component | Where | Role |
|---|---|---|
| Mininet | VM (`/usr/local/lib/python3.8/dist-packages/mininet`) | Creates hosts, OVS switches, veth links with optional `TCLink` bandwidth/delay; runs `iperf` inside host namespaces. **[source: `_create_network` in `experiment_runner_recollection.py`]** |
| Open vSwitch 2.13.1 | VM | Data plane. Exposes port counters via `ovs-ofctl -O OpenFlow13 dump-ports <switch>` and port names via `ovs-ofctl show`. **[source: `telemetry.py`]** |
| Ryu controller | VM, `/home/mininet/sdn_project/controller.py` (not in this repository) | `SimpleSwitch` learning switch, OpenFlow 1.3: installs a table-miss flow to the controller, learns MAC->port, installs `in_port + eth_dst + eth_src` flows at priority 1, floods unknown destinations. **[source: read from the VM]** |
| iperf2 2.0.13 | VM | UDP traffic h1 -> h2: client `iperf -c 10.0.0.2 -u -b 6M -t 60 -p 5001`, server `iperf -s -u -p 5001 -t 75`. **[source]** |
| `telemetry.py` | VM + Windows | Collector: loops over switches, parses `dump-ports`, computes per-second rate/throughput deltas, appends CSV rows. **[source]** |
| `experiment_runner_recollection.py` | VM (run as root) | Orchestrates one experiment: preflight, topology, runtime mapping, collector, iperf, fault injection, phase events, validation, cleanup. **[source]** |
| `run_topology_batch.py` | VM | Runs registered IDs sequentially; fails closed. **[source]** |
| `build_topology_candidate.py` | Windows | Admission and candidate dataset for 8/12 switches. The four-switch candidate came from `build_validated_candidate.py`. **[source]** |
| `build_graph_multi.py` | Windows | Per-timestamp graph snapshots (node features = per-switch sums of 4 rate metrics). **[source]** |
| `evaluate_topology_loeo.py` | Windows | RF + topology ranker, grouped LOEO, K candidates. **[source]** |
| `graph_temporal_topology.py`, `evaluate_graph_temporal_topology_loeo.py` | Windows | GCN, LSTM, GCN+LSTM models and their grouped LOEO. **[source]** |
| `explain_rca.py` | Windows | XAI with validation checks; per-experiment JSON + Markdown reports. **[source]** |
| `build_topology_comparison.py`, `audit_topology_results.py` | Windows | Comparison table/plot; independent recomputation. **[source]** |

Windows runs Python 3.13.7 in `venv/` with numpy 2.5.3, pandas 3.0.6,
scikit-learn 1.9.1, torch 2.14.0 (CPU), torch-geometric 2.8.0.post1,
shap 0.54.1 **[source: `requirements-windows.txt`]**. The VM runs Ubuntu
20.04 with Python 3.8.5; the runner, collector, topology module, and batch
script are written to stay Python-3.8 compatible **[source: `%`-formatting and
no 3.9+ syntax in those files; verified by running their tests on the VM]**.

### 2.2 Architecture diagram (from the code)

```mermaid
flowchart TD
  subgraph VM["Ubuntu VM (1 vCPU): Mininet / OVS 2.13.1 / Ryu / iperf2"]
    RYU[Ryu SimpleSwitch<br/>controller.py<br/>OpenFlow 1.3, ports 6633/6653]
    BATCH[run_topology_batch.py<br/>sequential registered IDs<br/>fails closed] --> RUNNER
    RUNNER[experiment_runner_recollection.py --switches N --run<br/>preflight -> Mininet net -> runtime mapping<br/>collector -> iperf -> fault -> phases -> validation -> cleanup]
    TOPO[linear_topology.py<br/>N switches, N-1 candidates,<br/>bottleneck on middle link, ID registry] --> RUNNER
    RUNNER --> NET[Mininet: h1 - s1 ... sN - h2<br/>TCLink 10 Mbps / 5 ms on middle link]
    NET <-->|OpenFlow 1.3| RYU
    RUNNER --> COLL[telemetry.py collect()<br/>ovs-ofctl show + dump-ports per switch<br/>~1 s loop, 65 s]
    RUNNER --> IPERF[iperf -c 10.0.0.2 -u -b 6M -t 60<br/>iperf -s -u -t 75]
    RUNNER -->|ip link set dev X down / up<br/>on both ends| FAULT[link fault 20 s]
    RUNNER --> RAW[(run dir: telemetry.csv, phase_events.csv,<br/>runtime_port_mapping.csv, run_metadata.json,<br/>iperf_client.log, iperf_server.log)]
  end
  RAW -->|tar + scp, SHA256SUMS| EVID[(raw_evidence/topology_N_switches/)]
  EVID --> BUILD[build_topology_candidate.py<br/>admission rules, phase labels]
  BUILD --> CAND[(results/topology_N_switches/candidate/<br/>candidate_dataset.csv, manifest,<br/>link_port_mapping.csv, exclusion_report.csv, provenance.json)]
  CAND --> GRAPH[build_graph_multi.py --switches N]
  GRAPH --> SNAP[(graph/graph_dataset.json<br/>per-timestamp snapshots)]
  CAND --> RFT[evaluate_topology_loeo.py<br/>RF + topology ranker, grouped LOEO]
  SNAP --> NEU[evaluate_graph_temporal_topology_loeo.py<br/>GCN / LSTM / GCN+LSTM, 3 seeds, grouped LOEO]
  RFT -->|same-fold reference| NEU
  RFT --> XAI[explain_rca.py<br/>SHAP, IG + occlusion, component exposure<br/>+ validation checks]
  NEU -->|checkpoints| XAI
  RFT --> CMP[build_topology_comparison.py]
  NEU --> CMP
  XAI --> CMP
  RFT --> AUD[audit_topology_results.py<br/>recompute everything]
  NEU --> AUD
  XAI --> AUD
```

### 2.3 Execution order and communication

1. **Preflight** (`preflight(logical_id, physical_id, switch_count)`
   **[source]**): verifies the ID pair against the registry, refuses an
   existing run directory, loads and validates the frozen traffic profile
   (offered 6 Mbps must be at most 70% of the 10 Mbps bottleneck and the
   profile's bottleneck link must equal the topology's), checks that
   `iperf --version` is iperf2, that no OVS bridge named like the topology's
   switches exists, and that TCP 127.0.0.1:6633 (Ryu) accepts a connection.
2. **Network** (`_create_network(topology)`): `Mininet(controller=RemoteController,
   switch=OVSSwitch, link=TCLink, autoSetMacs=True)`, controller `c0` at
   127.0.0.1:6633, hosts h1/h2, switches `s1..sN` with `protocols="OpenFlow13"`,
   links in topology order; the middle candidate link gets `bw=10, delay="5ms"`.
3. **Runtime mapping** (`_runtime_mapping`): for each switch, `ovs-ofctl show`
   gives OpenFlow port -> interface name; the Mininet link list gives
   interface -> peer; rows are written to `runtime_port_mapping.csv`. The
   mapping is checked to cover exactly the Mininet switch interfaces.
4. **Target validation** (`_target_link`): the registered fault link must
   resolve to exactly one Mininet link whose two interfaces have reciprocal
   runtime mapping rows. Port numbers are read from OVS, never inferred.
5. **Collector**: a subprocess `python -c "from telemetry import collect; ..."`
   with duration 65 s (20+20+20+5) and the switch list. The runner waits for a
   first valid sample before writing the `normal` phase event
   (`record_normal_phase_after_sample`).
6. **Traffic**: iperf server on h2 (started 2 s before the client), client on
   h1 for 60 s at 6 Mbps.
7. **Fault**: after 20 s, `ip link set dev <intf> down` on both interfaces of
   the target link (`_set_link`), phase event `fault`; after 20 s, both set
   `up`, phase event `recovery`; 20 s more.
8. **Completion**: iperf client and server are waited for with bounded
   timeouts; logs are parsed (`validate_iperf_completion`); the sender rate is
   checked (`validate_offered_rate`); the collector's rows are validated
   (`finalize_run_metadata`: schema, finite values, phase events inside the
   telemetry span); status becomes `COMPLETE`.
9. **Cleanup** (`finally`): link set back up if a fault was attempted; iperf
   processes terminated and reaped; collector terminated if still running;
   `net.stop()`; metadata written. Any cleanup failure forces
   `FAILED_INVALID`.

Communication is through files (CSV/JSON in the run directory), subprocesses
(ovs-ofctl, iperf via Mininet's `host.popen`), and OpenFlow between OVS and
Ryu. Windows reaches the VM only over SSH (port 2222 forwarded) and SCP.

### 2.4 One experiment end to end (12-switch logical 230, physical 1230)

**[artifact: `raw_evidence/topology_12_switches/physical_1230_logical_230/`
and `results/topology_12_switches/`]**

1. Registry slot 29 -> fault link `s8-s9` (round-robin over 11 links).
2. Preflight passes; Mininet builds h1-s1-...-s12-h2 with the bottleneck on
   `s6-s7`; runtime mapping records `s8` port 2 <-> `s9` port 1 for `s8-s9`.
3. Collector samples 12 switches x 3 ports (LOCAL, 1, 2) every ~1.35 s.
4. iperf runs 60 s; at t = 20 s both ends of `s8-s9` go down; traffic beyond
   `s8` stops; at t = 40 s the link comes back.
5. Run validated: sender 60.0 s at 6.29 Mbit/s, receivers agree, phases
   ordered within telemetry -> `COMPLETE`.
6. Builder admits it; its rows get `phase` and `fault_location` labels from the
   phase timestamps.
7. Graph builder makes one snapshot per timestamp: 14 nodes (h1, s1..s12,
   h2), 13 undirected edges, 4 features per node.
8. In its LOEO fold the other 25 experiments train each model; the first ten
   seconds of its fault phase (6-8 snapshots) are scored; each model emits an
   11-way ranking.
9. `explain_rca.py` refits the RF fold, loads the three seed checkpoints per
   neural model, and writes `results/xai/topology_12_switches/experiments/experiment_230.{json,md}`.

### 2.5 Failure handling

- Any exception in `run()` marks the run `FAILED_INVALID` with the exception
  text and still runs cleanup. **[source]**
- The batch stops after 3 consecutive failures, or when bridges or
  Mininet/iperf processes are present before a run. **[source: `run_topology_batch.py`]**
- A run killed before cleanup (observed once, run 1208 during a VM suspend)
  leaves bridges; `cleanup_abandoned_run.py` removes only the resources that
  run recorded and refuses if any Mininet/iperf process is alive. **[source +
  artifact: `EXECUTION_LOG.md`]**
- The builder excludes any run that is not `COMPLETE` or fails any
  admission check and records the reason. **[source]**

---

## 3. Repository and code walkthrough

### 3.1 Inventory (important files only)

**Topology-scaling pipeline (this work):**

| Path | Responsibility |
|---|---|
| `linear_topology.py` | `LinearTopology(N)`: switches, hosts, candidate links, bottleneck, link definitions, nodes/edges, `link_name`, `remote_switches`, `to_metadata/from_metadata`; `balanced_fault_assignment`; `topology_run_registry(N)`; `registry_entry`; `assert_registries_disjoint`. |
| `experiment_runner_recollection.py` | Live runner (see 2.3). Also `verify_topology(N)` (`--verify-topology`), `validate_iperf_completion`, `validate_offered_rate`, `canonical_link_name`. |
| `telemetry.py` | `parse_port_interfaces`, `get_port_stats`, `collect(output, experiment_id, duration, interval, switches, ...)`; CLI `--output --experiment-id --switches`. |
| `telemetry_pipeline.py` | `TELEMETRY_FIELDS`, legacy readers, `is_adjacent_switch_link`. |
| `run_topology_batch.py` | Batch driver (`--switches --target-valid --max-runs --max-consecutive-failures`). |
| `cleanup_abandoned_run.py` | Evidence-driven cleanup (`--run-dir [--apply]`). |
| `build_topology_candidate.py` | `validate_topology_run`, `build_topology_candidate(switch_count, runs_root, output_dir)`. |
| `build_graph_multi.py` | `build_snapshots(frame, topology)`, `build(input, output, topology)`; CLI `--input --output --switches`. |
| `evaluate_topology_loeo.py` | `load_candidate`, `fold_inputs`, `fit_rf`, `rank_topology`, `summarize`, `evaluate(candidate_dir, switch_count, output_dir, static_mapping)`; CLI `--candidate-dir --switches --output-dir [--static-four-switch-mapping]`. |
| `graph_temporal_topology.py` | `prepare_examples`, `fit_feature_policy`, `normalize_sequence`, `GraphEncoder`, `GraphOnly`, `TemporalOnly`, `GraphTemporal`, `build_model`, `train_and_predict`, `load_checkpoint`. |
| `evaluate_graph_temporal_topology_loeo.py` | `read_reference`, `evaluate(graph, candidate, reference_dir, output_dir, switch_count, seeds, save_checkpoints)`; CLI `--switches --graph --candidate --reference-dir --output-dir [--seeds] [--save-checkpoints]`. |
| `explain_rca.py` | `explain_rf_fold`, `explain_topology_fold`, `explain_neural_fold`, `EnsembleScorer`, `integrated_gradients`, `occlusion_tests`, `write_markdown_report`, `run(...)`; CLI `--switches --candidate-dir --graph --rf-eval-dir --neural-eval-dir --output-dir [--experiments] [--static-four-switch-mapping] [--ig-steps]`. |
| `build_topology_comparison.py` | `collect_topology`, `write_outputs`, `plot`. |
| `audit_topology_results.py` | `audit_topology`, `sign_test_p`. |
| `traffic_profiles/udp_6mbps_v1.json`, `udp_6mbps_8sw_v1.json`, `udp_6mbps_12sw_v1.json` | Frozen profiles (6 Mbps UDP, 20/20/20 s, bottleneck `s2-s3`/`s4-s5`/`s6-s7`). |

**Four-switch study (frozen):** `build_validated_candidate.py`,
`evaluate_grouped_rca_generalized.py` (RF + ranker, 3 links),
`evaluate_validated_candidate.py` (wrapper), `evaluate_graph_temporal_link_rca.py`
(original neural models, fixed 6 nodes), `evaluate_graph_temporal_grouped_loeo.py`,
`evaluate_online_fault_detection.py`, `demo_rca.py`, `demo_rca_v3.py`,
`build_experiment_admission_ledger.py`, `experiment_runner.py` /
`experiment_runner_batch.py` (legacy 25 Mbps runners, not used for new data).

**Datasets and artifacts:**

| Kind | Path |
|---|---|
| Frozen 4-switch candidate | `derived_datasets/balanced_recollection_20261015_v3/candidate_dataset.csv` (16,956 rows, 25 experiments, SHA-256 `b63d0457...`) |
| Frozen 4-switch graph | `derived_graphs/balanced_recollection_v3_portsum/graph_dataset.json` (1,413 snapshots) |
| Frozen 4-switch evaluations | `evaluations/balanced_recollection_v3_loeo_release/`, `evaluations/graph_temporal_v3_grouped_loeo_verified/` |
| 4-switch regression outputs (new code on frozen data) | `results/topology_4_switches_regression/` |
| 8-switch raw evidence / candidate / graph / evaluations | `raw_evidence/topology_8_switches/` (30 runs), `results/topology_8_switches/{candidate,graph,loeo_rf_topology,loeo_neural}` |
| 12-switch raw evidence / candidate / graph / evaluations | `raw_evidence/topology_12_switches/` (44 runs), `results/topology_12_switches/...` |
| XAI | `results/xai/topology_{4,8,12}_switches/` |
| Comparison | `results/comparison_4_8_12/` |
| Audit | `results/audit/` |
| Backups (outside repo) | `C:\Users\ASUS\sdn-ml_backups\20261025T005215`, `...\20261025T210707` |

**Documentation:** `README.md`, `docs/TOPOLOGY_SCALING_RUNBOOK.md`,
`docs/RESULTS_TOPOLOGY_SCALING.md`, `docs/REVIEW_SUMMARY_TOPOLOGY_SCALING.md`,
`docs/END_TO_END_RUNBOOK.md`, `docs/RESULTS_BALANCED_V3.md`,
`docs/ARCHITECTURE.md`, `docs/LIMITATIONS.md`, `docs/DATASET_CARD*.md`,
`EXECUTION_LOG.md`, `project_inventory.json`.

**Tests:** 18 files, 115 tests (section 11).

### 3.2 Function-level call trace (new pipeline) **[source]**

```
run_topology_batch.main
  -> runner.topology_for(N) ; topology_run_registry(N)
  -> for each registered ID: runner.run_directory(l, p, N) ; environment_is_clean()
     -> subprocess: experiment_runner_recollection.py --switches N --logical-id l --physical-id p --run
        run() -> preflight() -> load_traffic_profile(topology=...) ; resolve_registry()
              -> _create_network(topology) ; net.start()
              -> _runtime_mapping(net, path, topology.switches) -> telemetry.parse_port_interfaces
              -> _target_link(net, l, peers, rows, target=fault_link)
              -> Popen(telemetry.collect ... switches=...)
              -> record_normal_phase_after_sample() -> wait_for_first_valid_sample()
              -> h2.popen(iperf -s ...) ; h1.popen(iperf -c ...)
              -> _set_link(down) ; mark("fault") ; _set_link(up) ; mark("recovery")
              -> validate_iperf_completion() ; validate_offered_rate()
              -> finalize_run_metadata() -> validate_sample_row(), validate_event_coverage()
              -> finally: cleanup
build_topology_candidate.build_topology_candidate
  -> validate_topology_run(run_dir, topology, registry) for each run
     -> build_validated_candidate._finite_nonnegative / _event_wall_time / read_csv
     -> experiment_runner_recollection.validate_iperf_completion
  -> phase assignment by wall-clock comparison ; writes candidate + manifest + mapping + exclusions + provenance
build_graph_multi.build -> build_snapshots(frame, LinearTopology(N))
evaluate_topology_loeo.evaluate
  -> load_link_ports() ; load_candidate()
  -> for held_out, train in ordered_grouped_splits(ids):
       fold_inputs() -> fit_active_metrics, switch_level_frame, fit_switch_baseline,
                        make_rf_vector (train + test), fit_port_baseline, port_scores, threshold
       fit_rf() ; stable_rf_ranking() ; rank_topology() ; ranking_record()
  -> summarize() per method ; writes grouped_evaluation.csv, split_assignments.csv,
     fold_feature_policy.csv, topology_ranker_components.csv, evaluation_summary.json, evaluation_provenance.json
evaluate_graph_temporal_topology_loeo.evaluate
  -> models.prepare_examples(graph, topology) ; read_reference(rf_dir, ...)
  -> for fold: models.fit_feature_policy(examples, train_ids, topology)
       for method in (graph_only, temporal_only, graph_temporal), for seed in (17, 42, 2026):
           models.train_and_predict(...) [-> build_model, normalize_sequence]
  -> mean-score ensemble ; evaluate_topology_loeo.summarize ; writes per_seed_predictions.csv,
     mean_seed_ensemble_predictions.csv, fold_feature_policy.csv, evaluation_summary.json, checkpoints/
explain_rca.run
  -> per experiment: explain_rf_fold (fold_inputs + fit_rf + shap.TreeExplainer),
     explain_topology_fold (components CSV), explain_neural_fold (load_checkpoint x3 -> EnsembleScorer
     -> integrated_gradients, occlusion_tests) ; write_markdown_report ; xai_summary.json
build_topology_comparison.main -> collect_topology x3 -> write_outputs -> plot
audit_topology_results.main -> audit_topology x3 -> methodology_audit.{json,md}
```

### 3.3 Entry points and exact commands

All commands below were executed in this project and their outputs exist
**[artifact]** unless marked *documented only*.

Windows (repository root, `.\venv\Scripts\python.exe`):

```powershell
# tests and checks (executed; 115 OK)
.\venv\Scripts\python.exe -m unittest discover
.\venv\Scripts\python.exe -m pip check
git diff --check

# 8-switch pipeline (executed)
.\venv\Scripts\python.exe build_topology_candidate.py --switches 8 --runs-root raw_evidence\topology_8_switches --output-dir results\topology_8_switches\candidate
.\venv\Scripts\python.exe build_graph_multi.py --switches 8 --input results\topology_8_switches\candidate\candidate_dataset.csv --output results\topology_8_switches\graph\graph_dataset.json
.\venv\Scripts\python.exe evaluate_topology_loeo.py --switches 8 --candidate-dir results\topology_8_switches\candidate --output-dir results\topology_8_switches\loeo_rf_topology
.\venv\Scripts\python.exe evaluate_graph_temporal_topology_loeo.py --switches 8 --graph results\topology_8_switches\graph\graph_dataset.json --candidate results\topology_8_switches\candidate\candidate_dataset.csv --reference-dir results\topology_8_switches\loeo_rf_topology --output-dir results\topology_8_switches\loeo_neural --save-checkpoints
.\venv\Scripts\python.exe explain_rca.py --switches 8 --candidate-dir results\topology_8_switches\candidate --graph results\topology_8_switches\graph\graph_dataset.json --rf-eval-dir results\topology_8_switches\loeo_rf_topology --neural-eval-dir results\topology_8_switches\loeo_neural --output-dir results\xai\topology_8_switches
# same with 12 for the 12-switch set (executed)

# four-switch regression on the frozen data (executed; reproduces the release exactly)
.\venv\Scripts\python.exe evaluate_topology_loeo.py --switches 4 --candidate-dir derived_datasets\balanced_recollection_20261015_v3 --static-four-switch-mapping --output-dir results\topology_4_switches_regression\loeo_rf_topology
.\venv\Scripts\python.exe evaluate_graph_temporal_topology_loeo.py --switches 4 --graph derived_graphs\balanced_recollection_v3_portsum\graph_dataset.json --candidate derived_datasets\balanced_recollection_20261015_v3\candidate_dataset.csv --reference-dir results\topology_4_switches_regression\loeo_rf_topology --output-dir results\topology_4_switches_regression\loeo_neural --save-checkpoints
.\venv\Scripts\python.exe explain_rca.py --switches 4 --candidate-dir derived_datasets\balanced_recollection_20261015_v3 --static-four-switch-mapping --graph derived_graphs\balanced_recollection_v3_portsum\graph_dataset.json --rf-eval-dir results\topology_4_switches_regression\loeo_rf_topology --neural-eval-dir results\topology_4_switches_regression\loeo_neural --output-dir results\xai\topology_4_switches --ig-steps 512

# comparison and audit (executed)
.\venv\Scripts\python.exe build_topology_comparison.py
.\venv\Scripts\python.exe audit_topology_results.py
```

VM (as root, in `/home/mininet/sdn_project/topology_scaling_20261023/`, system `python3` 3.8):

```sh
sudo -n python3 -B experiment_runner_recollection.py --switches 12 --verify-topology        # executed
sudo -n python3 -B experiment_runner_recollection.py --switches 12 --logical-id 228 --physical-id 1228 --normal-seconds 20 --fault-seconds 20 --recovery-seconds 20   # preflight only (no --run); documented
sudo -n nohup python3 -B run_topology_batch.py --switches 12 --target-valid 25 >> batch_12.log 2>&1 < /dev/null &   # executed
sudo -n python3 -B cleanup_abandoned_run.py --run-dir recollection_runs/topology_12_switches/physical_1208_logical_208 --apply   # executed once
cd /home/mininet/sdn_project && nohup /home/mininet/.local/bin/ryu-manager controller.py > ryu_20261025_postreboot.log 2>&1 &   # executed after the reboot
```

Every evaluator refuses to overwrite an existing output directory (`FileExistsError`) **[source]**.

---

## 4. SDN topology and networking

### 4.1 The linear topologies **[source: `linear_topology.py`]**

```
h1 - s1 - s2 - s3 - s4 - h2                          4 switches, candidates s1-s2, s2-s3, s3-s4 ; bottleneck s2-s3
h1 - s1 - s2 - ... - s8 - h2                          8 switches, 7 candidates ; bottleneck s4-s5
h1 - s1 - s2 - ... - s12 - h2                         12 switches, 11 candidates ; bottleneck s6-s7
```

- `candidate_links = ("s1-s2", ..., "s(N-1)-sN")`; `bottleneck_link =
  candidate_links[(N-1)//2]`; the bottleneck gets `{"bw": 10, "delay": "5ms"}`;
  all other links have no TC shaping. For N = 4 this reproduces the original
  study topology exactly (asserted by `test_linear_topology.py`).
- Hosts: h1 (10.0.0.1) attached to s1, h2 (10.0.0.2) to sN. Mininet's
  `autoSetMacs=True` gives deterministic MACs.
- Port mapping: Mininet adds links in the order h1-s1, s1-s2, ..., sN-h2, so
  on every switch OpenFlow port 1 faces the left neighbour and port 2 the right
  neighbour. This is **recorded at runtime** from `ovs-ofctl show`, not
  assumed, and all admitted runs of a topology agreed on it (the builder
  refuses to merge otherwise). For the historical four-switch data no runtime
  mapping exists for the 17 oldest runs, so the evaluator uses the
  setup-inferred static mapping (`--static-four-switch-mapping`) **[source + doc]**.
- Candidate identity: the link name `s{i}-s{i+1}`; the class index is its
  position in `candidate_links`. Link names for switch pairs are ordered
  numerically (`canonical_link_name`), which fixed a real bug: lexicographic
  sorting had produced `"s10-s9"` on the 12-switch topology **[source + log]**.
- Fault assignment per experiment: `balanced_fault_assignment` round-robins
  over the candidate links by registry slot, so every prefix of the schedule
  is balanced. Faults are **not** restricted to the middle link.

### 4.2 Controller behaviour **[source: `controller.py` read from the VM]**

Ryu `SimpleSwitch` (OpenFlow 1.3): on switch connect it installs a priority-0
table-miss rule sending packets to the controller; on each `PacketIn` it
learns `src MAC -> in_port`, and if the destination is known installs a
priority-1 flow matching `in_port, eth_dst, eth_src` with an output action,
otherwise floods. There is no topology discovery (no LLDP), no path
computation, and no reaction to link-down events; forwarding on a loop-free
chain works because flooding reaches the destination and flows are then
installed. **[interpretation]** After the fault the installed flows still
point to the dead link, so traffic simply stops beyond the fault, which is
exactly the symptom the models learn.

### 4.3 Fault injection and labeling **[source: runner]**

- Fault: `ip link set dev <left-intf> down` and `... <right-intf> down`
  executed inside the switch nodes (`intf.node.pexec`), then `up` after
  `fault_seconds`. Both ends go down, so neither endpoint carries traffic.
- Phase events are written to `phase_events.csv` with the VM's local time
  including UTC offset; telemetry timestamps are naive local time from
  `datetime.now().isoformat()` in the collector. The builder compares them as
  wall-clock values (`_event_wall_time` strips the offset) **[source]**.
- Labeling (builder): a telemetry row's `phase` is `normal` if its timestamp
  is before the fault event, `fault` if before the recovery event, else
  `recovery`; `fault_type` is `none`/`link_failure`; `fault_location` is
  `none` or the link name.
- The **fault window** used by every model is the first 10 s of rows/snapshots
  whose phase is `fault` (`EARLY_SECONDS = 10`) **[source]**. This is the
  "oracle": the model is told when the fault happened.

### 4.4 Traffic and telemetry

- Offered load: iperf2 UDP at `-b 6M` for 60 s with default datagram size,
  which iperf2 reports as 6.29 Mbit/s (all admitted new runs report exactly
  6.29) **[artifact: manifests]**. Over the whole run the receiver loses about
  10,700-11,500 of 32,100 datagrams, which includes the 20 s outage; this is
  not a baseline-loss estimate **[artifact + doc]**.
- Counters: `rx_packets, rx_bytes, rx_dropped, tx_packets, tx_bytes,
  tx_dropped` per OpenFlow port (cumulative). Derived per sample:
  `rx_packet_rate = max(0, delta packets) / interval`, `tx_packet_rate`,
  `rx_throughput_mbps = max(0, delta bytes) * 8 / interval / 1e6`,
  `tx_throughput_mbps`, where `interval = 1` is the **nominal** interval
  **[source: `telemetry.collect`]**. The loop sleeps 1 s after each sweep, so
  the real interval is 1 s plus sweep time: median 1.08 s (4 switches,
  **[doc]**), 1.23 s (8), 1.35 s (12) **[artifact: manifests]**. Rates are
  therefore inflated by the same factor within a topology; models normalize
  within topology, so this does not mix topologies.
- Ports sampled: `LOCAL`, `1`, `2` per switch; LOCAL is excluded from all
  features.
- Verification: `--verify-topology` starts the network, records the mapping,
  pings all hosts, measures a collector sweep, stops, and reports remaining
  bridges. Measured 2026-10-25 after the reboot: 11 links, 0% loss, sweep
  0.315 s **[artifact: log]**.

### 4.5 Known environment problems and recovery **[artifact: `EXECUTION_LOG.md`, runbook]**

- The single-vCPU VM is sensitive to host CPU contention: Windows compute
  jobs or the user's VS Code remote server (up to 89% CPU) coincided with iperf
  under-pacing (~3 Mbps) and sender stalls (73-163 s).
- The Windows host sleeps after 5 minutes on AC; two host suspends occurred
  mid-run. The guest kernel then logged `soft lockup - CPU#0 stuck for 9842s`
  and RCU stalls; afterwards only 3 of 13 twelve-switch attempts were valid.
- Recovery (approved): the documented `sudo reboot` did not work because
  systemd's bus was wedged; `sudo -n sync; sudo -n reboot -f` rebooted the
  guest. After the reboot: 0 kernel warnings, clean ext4 mount, Ryu restarted
  with the documented command, preflight passed, and 17/17 runs were valid.
- A temporary `SetThreadExecutionState` keep-awake process was used on the
  host during collection windows only.

---

## 5. Dataset and preprocessing

### 5.1 Raw run files **[source: runner]**

| File | Content |
|---|---|
| `telemetry.csv` | 15 columns: `timestamp, switch, port, rx_packets, rx_bytes, rx_dropped, tx_packets, tx_bytes, tx_dropped, rx_packet_rate, tx_packet_rate, rx_throughput_mbps, tx_throughput_mbps, interface_name, experiment_id` (the physical run ID). |
| `phase_events.csv` | `physical_run_id, logical_experiment_id, timestamp, phase, fault_type, fault_location` (3 rows). |
| `runtime_port_mapping.csv` | `switch, openflow_port, interface_name, peer_node, peer_interface, link`. |
| `run_metadata.json` | status, IDs, topology spec, traffic profile, phase events, iperf process records and parsed summaries, runtime mappings, timings. |
| `iperf_client.log`, `iperf_server.log` | raw iperf2 output. |

### 5.2 Candidate dataset schema **[source: `DATASET_FIELDS`]**

17 columns: the 13 telemetry data fields, then `experiment_id` (the
**logical** ID), `phase` (`normal|fault|recovery`), `fault_type`
(`none|link_failure`), `fault_location` (`none` or link). Example row
**[artifact]**:

```
2026-10-19T19:33:19.259303,s1,1,0,0,0,0,0,0,0.0,0.0,0.0,0.0,201,normal,none,none
```

Counters are integers (cumulative), rates are floats per nominal second,
throughput in Mbit/s. Historical four-switch rows use a space separator in
timestamps; new rows use ISO `T` (both parsed with `format="mixed"`).

Per candidate directory the builder also writes `experiment_manifest.csv`
(IDs, topology size, fault link, phase events, row and timestamp counts,
median sampling interval, fault-window snapshot count, iperf sender seconds
and Mbps, loss, RX-all-zero flag), `link_port_mapping.csv` (canonical
candidate endpoints), `exclusion_report.csv`, `provenance.json` (hashes of
every raw file of every admitted run, topology, labels, counts).

### 5.3 Admission criteria (new topologies) **[source: `validate_topology_run`]**

A run is admitted only if all of the following hold: all six raw files exist;
metadata status is `COMPLETE`; directory name matches metadata IDs; the ID
pair is in the registry and the fault link equals the registry's; the
`topology_spec` equals `LinearTopology(N)`; the traffic profile's bottleneck
is the topology's and the offered rate is 6.0; telemetry schema is exact,
non-empty, row count equals metadata, every row's physical ID matches, every
switch is a topology switch, port and interface present, timestamps parse,
numeric fields finite and non-negative with integral counters, no duplicate
(timestamp, switch, port); all N switches appear; runtime mapping schema
exact, no duplicates, equal to the metadata copy, equal to the telemetry's
port/interface set; every candidate link has exactly two reciprocal endpoint
rows; the fault target mapping equals the metadata copy; three ordered phase
events inside the telemetry span, consistent IDs, fault row is
`link_failure` on the fault link; iperf client and server records exited
with code 0, valid PIDs and timings; reparsed iperf logs satisfy
`validate_iperf_completion` (sender 60 ± 2 s, receiver reports agree within
0.25 s and on lost/total counts, positive delivered count) and
`completion_valid` is set; recorded and reparsed summaries differ only in
allowed keys; **sender rate within ±10% of 6 Mbps**.

Exclusion reasons actually recorded **[artifact: exclusion reports]**:
8 switches: 2 `FAILED_INVALID` (sender duration 76.5 s and 75.6 s), 1 under
rate (3.02 Mbps). 12 switches: 14 `FAILED_INVALID` (sender durations 73-163 s,
one iperf server timeout, one first-sample timeout), 1
`RUNNING_INVALID_UNTIL_COMPLETE` (suspended run 1208), 2 under rate (3.04 and
3.12 Mbps), 1 missing raw files (run 1214).

### 5.4 Counts and coverage **[artifact: provenance files, audit]**

| Topology | Attempts | COMPLETE | Admitted | Rows | Timestamps per run | Snapshots | Class support |
|---|---:|---:|---:|---:|---|---:|---|
| 4 (frozen v3) | - | - | 25 | 16,956 | - | 1,413 | 8 / 9 / 8 |
| 8 | 30 | 25 | 24 | 30,288 | 50-54 | 1,262 | s1-s2 3, s2-s3 4, s3-s4 3, s4-s5 4, s5-s6 4, s6-s7 4, s7-s8 2 |
| 12 | 44 | 28 | 26 | 44,712 | 45-49 | 1,242 | 2,3,2,2,2,3,3,2,3,2,2 (s1-s2 ... s11-s12) |

Fault-window snapshots (first 10 s): 9-10 (4 sw), 7-9 (8 sw), 6-8 (12 sw).

### 5.5 Features, missing and constant values, acquisition shift

- Model features use only the four rate metrics (`FEATURE_COLUMNS` /
  `METRICS`); raw cumulative counters and drops are not model inputs **[source]**.
- Per fold, a metric is "active" if it varies in the training-normal
  non-LOCAL rows; constant metrics are excluded (`fit_active_metrics`,
  `fit_feature_policy`). In all 8- and 12-switch folds all four metrics were
  active **[artifact: `fold_feature_policy.csv`]**.
- RX acquisition shift (four-switch data only): RX counters are zero in the
  17 historical experiments and nonzero in the 8 recollections **[doc:
  `docs/DATASET_CARD_BALANCED_V3.md`]**; all new runs have nonzero RX
  (`rx_counters_all_zero = False` in every manifest row) **[artifact]**.
- No missing values are permitted by the builder; the graph builder fills
  host nodes with zeros because hosts have no telemetry **[source]**.

### 5.6 Graph representation **[source: `build_graph_multi.py`, `prepare_examples`]**

One snapshot per (experiment, timestamp): `nodes = [h1, s1, ..., sN, h2]`,
`edges` = the N+1 physical links (made bidirectional in the model), node
feature vector = sum over the switch's numbered ports of the four rate
metrics (hosts: zeros), plus `phase`, `fault_type`, `fault_location` labels
carried alongside (never fed to the model). The per-experiment input is the
**sequence** of the first-10-second fault snapshots.

### 5.7 Integrity protections

- Exclusive-create writes everywhere (`open(..., "x")`, refusal of existing
  output directories).
- Hashes: every evaluation summary records the candidate SHA-256; the neural
  evaluator verifies the graph's `source_sha256` equals the candidate hash;
  `read_reference` verifies the RF/topology provenance hash; XAI verifies
  both; `test_frozen_artifacts.py` pins the four-switch files:
  `master_dataset.csv 7fbfcc51...`, v3 candidate `b63d0457...`, v3 graph
  `5d639c21...`, release `grouped_evaluation.csv b2381287...`, verified neural
  summary `cf0a6b89...` and its CSVs **[source]**.
- Raw evidence directories carry `SHA256SUMS.txt`; the builder's provenance
  stores per-file hashes of admitted runs.

---

## 6. Machine learning models

Common to all: input = fault-window telemetry of one experiment; output = a
score per candidate link; ranking = scores descending with lexical tie-break
on the link name (`stable_rf_ranking`, `score_ranking`) **[source]**.
"Ranking score" means: a number used only to order candidates. RF's is a
vote fraction, the neural models' a softmax output, the ranker's a rank
utility; none is calibrated (a score of 0.7 does not mean a 70% chance).

### 6.1 Random Forest **[source: `evaluate_topology_loeo.py`]**

- Preprocessing per fold: training-normal rows (non-LOCAL ports) are
  averaged per (experiment, timestamp, switch) to a switch-level frame; per
  switch, mean and std of each active metric over training-normal rows
  (`fit_switch_baseline`, std floored at 1e-4).
- Features per experiment (`make_rf_vector`): for each switch, over the first
  10 s of its fault rows, `z = |x - mean| / std` averaged over active
  metrics -> `score` per sample; then 4 statistics: `mean_anomaly`,
  `max_anomaly`, `persistence` (fraction of samples with score > 1.0),
  `first_anomaly_seconds` (time of first score > 1.0, else 999). Vector width
  = 4 x N (16, 32, 48).
- Model: `RandomForestClassifier(n_estimators=300, max_depth=5,
  random_state=42, class_weight="balanced")`; label = fault link name.
- Scores: `predict_proba`; classes absent from the training fold are appended
  with score 0 (so the ranking always covers all N-1 candidates).
- Strengths: simple, fast, robust on 4 and 8 switches (20/25, 20/24 Top-1).
  Weaknesses: switch-level features lose port direction; on 12 switches the
  per-class training support is 1-2 experiments, so recall per link swings
  (0/2 on `s2-s3` and `s4-s5`) **[artifact]**; errors are adjacent links.

### 6.2 Topology ranker **[source: `rank_topology`]**

- Per fold: per (switch, port) baselines on training-normal rows; per-row
  anomaly score = mean over active metrics of `min(|z|, 10)`; threshold =
  95th percentile of the training-normal anomaly scores.
- Per candidate link (endpoints from the runtime mapping): `link_anomaly` =
  min of the two endpoint mean anomalies in the window; `endpoint_imbalance`
  = |difference|; `pair_onset_seconds` = time when both endpoints first exceed
  the threshold (999 if never); `remote_onset_seconds` = earliest threshold
  crossing on any other switch (11 if none); `propagation_margin_seconds` =
  remote onset minus pair onset (-10 if pair never crosses).
- Score: each component is rank-transformed to a utility `(K+1-rank)/K`
  (anomaly and margin descending, imbalance and onset ascending), and the
  four utilities are averaged with equal weight; ties break by
  `link_anomaly`, then `endpoint_mean_anomaly`, then insertion order.
- No learning, no labels. Strength: fully transparent. Failure mode (measured,
  see 9.3): on long chains all downstream links share the anomaly, the
  threshold is never crossed, and the imbalance term penalizes the true link.

### 6.3 Shared neural preprocessing **[source: `graph_temporal_topology.py`]**

- Examples: the first-10-second fault snapshots per experiment (6-10 graphs).
- Feature policy per fold: concatenate all training experiments' switch-node
  rows; active features are those with std > 1e-12; means/stds over them.
- Normalization: switch rows become `(x - mean)/std`; host rows stay 0.
- Edge index: both directions of every physical edge.
- Training: per fold and seed, `random.seed/np.random.seed/torch.manual_seed`,
  `torch.use_deterministic_algorithms(True)`, one thread; Adam lr 0.01,
  weight decay 1e-3; cross-entropy; 100 epochs; **one optimizer step per
  training experiment** (batch size 1) in a shuffled order each epoch.
- Inference: softmax over the K logits; three seeds (17, 42, 2026) are
  averaged into a mean-score ensemble that defines the reported ranking.

### 6.4 GCN (`GraphOnly`)

- `GraphEncoder`: `GCNConv(F_active -> 16)` -> ReLU -> `GCNConv(16 -> 12)` ->
  ReLU; output flattened to `(N+2) x 12`.
- Each snapshot is encoded; embeddings are **averaged over time**; a linear
  head `Linear((N+2)*12, K)` gives the logits. Parameter counts depend on N.
- Strength: best measured Top-1 on 8 and 12 switches (23/24, 25/26);
  weakness: time ordering is discarded (mean over snapshots).

### 6.5 LSTM (`TemporalOnly`)

- Each snapshot's node matrix is flattened to `(N+2) x F_active`; the
  sequence goes through `nn.LSTM(input=(N+2)*F, hidden=24, batch_first)`;
  the last output -> `Linear(24, K)`.
- Uses no graph structure at all (edges ignored). Strength: captures order;
  weakness: input width grows with N, few training sequences.

### 6.6 GCN+LSTM (`GraphTemporal`)

- `GraphEncoder` per snapshot -> sequence of `(N+2)*12` vectors -> `nn.LSTM(
  (N+2)*12, 24)` -> last output -> `Linear(24, K)`.
- Best on 4 switches (23/25), not on 8 or 12; on 12 switches its per-seed
  Top-1 is 13/13/17 while the ensemble reaches 20 **[artifact]**, i.e. the
  individual fits are unstable at this sample size.

### 6.7 Concepts for oral explanation

- *Graph node*: a device; *edge*: a physical link; *adjacency*: which devices
  are directly connected (a chain). *Node features*: that switch's summed port
  rates at one timestamp. *Graph sequence*: the same graph at consecutive
  timestamps during the first 10 s of the fault. *Candidate link*: an
  inter-switch link that could be the failed one; *class index*: its position
  along the chain.
- Example: 8 switches, fault on `s4-s5`. Snapshots show s1-s4 still carrying
  ~300 packets/s while s5-s8 drop to ~0. A GCN mixes each switch's features
  with its neighbours', so the boundary between "busy" and "dead" becomes a
  local pattern; the LSTM sees that this pattern persists over the window.
  The ranking `s4-s5 (0.996) > s5-s6 (0.002) > ...` **[artifact: experiment
  104 report]** says "s4-s5 first", not "99.6% probability".

### 6.8 What cannot be established from source

The neural architectures were designed in the four-switch study; no
hyperparameter search is recorded in the repository, so why hidden sizes
16/12/24, lr 0.01, or 100 epochs were chosen is undocumented. The Ryu
controller's source lives only on the VM. Timing of model fits is only
partially measured (wall clocks were inflated by host sleeps).

---

## 7. Evaluation methodology

### 7.1 LOEO step by step **[source: `ordered_grouped_splits`, `evaluate`]**

1. Sort the admitted experiment IDs.
2. For each ID `e`: training set = all other IDs; held-out set = `{e}`.
3. Fit everything that learns from data on the training set only: active
   metric selection, switch/port baselines, the ranker threshold, RF, the
   neural feature policy (means/stds), the neural weights.
4. Build the held-out experiment's features with the training-fitted
   statistics, rank the K candidates, join the true label **after** ranking.
5. Repeat for every experiment; aggregate experiment-level outcomes.

Why not random rows: each experiment contributes ~1,200-1,700 highly
correlated rows from one fault; a random row split would put rows of the same
fault in both train and test, letting a model memorize the experiment rather
than learn the fault pattern. Grouping by `experiment_id` keeps the whole
experiment on one side.

Concrete fold (8 switches): held-out 104 (`s4-s5`), training IDs
101-103, 105, 106, 108-121, 123, 125-127 (23 experiments; 107, 122, and 124
are not admitted; `train_experiment_ids` column) **[artifact:
`grouped_evaluation.csv`]**.

### 7.2 Metrics **[source: `summarize`]**

- Top-k: fraction of experiments whose true link is within the first k
  ranked candidates. Top-3 is uninformative on 4 switches (K = 3).
- MRR: mean of `1/rank_of_true_link`.
- Wilson 95% intervals on Top-k use the experiment count as n.
- Chance: uniform random ranking gives Top-1 = 1/K (0.333, 0.143, 0.091),
  MRR = H_K/K (0.611, 0.370, 0.275).
- Paired comparisons (`audit_topology_results.sign_test_p`): for two models,
  count experiments where A is right and B wrong and vice versa; exact
  two-sided binomial sign test on the discordant pairs, uncorrected for the
  ten pairs per topology.

### 7.3 Seeds and ensembles

Three seeds are three fits of the same model on the same fold; they are not
new experiments. The reported neural ranking is from the mean of the three
softmax vectors. Per-seed metrics are also stored (`seed_metrics`).

### 7.4 Unseen fault links

If a held-out experiment's link has no training experiment with the same
label, a classifier cannot predict it. On the interim 12-switch set (9
experiments) 7 of 9 held-out links were unseen and every supervised model
scored 0; the final 26-experiment set has 0 unseen (every link has 2-3
experiments) **[artifact: audit]**. This is why the final collection had to
reach at least two experiments per link.

### 7.5 The independent audit **[source: `audit_topology_results.py`]**

Per topology it recomputes from `candidate_dataset.csv`, `grouped_evaluation.csv`,
`per_seed_predictions.csv`, `mean_seed_ensemble_predictions.csv`, and the XAI
reports: one label per experiment and labels are candidates; K = N-1; each
experiment held out once per method; held-out ID absent from every training
list; training size n-1; rankings are permutations of the candidates; rank
columns consistent with rankings and labels; Top-1/Top-2/MRR and denominators
equal the summaries; chance 1/K reported; ensemble scores equal the per-seed
means; neural summary's reference equals the RF/topology summary; feature
policy per fold excludes the held-out ID; XAI rankings, truth, Top-1 status,
endpoint mappings, SHAP additivity and IG completeness identities, and
summary pass counts agree with the per-report values. Result: 49/49 checks on
each of the three topologies, exit 0 **[artifact: `results/audit/`]**.

---

## 8. Explainable AI

### 8.1 Why

Accuracy says how often the top link is right; it says nothing about *what in
the telemetry* drove a ranking, whether the model used the expected switches,
or whether an explanation is even faithful to the model. The XAI layer exists
to make each ranking inspectable and to test the explanations themselves.

### 8.2 RF: SHAP **[source: `explain_rf_fold`]**

The fold is rebuilt with `fold_inputs` and `fit_rf` (same seed, same data);
the refit ranking is asserted equal to the saved one. `shap.TreeExplainer(model)`
gives exact Shapley values per feature and class for the held-out feature
vector. Validation: additivity, `base_value + sum(SHAP) == predict_proba`
(max error ~1e-16); deletion, neutralizing the top-3 positive-SHAP features
(set to the training mean) must lower the predicted-class score at least as
much as 3 random features (20 draws). Report lists top features with their
switch, the per-switch support, and the predicted and true links' endpoints.

### 8.3 Neural: integrated gradients and occlusion **[source: `explain_neural_fold`]**

The three seed checkpoints of the fold are loaded; their feature policy is
asserted equal to the recomputed fold policy; the recomputed ensemble scores
are asserted equal to the saved ones. The explained function is the ensemble
`mean_s softmax(model_s(sequence))` for the predicted class. Integrated
gradients with a zero baseline in normalized space (= training-mean
fault-window telemetry), 512 Riemann steps (64 left completeness gaps up to
0.59; 512 brings the worst to under 10%). Attributions are summed per switch,
per feature, per timestep. Occlusion: zero a switch's features in all
snapshots (all models), remove an edge in both directions (GCN models only),
drop a timestep. Validation: completeness
`sum(IG) == f(x) - f(baseline)` within 5% relative or 1e-3 absolute; deletion,
zeroing the top-2 positive-IG switches must lower the score at least as much as
2 random switches (20 draws).

### 8.4 Topology ranker: component exposure **[source: `explain_topology_fold`]**

The four component values, their utilities, and the aggregate are shown for
every candidate; `rank_score` is recomputed as the mean of utilities;
leave-one-component-out recomputes the ranking without each component and
reports whether the top-1 changes and where the true link lands. This is
transparency of a fixed formula, not attribution of a learned model.

### 8.5 Validation outcomes **[artifact: `xai_summary.json`, audit]**

| Model | 4 sw (n=25) | 8 sw (n=24) | 12 sw (n=26) | Failing check |
|---|---|---|---|---|
| RF | 25/25 | 23/24 (exp. 112) | 26/26 | deletion |
| Topology ranker | 25/25 | 24/24 | 26/26 | - |
| GCN | 24/25 (10) | 22/24 (112, 119) | 24/26 (205, 238) | deletion |
| LSTM | 23/25 (11, 18) | 23/24 (126) | 25/26 (239) | deletion |
| GCN+LSTM | 22/25 (3, 7, 17) | 23/24 (113) | 25/26 (231) | deletion |

All additivity and completeness identities pass. Failures are retained in
the per-experiment JSON and listed in `xai_summary.json`.

### 8.6 A real example (8 switches, experiment 104, truth `s4-s5`) **[artifact: `results/xai/topology_8_switches/experiments/experiment_104.md`]**

- RF: ranking `s4-s5 (0.737) > s3-s4 (0.145) > s6-s7 (0.050) > ...`, Top-1
  correct. Main support: `s4_max_anomaly` (SHAP +0.055, value 1.44),
  `s4_mean_anomaly` (+0.050, 1.19), `s3_first_anomaly_seconds` (+0.041, 999).
  Relevant ports: s4 port 2, s5 port 1. Additivity 3.3e-16; deletion drop
  0.076 vs random 0.059: pass.
- Topology ranker: `s7-s8 (0.679) > s2-s3 (0.607) > s4-s5 (0.571) ...`,
  truth ranked 3. Winner's components: link_anomaly 1.057 (utility 0.57),
  imbalance 0.004 (utility 1.00), pair onset 999, margin -10; deciding
  component: `endpoint_imbalance`.
- GCN: `s4-s5 (0.996)`, correct; top attributions s6 rx_throughput (+0.125),
  s6 rx_packet_rate (+0.122), s5 rx_throughput (+0.102); completeness gap
  5.1e-4; zeroing s6 and s5 drops the score by 0.928 vs 0.184 random: pass.
- LSTM: `s4-s5 (0.995)`, correct; top attributions on s5 and s4.
- GCN+LSTM: `s4-s5 (0.717)`, correct; top attributions on s2 and s3 (upstream
  side), deletion 0.455 vs 0.125: pass.

Read honestly: the models agree on the link, but their "evidence" sits on
different switches (downstream s5/s6 for GCN and LSTM, upstream s2/s3 for
GCN+LSTM). Attribution tells you what moved the score, not what caused the
outage.

### 8.7 Why attribution is not causal proof, and scores are not probabilities

The fault window is chosen with the true phase (oracle); every switch past
the fault stops carrying traffic, so many features are informative and the
attribution spreads along the chain (the top-2 |IG| switches equal the true
endpoints in only 12-38% of cases **[artifact]**). Deletion checks test
whether the attributed inputs matter *to the model*, not whether the link
caused the symptoms. Softmax outputs from 100-epoch, batch-size-1 training on
~25 examples are not calibrated; RF vote fractions are not calibrated either;
no calibration study exists in the repository.

### 8.8 GNNExplainer

PyTorch Geometric's `Explainer`/`GNNExplainer` expects a model with
`forward(x, edge_index, ...)` on one graph. The implemented models consume a
**sequence** of graphs (a Python list of `{x, edge_index}`) and the LSTM
variants depend on their order; wrapping them for a single graph (for
example a time average) would explain a different function. The decision to
use integrated gradients and occlusion on the real input is technically
justified by that architecture **[interpretation of source]**; a
sequence-aware GNNExplainer could be built but was not.

---

## 9. Verified experimental results

### 9.1 Final metrics (experiment-level grouped LOEO; recomputed by the audit) **[artifact]**

| Model | 4 switches (n=25, K=3) | 8 switches (n=24, K=7) | 12 switches (n=26, K=11) |
|---|---|---|---|
| Random Forest | 20/25, 22/25, 0.880 | 20/24, 23/24, 0.910 | 19/26, 21/26, 0.824 |
| Topology ranker | 13/25, 22/25, 0.740 | 1/24, 11/24, 0.412 | 1/26, 2/26, 0.200 |
| GCN | 20/25, 23/25, 0.887 | 23/24, 23/24, 0.972 | 25/26, 26/26, 0.981 |
| LSTM | 18/25, 21/25, 0.833 | 22/24, 23/24, 0.951 | 22/26, 23/26, 0.896 |
| GCN+LSTM | 23/25, 23/25, 0.947 | 22/24, 22/24, 0.933 | 20/26, 23/26, 0.849 |

(Top-1, Top-2, MRR.) Chance Top-1 0.333 / 0.143 / 0.091; chance MRR 0.611 /
0.370 / 0.275. Wilson 95% intervals for Top-1 are in
`results/comparison_4_8_12/comparison_table.md`; for example GCN on 12
switches [81.1%, 99.3%], RF on 12 switches [53.9%, 86.3%].

### 9.2 Paired comparisons **[artifact: `results/audit/methodology_audit.md`]**

- Ranker vs every learned model: p < 0.001 on 8 and 12 switches; p = 0.039
  (RF) to 0.002 (GCN+LSTM) on 4 switches.
- Among learned models the only pair under 0.05 is RF vs GCN on 12 switches
  (0 vs 6 discordant, p = 0.031, uncorrected; on 4 switches it is 3 vs 3).
  GCN vs GCN+LSTM on 12 switches: 5 vs 0, p = 0.062. Everything else p >= 0.25.
- Conclusion the evidence supports: learned models >> heuristic; learned
  models not separable from each other.

### 9.3 Strong and weak results explained

- **Learned models above chance everywhere**, with Top-1 at 73-96% against
  9-33% chance.
- **Ranker collapse on 8 and 12 switches** (`results/audit/topology_ranker_8sw_investigation.md`):
  thresholds 2.56-2.58 are never crossed because fault-window per-port
  anomaly is only ~1.1-1.2 (normal-phase std is as large as the mean, since
  the normal baseline includes the zero-rate first sample and ramp-up);
  therefore onset and margin are constants; the true link is top by
  `link_anomaly` alone in 17/24 experiments but has a larger endpoint
  imbalance than fully dead downstream links, so the imbalance utility cancels
  it; 7-way ties occurred in 8 experiments. Port mapping, candidate
  generation, window, and tie-breaking were verified correct. Not modified
  (changing it to "most upstream anomalous link" would be tuning to the test
  outcomes).
- **12 switches**: legitimate but small (2-3 per link). RF misses both
  `s2-s3` and both `s4-s5` experiments; GCN+LSTM seeds vary 13-17/26.
- **8-switch set has 24, not 25**: the registry's 30 IDs were exhausted (3 of
  the last attempts failed after the VM suspend).

### 9.4 Discrepancies and stale statements found

1. `README.md` and `docs/END_TO_END_RUNBOOK.md` state that "no further
   physical run is authorized" and that all registered IDs are consumed. That
   was true for the **four-switch** registry on 2026-10-19; the 8- and
   12-switch collections were later authorized by the user and use separate
   registries. The README's new section points to the topology-scaling docs
   but the older sentences were left as written **[doc inconsistency]**.
2. `project_inventory.json` has `"inventory_date": "2026-10-19"` at the top
   while its `topology_scaling_20261024` section was updated through
   2026-10-25 **[stale header]**.
3. The four-switch "median sampling interval ~1.08 s" in
   `docs/RESULTS_TOPOLOGY_SCALING.md` is taken from an `EXECUTION_LOG.md`
   statistic (1.075 s median of within-phase non-fault intervals) computed
   differently from the 8/12-switch manifest medians (all adjacent timestamps);
   the numbers are comparable only approximately **[methodological note]**.
4. Wall-clock runtimes for the 8-switch neural LOEO (49,383 s), the final
   12-switch neural LOEO (68,349 s), and the 8-switch XAI (18,675 s) include
   host sleeps; they are not compute estimates (documented as such).
5. `EXECUTION_LOG.md` entries from 2026-10-18/19 report 80 and 82 tests; the
   current suite has 115. These are consistent over time (new tests were
   added), not contradictory.
6. The runbook's VM-reboot recipe says `sudo reboot`; the actual recovery
   needed `reboot -f` (now recorded in the runbook) **[doc updated]**.
7. Early batch attempts counted runs as valid before the offered-rate rule
   existed (e.g. the 8-switch batch printed `valid=25` while the builder admits
   24). The `batch_log.jsonl` status field is the raw runner status; the
   authoritative admission is the candidate's `provenance.json` /
   `exclusion_report.csv` **[accounting note]**.

No contradiction was found between per-experiment rows, summary JSON,
comparison table, plot data, and the audit (all recomputed, 49/49 x 3).

### 9.5 Final verification **[artifact: `EXECUTION_LOG.md`, this session]**

`.\venv\Scripts\python.exe -m unittest discover` -> 115 tests OK;
`py_compile` of all new/modified modules -> exit 0; `pip check` -> clean;
`git diff --check` -> exit 0; `audit_topology_results.py` -> exit 0;
`test_frozen_artifacts.py` -> frozen four-switch hashes unchanged. Backups
verified by SHA-256 (0 mismatches). Nothing committed.

---

## 10. Reproducibility and operations

### 10.1 Environments

- Windows: `py -3.13 -m venv venv`; `.\venv\Scripts\python.exe -m pip install
  --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-windows.txt`
  **[doc: END_TO_END_RUNBOOK; the current venv was verified with `pip check`]**.
- VM: Ubuntu 20.04.1, Python 3.8.5, Mininet, OVS 2.13.1, Ryu
  (`/home/mininet/.local/bin/ryu-manager`), iperf2 2.0.13; SSH
  `mininet@127.0.0.1:2222` with key `~/.ssh/mininet_vm_ed25519`
  (`-o IdentitiesOnly=yes`); `sudo -n` works; the OVS DB socket is root-only.
- Staging directory for this work: `/home/mininet/sdn_project/topology_scaling_20261023/`
  (runner, collector, topology module, batch, cleanup tool, tests, profiles).

### 10.2 Safe order of operations

1. Read-only VM check: `ss -lnt | grep -E '6633|6653'`, `sudo -n ovs-vsctl list-br`
   (must be empty), `ps -eo pid,args | grep -E '[m]n |[i]perf'` (none),
   `sudo -n dmesg | grep -ciE 'soft lockup|rcu_sched'` (0 since boot).
2. If Ryu is not listening: `cd /home/mininet/sdn_project && nohup
   /home/mininet/.local/bin/ryu-manager controller.py > ryu_<date>.log 2>&1 &`.
3. Host: on mains, keep-awake active, no heavy Windows jobs, VS Code
   remote session to the VM closed.
4. `sudo -n python3 -B experiment_runner_recollection.py --switches N --verify-topology`
   (expect N-1 links, 0% loss, empty bridges after).
5. Batch: `sudo -n nohup python3 -B run_topology_batch.py --switches N
   --target-valid 25 >> batch_N.log 2>&1 < /dev/null &`; monitor
   `batch_N.log` and `recollection_runs/topology_N_switches/batch_log.jsonl`.
6. Export: `sudo -n tar czf /tmp/export.tgz -C <stage>/recollection_runs topology_N_switches`,
   `chown mininet`, `scp`, extract into `raw_evidence/`, write `SHA256SUMS.txt`
   (Git Bash: `tar --force-local`).
7. Windows pipeline (section 3.3) into **new** output directories.
8. `audit_topology_results.py`, `build_topology_comparison.py`, tests.

### 10.3 Interpreting logs and failures

- `batch_N.log`: `start/done` lines with status, return code, elapsed, and a
  running `valid=` count; `STOP: 3 consecutive failures` or `STOP: environment
  not clean`.
- `run_metadata.json` `status`: `COMPLETE`, `FAILED_INVALID` (with `failure`
  text, e.g. `iperf sender duration 76.5s is outside requested 60s ± 2s`,
  `iperf sender achieved 3.02 Mbps ...`), or `RUNNING_INVALID_UNTIL_COMPLETE`
  (interrupted).
- Resume: rerun the same batch command; existing run directories are
  skipped; never delete or rename a run directory to reuse its ID.
- Stale bridges after an interrupted run: `cleanup_abandoned_run.py --run-dir
  <dir>` (dry run) then `--apply`; never `mn -c` (it kills Ryu).
- Wedged guest (SSH logins take minutes, `timedatectl` times out, kernel
  lockups in `dmesg`): `sudo -n sync; sudo -n reboot -f`, then restart Ryu.

### 10.4 Operations that disrupt shared infrastructure

Rebooting the VM, `mn -c`, killing `ryu-manager`, starting a second
controller on 6633, running two batches at once, or running heavy Windows
compute during collection.

### 10.5 Reproducing final results without touching frozen artifacts

All evaluators refuse existing output paths; pass fresh `--output-dir`
values. The frozen four-switch files are only read. `test_frozen_artifacts.py`
confirms their hashes afterwards.

### 10.6 Executed versus documented-only commands

Executed and verified in this project: every command in section 3.3 marked
"executed", the VM checks and batch commands above, the backup procedure
(`robocopy` + `Get-FileHash`). Documented but **not** executed here: fresh
venv creation on a new machine, the legacy `experiment_runner.py`, the
four-switch `build_validated_candidate.py` rebuild and `demo_rca_v3.py`
(documented in `README.md` and `docs/END_TO_END_RUNBOOK.md` as previously
verified on 2026-10-19).

---

## 11. Testing and software quality

### 11.1 Inventory (115 tests, all passing on the final tree) **[source + artifact]**

| File | Tests | What it validates |
|---|---:|---|
| `test_recollection_runner.py` | 42 | Runner guards: ID registry, isolated output paths, first-sample-before-normal rule, phase coverage and ordering, runtime mapping from observed ports, target mapping reciprocity, mocked end-to-end orchestration producing all artifacts, iperf process/summary validation incl. receiver-shorter-than-sender, offered-rate rule, cleanup failures cannot yield COMPLETE, traffic-profile margin. |
| `test_linear_topology.py` | 13 | Switch/host/link counts for 4/8/12 (3, 7, 11 candidates), four-switch equality with the original study, middle bottleneck, metadata round trip, link helpers, balanced schedules, registries (30 and 60 slots, disjoint from four-switch IDs), runner directories, per-topology profiles, target resolution for any candidate on 12 switches, preflight topology report, numeric link naming, graph builder with 8 switches. |
| `test_telemetry_pipeline.py` | 9 | Port/interface parser, collector schema and overwrite refusal, legacy merge rules. |
| `test_dataset_builder.py` | 8 | Four-switch builder: approved ID pairs, run-23 integrity, output isolation, mapping mismatch rejection, run-21 re-audit rule. |
| `test_evaluate_topology_loeo.py` | 6 | Static 4-switch mapping equals the historical one; runtime mapping ordering; `summarize` for 7 candidates (counts, MRR, chance, confusion, adjacent errors); grouped splits never leak; synthetic 8-switch evaluation ranks all 7 candidates with 9-experiment training folds; **frozen regression**: reproduces the v3 release rankings and counts. |
| `test_graph_temporal_grouped_loeo.py` | 5 | Original four-switch neural LOEO helpers (splits, feature policy, metrics, writers, reference checks). |
| `test_graph_temporal_link_rca.py` | 4 | Labels not in tensors, first-10-second window, deterministic tie-break, Wilson intervals. |
| `test_explain_rca.py` | 4 | IG completeness on random models for all three architectures, occlusion coverage of all switches/edges/timesteps, model shapes follow N, end-to-end RF/ranker explanation schema and identity checks with overwrite refusal. |
| `test_online_fault_detection.py` | 4 | Causality of the (negative-result) detector. |
| `test_frozen_artifacts.py` | 3 | Pinned hashes of the frozen datasets/results, published four-switch metrics, new registries do not collide with frozen paths. |
| `test_topology_candidate_builder.py` | 3 | Builds from valid synthetic runs (schema, labels, manifest, mapping, provenance); excludes eight kinds of invalid runs with reasons incl. under-rate; rejects duplicate identity and inconsistent mapping. |
| `test_audit_topology_results.py` | 3 | Exact sign test; audit passes on the 8-switch artifacts; audit detects a tampered leaky split. |
| `test_graph_builder.py` | 3 | Port-sum aggregation, LOCAL exclusion, label consistency, overwrite refusal. |
| `test_demo_rca_v3.py` | 3, `test_demo_rca.py` 2 | Saved replay and fresh inference demos, hash checks. |
| `test_evaluate_grouped_rca_generalized.py`, `test_experiment_admission_ledger.py`, `test_audit_traffic_profile_pilot.py` | 1 each | Four-switch evaluator loading/splitting; ledger status separation; pilot audit without admission. |

### 11.2 Unit tests versus integration

Unit tests mock Mininet, OVS, and iperf (`FakeNetwork`, `FakeIperfProcess`,
`FakeCollector`); they cannot prove the live path works. Live confidence comes
from `--verify-topology` runs, the 24 + 26 admitted real runs, and the 4-switch
regression that reproduced frozen results byte-for-byte in rankings.

### 11.3 Known limitations and technical debt

- Controller source is outside the repository.
- Collector rate uses the nominal 1 s interval, not the measured one.
- `run_topology_batch.py` has no per-link targeting; balance relies on the
  round-robin registry (an extension was needed for `s11-s12`).
- Neural training is batch-size-1 and seeds show instability on 12 switches.
- No calibration, no online detection, no causal analysis.
- 8-switch set is 24/25; 12-switch per-link support is 2-3.
- Several documents retain four-switch-era statements (section 9.4).

---

## 12. Viva preparation

### 12.1 Two-minute explanation

"My project localizes a failed link in a software-defined network from
switch port counters. I emulate linear topologies of 4, 8, and 12 switches in
Mininet with Open vSwitch and a Ryu controller, send a 6 Mbps UDP flow from one
end host to the other, and after 20 seconds I take one inter-switch link down
for 20 seconds. A collector samples every switch port about once a second. For
each experiment, given the first ten seconds of the fault, five methods rank
the N-1 candidate links: a Random Forest on per-switch anomaly statistics, a
hand-built topology heuristic, a graph convolutional network, an LSTM over
the telemetry sequence, and a GCN followed by an LSTM. I evaluate with
leave-one-experiment-out so no telemetry from the tested experiment is ever
used to fit anything. Across 25, 24, and 26 experiments the learned models
place the true link first in 73 to 96 percent of experiments, against chance
levels of 33, 14, and 9 percent; the heuristic works only on 4 switches. I
added an explainability layer with SHAP, integrated gradients, and occlusion,
validated by additivity, completeness, and deletion checks, and an audit
script that recomputes every number from the per-experiment outputs. The
limits: the fault window is known, the samples are small, the scores are
rankings not probabilities, and no model is statistically better than the
other learned models."

### 12.2 Five-minute technical walkthrough

1. Topology and traffic (section 4.1, 4.4): chain, bottleneck in the middle,
   iperf 6 Mbps, 20/20/20 s phases.
2. Runner (2.3): preflight, runtime port mapping from OVS, collector, fault via
   `ip link set down` on both ends, validation, cleanup; fail-closed batch.
3. Admission (5.3): why 18 of 44 twelve-switch runs were rejected; the
   offered-rate rule added after half-rate runs slipped through.
4. Data to features (5.6, 6.1, 6.3): rows -> switch sums -> graph snapshots;
   RF statistics; per-fold normalization.
5. Models (6): RF 300 trees; ranker's four components; GCN 2 layers 16/12,
   mean over time; LSTM hidden 24; GCN+LSTM; 3 seeds averaged.
6. LOEO and metrics (7): grouped folds; Top-1/Top-2/MRR; chance 1/K; paired
   sign tests.
7. Results (9.1-9.3) and the ranker failure mechanism.
8. XAI (8) with the experiment-104 example.
9. Audit, tests, frozen hashes, backups (7.5, 9.5, 11).

### 12.3 Demo script (offline, no VM needed)

1. Show `results/comparison_4_8_12/comparison.png` and `comparison_table.md`.
2. Open `results/topology_12_switches/candidate/experiment_manifest.csv`: 26
   rows, every link 2-3 times, sender 6.29 Mbps everywhere.
3. Open `results/topology_12_switches/loeo_rf_topology/grouped_evaluation.csv`
   and point at one row: `train_experiment_ids` excludes `experiment_id`;
   `ranking_json` has 11 links.
4. Run `.\venv\Scripts\python.exe audit_topology_results.py` live (seconds):
   49/49 checks per topology.
5. Open `results/xai/topology_8_switches/experiments/experiment_104.md` and
   read the RF and GCN sections.
6. Run `.\venv\Scripts\python.exe -m unittest test_frozen_artifacts test_linear_topology -v`.
7. Optional (VM available): `sudo -n python3 -B experiment_runner_recollection.py
   --switches 8 --verify-topology` to show 7 links and 0% ping loss without
   injecting any fault.

### 12.4 Likely viva questions and answers

**Architecture and SDN**

1. *What does the controller do during a fault?* Nothing special: Ryu's
   learning switch installs flows on packet-in and floods unknowns; it has no
   link-down handling. The flows keep pointing into the dead link, so traffic
   past the fault stops. That is the observable symptom.
2. *Why a linear topology?* It makes "N-1 candidate links" exact and lets the
   number of candidates scale cleanly; the trade-off is that a fault has a
   simple downstream signature. Meshes and reroutes are future work.
3. *Why Mininet and not real hardware?* Reproducible, scriptable, and it
   exposes real OVS counters; the price is a single-vCPU VM whose timing can
   be disturbed (host suspends caused kernel lockups).
4. *How are OpenFlow ports mapped to links?* Read at runtime from
   `ovs-ofctl show` and cross-checked against Mininet's link list; stored per
   run; the builder refuses to merge runs whose mapping differs.
5. *What exactly is injected?* `ip link set dev <intf> down` on both
   interfaces of the chosen inter-switch link for 20 s, then `up`.

**Telemetry and data**

6. *What is a telemetry row?* One switch port at one timestamp: cumulative
   RX/TX packets, bytes, drops, and per-second rate deltas.
7. *Why do rates look inflated on 12 switches?* The collector divides deltas
   by a nominal 1 s while the real interval is ~1.35 s. Normalization is per
   topology, so comparisons within a topology are fair; absolute rates are not
   comparable across topologies.
8. *What is the RX acquisition shift?* In the four-switch data the 17
   historical runs have all-zero RX counters and the 8 recollections do not.
   New runs all have nonzero RX. Feature policy is fit per training fold, so
   constant features are dropped where they occur.
9. *How many experiments do you have?* 25, 24, 26 admitted; 30 and 44
   attempts for the new topologies; 6 and 18 rejections with recorded reasons.
10. *Why was a run rejected for sending at 3 Mbps?* The profile is 6 Mbps; a
    half-rate client did not execute the protocol; such runs were found after a
    VM suspend and a rule (±10%) was added to the runner, batch, and builder.

**Models**

11. *What does the RF see?* 4 statistics per switch of the mean absolute
    z-score over the first 10 fault seconds; width 4N; 300 trees, depth 5,
    balanced class weights, seed 42.
12. *Why does the topology ranker fail on 8 switches?* Its threshold is never
    crossed, so two components are constants; all downstream links share the
    anomaly; the true link's larger endpoint imbalance is penalized; ties
    decide. Verified by inspecting components; not tuned.
13. *What is a GCN doing here?* Two graph convolutions mix each switch's
    features with its neighbours'; the chain adjacency lets the "busy/dead"
    boundary become a local pattern; embeddings are averaged over time and a
    linear layer scores the N-1 links.
14. *What does the LSTM add?* Order over the 6-10 snapshots; it ignores edges.
15. *Why is GCN+LSTM not the best on 8 and 12 switches?* Its seeds are
    unstable (13-17 of 26 on 12 switches); with ~25 training sequences the
    larger model is harder to fit. Differences to GCN are not significant.
16. *Is the softmax a probability?* No. It is an uncalibrated score from a
    tiny training set; I only use its order.
17. *How are the three seeds used?* Their softmax vectors are averaged; the
    average defines the ranking; per-seed metrics are stored too.

**Evaluation**

18. *What is LOEO and why grouped?* Hold out one whole experiment, fit
    everything on the others. Rows of one experiment are correlated; random row
    splits would leak the fault into training.
19. *What is fitted inside the fold?* Active metrics, switch and port
    baselines, the ranker threshold, RF, neural normalization and weights.
20. *What is MRR?* Mean of 1/rank of the true link; 1.0 means always first;
    random is 0.611/0.370/0.275 for 3/7/11 candidates.
21. *Why report chance levels?* Because Top-1 percentages fall with more
    candidates; 73% on 11 candidates is further above chance than 80% on 3.
22. *Is GCN better than RF?* Not demonstrably. The paired sign test gives
    p = 0.031 on 12 switches (0 vs 6 discordant) but 3 vs 3 on 4 switches and
    0 vs 3 (p = 0.25) on 8; uncorrected for 10 comparisons. I report it as
    not separable.
23. *What is an unseen fault link?* A held-out link that no training
    experiment has; the classifier cannot predict it. With 9 experiments, 7 of
    9 were unseen; with 26, none are.
24. *How do you know the numbers in the report are right?* An independent
    script recomputes them from the per-experiment rows: 49 checks per
    topology, all passing.
25. *What do the Wilson intervals mean?* 95% intervals on a proportion with
    n = experiments; e.g. RF on 12 switches 73% [54%, 86%].

**XAI**

26. *Why SHAP for RF?* TreeExplainer gives exact Shapley values for tree
    ensembles cheaply, and additivity can be checked exactly.
27. *What is integrated gradients?* The integral of the gradient along a
    straight path from a baseline input to the real input; it satisfies
    completeness (attributions sum to the score difference). I use 512 steps
    because 64 left gaps up to 59%.
28. *What is your baseline and why does it matter?* All-zero normalized
    features, i.e. the training-mean fault-window state. Attributions are
    relative to that baseline; a different one changes them.
29. *What is the deletion check and what did it show?* Zero the top-2
    positive-IG switches (or neutralize the top-3 SHAP features) and compare
    the score drop to random deletions. It fails in a few cases per topology
    (e.g. GCN 2/26 on 12 switches); I report those as failures.
30. *Does an explanation prove the model found the cause?* No. It shows what
    moved the score; the whole downstream chain is informative, and
    attributions often sit on neighbouring switches.
31. *Why not GNNExplainer?* It explains one graph with `forward(x,
    edge_index)`; my models take a sequence and the LSTM variants depend on
    order. IG and occlusion work on the actual input.
32. *What does the ranker's "explanation" mean?* It is the formula's four
    components and what happens when each is removed; it is transparency, not
    attribution.

**Reproducibility and operations**

33. *How is the frozen baseline protected?* Exclusive-create writes, hash
    pins in a test, provenance hashes in every summary, and backups outside the
    repository.
34. *What went wrong operationally?* Host suspends froze the VM mid-run; the
    guest kernel logged soft lockups; iperf then under-paced or stalled. A
    forced reboot and a restarted Ryu fixed it (17/17 valid runs afterwards).
35. *Why is the 8-switch set 24 and not 25?* The 30-ID registry ran out after
    post-suspend failures; I did not reuse or extend IDs for it.
36. *Can I reproduce your numbers?* Yes, from the admitted candidates: all
    seeds are fixed, torch runs deterministically on one thread, and the
    four-switch regression reproduced the published results with zero score
    difference.
37. *How long does a run take?* About 85-100 s per live experiment; RF/ranker
    LOEO under a minute; neural LOEO tens of minutes to about an hour per
    topology on CPU (wall clocks in the log include host sleeps).

**Challenging follow-ups**

38. *Your fault window comes from the labels. Isn't that cheating?* It is the
    stated design: conditional localization. Online detection was tried and
    failed (0/25). I never present these as online results.
39. *With 2-3 experiments per link, can you claim anything about 12 switches?*
    Only that the learned models are far above chance and that the ranker is
    not; per-link recall is unreliable, intervals are wide.
40. *Why not fix the ranker since you know why it fails?* Changing it to
    "most upstream anomalous link" after seeing the test outcomes would be
    tuning on the held-out data; I documented the mechanism instead.
41. *Would results hold on a mesh with rerouting?* Unknown; the downstream
    signature is specific to a chain without reroute. That is the main
    external-validity limit.
42. *Are the three seeds independent evidence?* No; they are repeated fits on
    the same data. The independent unit is the experiment.
43. *Why does the collector's nominal interval not break the models?*
    Normalization is per topology and per fold; the inflation is a constant
    factor within a topology. It would matter if models were transferred
    across topologies, which they are not.
44. *What would you do next?* Two-experiments-per-link became possible only
    after a reboot; I would collect to 5+ per link, add normal-only controls,
    fix the collector interval, test a mesh, and study calibration.

How to answer when evidence is thin: state the measured number and its
interval, say what it does not show, and name the design limit (oracle
window, sample size, single topology family). "The data do not separate the
learned models" is a complete, defensible answer.

### 12.5 Cheat sheet

- Topologies: 4/8/12 switches -> 3/7/11 candidates; bottleneck `s2-s3`,
  `s4-s5`, `s6-s7` (10 Mbps, 5 ms). Traffic 6 Mbps UDP, phases 20/20/20 s.
- Data: 25/24/26 experiments; 16,956 / 30,288 / 44,712 rows; snapshots
  1,413 / 1,262 / 1,242; fault window = first 10 s of `phase == fault`.
- Admission: COMPLETE, schema, finite, no duplicates, mapping coverage,
  reciprocal target, ordered phases, iperf exit 0, 60 ± 2 s, receivers agree,
  rate within 10% of 6 Mbps.
- RF: 4 stats x N switches, 300 trees, depth 5, seed 42. Ranker: 4 equal
  components, q95 threshold, |z| clip 10. GCN: GCNConv F->16->12, mean over
  time, Linear((N+2)*12, K). LSTM: hidden 24 on (N+2)*F. GCN+LSTM: encoder ->
  LSTM 24. Adam 0.01, wd 1e-3, CE, 100 epochs, batch 1, seeds 17/42/2026.
- Results (Top-1 / Top-2 / MRR): see 9.1. Chance Top-1 0.333/0.143/0.091.
- Paired tests: ranker vs learned p < 0.001 (8, 12); RF vs GCN p = 0.031 on 12
  only; others p >= 0.062.
- XAI passes: RF 25/25, 23/24, 26/26; ranker all; GCN 24/25, 22/24, 24/26;
  LSTM 23/25, 23/24, 25/26; GCN+LSTM 22/25, 23/24, 25/26 (deletion failures only).
- Audit 49/49 x 3; tests 115 OK; frozen hashes unchanged; backups
  `sdn-ml_backups\20261025T005215` and `...T210707`.
- Key commands: section 3.3; VM order: section 10.2.
- Caveats: oracle window; uncalibrated scores; seeds are not experiments;
  small n; one topology family; no causal claims; 8-switch set is 24.
