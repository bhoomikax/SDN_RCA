# Review summary: SDN faulty-link localization across 4, 8, and 12 switch topologies

Prepared 2026-10-25 for project review. Every number below is recomputed by
`audit_topology_results.py` from per-experiment artifacts; nothing is taken
from a summary alone.

## 1. Problem and scope

Given an emulated linear SDN path `h1 - s1 - ... - sN - h2` (Mininet, Open
vSwitch, Ryu learning switch) and per-port telemetry, rank the N-1
inter-switch links by how likely each is the link that failed. Evaluation is
**conditional localization**: the annotated fault phase selects the first ten
seconds of each experiment. It is not online detection, not causal
root-cause analysis, and all model scores are uncalibrated ranking scores.

## 2. Architecture

- `linear_topology.py`: N-switch specification, N-1 candidate links, 10 Mbps /
  5 ms bottleneck on the middle link (`s2-s3`, `s4-s5`, `s6-s7`), fixed
  per-topology ID registries with balanced fault schedules.
- `experiment_runner_recollection.py --switches N`: builds the topology,
  records the runtime OVS port-to-link mapping, collects telemetry, drives a
  6 Mbps UDP flow with 20/20/20 s normal/fault/recovery phases, injects a
  link-down fault, validates iperf process evidence, and fails closed.
- `run_topology_batch.py`: sequential collection on the VM; stops on stale
  bridges, busy processes, or three consecutive failures.
- `build_topology_candidate.py`: admission (schema, finite values, duplicate
  keys, mapping coverage, reciprocal target mapping, phase coverage, iperf
  duration 60 ± 2 s, receiver agreement, sender rate within ±10% of 6 Mbps).
- `build_graph_multi.py --switches N`: per-timestamp graph snapshots.
- `evaluate_topology_loeo.py` (RF, topology ranker) and
  `evaluate_graph_temporal_topology_loeo.py` (GCN, LSTM, GCN+LSTM).
- `explain_rca.py`: XAI with validation checks. `build_topology_comparison.py`:
  tables and plot. `audit_topology_results.py`: independent recomputation.

## 3. Data collection

| Topology | IDs used | COMPLETE | Admitted | Rows | Class support |
|---|---:|---:|---:|---:|---|
| 4 (frozen v3) | - | - | 25 | 16,956 | 8 / 9 / 8 |
| 8 | 30 | 25 | 24 | 30,288 | 3,4,3,4,4,4,2 |
| 12 | 44 | 28 | 26 | 44,712 | every link 2-3 (2,3,2,2,2,3,3,2,3,2,2) |

Raw evidence with SHA-256 manifests: `raw_evidence/topology_{8,12}_switches/`.
Every rejection is recorded with its reason (`exclusion_report.csv`); 18 of
the 44 twelve-switch attempts were rejected (14 sender-duration or stalled
runs, 2 half-rate clients, 1 suspended run, 1 incomplete run). The 12-switch
collection was interrupted by a host suspend that damaged the guest's
timekeeping (kernel soft lockups and RCU stalls; 3 valid runs in 13
attempts afterwards). With approval the VM was rebooted on 2026-10-25, Ryu
restarted per the runbook, and all preflight checks passed; the batch then
produced 17 valid runs in 17 attempts, including an approved one-run
extension so that `s11-s12` reached two experiments.

## 4. LOEO methodology

Leave-one-experiment-out grouped by `experiment_id`; each fold trains on n-1
experiments and tests on one. Per fold, active-metric selection, means,
standard deviations, the ranker threshold, and model weights are fit on the
training experiments only. Labels are joined after ranking. The audit
confirms no held-out ID appears in any training list and that each experiment
is held out exactly once (49/49 checks per topology). Top-k counts and MRR use
the number of admitted experiments as the denominator and are compared to
uniform-random chance (Top-1 1/3, 1/7, 1/11; MRR 0.611, 0.370, 0.275).

## 5. Models

RF on per-switch anomaly statistics (300 trees, depth 5, seed 42); a fixed
four-component topology heuristic; GCN (two GCNConv layers, mean over time);
LSTM over flattened node features; GCN+LSTM; neural models use three fixed
seeds (17, 42, 2026), 100 epochs, and a mean-softmax ensemble. The
generalized code reproduces the frozen four-switch release exactly.

## 6. Results (experiment-level, Top-1 / Top-2 / MRR)

| Model | 4 switches (n=25) | 8 switches (n=24) | 12 switches (n=26) |
|---|---|---|---|
| RF | 20 / 22 / 0.880 | 20 / 23 / 0.910 | 19 / 21 / 0.824 |
| Topology ranker | 13 / 22 / 0.740 | 1 / 11 / 0.412 | 1 / 2 / 0.200 |
| GCN | 20 / 23 / 0.887 | 23 / 23 / 0.972 | 25 / 26 / 0.981 |
| LSTM | 18 / 21 / 0.833 | 22 / 23 / 0.951 | 22 / 23 / 0.896 |
| GCN+LSTM | 23 / 23 / 0.947 | 22 / 22 / 0.933 | 20 / 23 / 0.849 |

Chance Top-1 is 1/3, 1/7, and 1/11; random MRR 0.611, 0.370, 0.275.

Major findings:

- On all three topologies the learned models localize well above chance.
  Paired exact sign tests separate the topology ranker from the learned
  models everywhere; among RF, GCN, LSTM, and GCN+LSTM the only pair below
  p = 0.05 is RF vs GCN on 12 switches (0 vs 6 discordant, p = 0.031,
  uncorrected for ten comparisons; not replicated on 4 switches where it is
  3 vs 3). No superiority claim is made.
- The fixed topology heuristic does not transfer to a 7-candidate chain: its
  threshold is never crossed in the fault window, two components become
  constants, and its imbalance term penalizes the true link
  (`results/audit/topology_ranker_8sw_investigation.md`). It was not tuned.
- On 12 switches (26 experiments, only 2-3 per link) RF, GCN, LSTM, and
  GCN+LSTM stay far above the 1/11 chance level with wide, overlapping
  intervals; GCN+LSTM's individual seeds reach only 13-17/26 while its
  ensemble reaches 20/26, so its fits are unstable at this sample size. The
  heuristic ranker is below chance there (MRR 0.200 vs 0.275). Results are
  exploratory: per-class recall rests on two or three experiments.

## 7. Explainability

| Model | Method | Checks | 4 | 8 | 12 |
|---|---|---|---|---|---|
| RF | exact TreeSHAP on the refit fold model | additivity; top-3 positive-SHAP deletion vs random | 25/25 | 23/24 | 26/26 |
| Topology ranker | component exposure, leave-one-component-out | score recomputation; ranking agreement | 25/25 | 24/24 | 26/26 |
| GCN / LSTM / GCN+LSTM | integrated gradients (512 steps) through the seed ensemble; node/edge/timestep occlusion | completeness; top-2 positive-IG switch deletion vs random | 24/25, 23/25, 22/25 | 22/24, 23/24, 23/24 | 24/26, 25/26, 25/26 |

Failures are deletion checks (attributed inputs not more deletable than
random ones) and are listed per experiment in each `xai_summary.json`. Every
report states that attributions describe the model's score, not causal
evidence, and that scores are uncalibrated. GNNExplainer was not applied
(sequence-of-graphs models); documented.

## 8. Limitations

One emulated topology family on a single-vCPU VM; oracle fault windows; small
samples (n ≤ 26, 2-3 experiments per link on 12 switches); sampling
interval grows with switch count (1.08, 1.23, 1.35 s) so larger topologies
have fewer snapshots per window (6-8 on 12 switches); RX-counter acquisition
shift exists only in the four-switch data; the 8-switch set has 24 rather
than 25 experiments; guest clock was not NTP-synced before the reboot.

## 9. Reproducibility

All commands are in `docs/TOPOLOGY_SCALING_RUNBOOK.md`. Verification on the
final tree: `.\venv\Scripts\python.exe -m unittest discover` (115 tests OK),
`py_compile` on all new modules, `pip check`, `git diff --check`,
`audit_topology_results.py` (49/49 per topology), frozen-artifact hash guard
(`test_frozen_artifacts.py`). Detailed results: `docs/RESULTS_TOPOLOGY_SCALING.md`;
chronology: `EXECUTION_LOG.md`; inventory: `project_inventory.json`.
