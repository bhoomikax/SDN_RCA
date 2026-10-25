# Results: topology scaling to 8 and 12 switches, with explanations

Collected and evaluated on 2026-10-23 to 2026-10-25. Everything here is conditional
fault-window link localization: the annotated fault phase selects the first
ten seconds of each experiment, and the model ranks the N-1 inter-switch
candidate links. It is not online detection and not causal root-cause
analysis. All scores are uncalibrated ranking scores. Experiments are the
independent units; seeds and folds are not.

## What was collected

| Topology | Registry IDs attempted | COMPLETE | Admitted after the offered-rate rule | Target |
|---|---:|---:|---:|---:|
| 8 switches (7 candidates) | 30 (logical 101-130) | 25 | **24** | 25 |
| 12 switches (11 candidates) | 44 (logical 201-244) | 28 | **26** | 25 |

Raw evidence: `raw_evidence/topology_8_switches/` (30 run directories) and
`raw_evidence/topology_12_switches/` (44), each with `SHA256SUMS.txt`,
`batch_log.jsonl`, and the batch console log. Every admitted run has six raw
files (telemetry, phase events, runtime port mapping, metadata, iperf client
and server logs) whose hashes are recorded in the candidate's
`provenance.json`. Nothing was relabeled, duplicated, or synthesized; the
shortfall is reported as a shortfall.

Admission used the existing rules (COMPLETE status, schema, finite values,
duplicate keys, full switch and candidate-link mapping coverage, reciprocal
target mapping, ordered phase coverage inside the telemetry span, iperf
process records, sender duration 60 ± 2 s, agreeing receiver reports) plus
one new rule: the iperf sender's reported rate must be within ±10% of the
6 Mbps profile. Three COMPLETE runs that paced only ~3 Mbps were excluded by
that rule (8-switch 1122; 12-switch 1210, 1212). Exclusion reasons are in each
candidate's `exclusion_report.csv`.

How the 12-switch set was collected: after 7 clean runs the VM was suspended
mid-run (run 1208 is preserved as `RUNNING_INVALID_UNTIL_COMPLETE`; its stale
bridges were removed with `cleanup_abandoned_run.py`). After the resume,
12-switch runs failed at a high rate (sender durations of 73-163 s, sender
rates of ~3 Mbps, iperf servers that never exited): 3 valid runs in 13
attempts (IDs 209-227) across four relaunches, even with the host on mains,
kept awake, and idle. The guest kernel log showed `soft lockup - CPU#0 stuck
for 9842s` and RCU stalls from the host suspends. With explicit approval the
VM was rebooted on 2026-10-25 (the documented `reboot` was ineffective because
systemd's bus was wedged; a `sync; reboot -f` was used), Ryu was restarted per
the runbook, and the preflight checks passed (0 kernel warnings, loopback
iperf 6.29 Mbps, 11 links, 0% ping loss). After recovery the batch produced
**17 valid runs in 17 attempts** (IDs 228-244, one of them an approved
one-run extension so that `s11-s12` reached two experiments). All 26
admitted runs paced exactly 6.29 Mbit/s. The three remaining 8-switch
attempts (128-130) had failed before the reboot, so the 8-switch set stays at
24. 12-switch IDs 245-260 remain unused.

## Data properties per topology

| Property | 4 switches (frozen v3) | 8 switches | 12 switches |
|---|---|---|---|
| Experiments | 25 | 24 | 26 |
| Candidate links | 3 | 7 | 11 |
| Class support | 8 / 9 / 8 | 3,4,3,4,4,4,2 | 2,3,2,2,2,3,3,2,3,2,2 (every link 2-3) |
| Rows | 16,956 | 30,288 | 44,712 |
| Median sampling interval | ~1.08 s | 1.23 s | 1.35 s |
| Snapshots in the 10 s fault window | 9-10 | 7-9 | 6-8 |
| RX counters | zero in 17 historical runs, nonzero in 8 recollections | nonzero in all runs | nonzero in all runs |
| Active metrics per fold | all four | all four | all four |
| Link endpoint ports | setup-inferred static mapping | recorded runtime mapping, identical across runs | recorded runtime mapping, identical across runs |

The sampling interval grows with switch count because the collector polls
every switch with two `ovs-ofctl` calls per sample on a single vCPU; the
collector code and its 1 s nominal interval are unchanged. Rates are computed
per nominal second, so absolute rates are inflated by the same factor within
a topology; all models normalize within topology, so this does not mix
topologies, but it does mean fewer snapshots per fault window on larger
topologies. Link bandwidth (10 Mbps / 5 ms on the middle link), offered load
(6 Mbps UDP), phase durations (20/20/20 s), fault type (link down/up), and
fault duration are identical across topologies. The RX-counter acquisition
shift exists only in the four-switch data.

## Five-model LOEO results

Chance levels for uniform random ranking: Top-1 1/3, 1/7, 1/11; MRR 0.611,
0.370, 0.275 for 4, 8, 12 switches. Metrics are experiment-level, Wilson 95%
intervals use the experiment count.

### 4 switches (existing frozen results; reproduced exactly by the new code)

| Model | Top-1 | Top-2 | MRR |
|---|---:|---:|---:|
| Random Forest | 20/25 (80%) | 22/25 (88%) | 0.8800 |
| Topology ranker | 13/25 (52%) | 22/25 (88%) | 0.7400 |
| GCN | 20/25 (80%) | 23/25 (92%) | 0.8867 |
| LSTM | 18/25 (72%) | 21/25 (84%) | 0.8333 |
| GCN+LSTM | 23/25 (92%) | 23/25 (92%) | 0.9467 |

Regression check of the generalized code on the frozen v3 data
(`results/topology_4_switches_regression/`): all 50 RF/topology rankings and
all 75 ensemble neural rankings are identical to the release, with ensemble
score differences of 0.0.

### 8 switches (24 experiments, 7 candidates)

| Model | Top-1 | Top-2 | Top-3 | MRR | Top-1 Wilson 95% |
|---|---:|---:|---:|---:|---|
| Random Forest | 20/24 (83%) | 23/24 (96%) | 24/24 | 0.910 | [64.1%, 93.3%] |
| Topology ranker | 1/24 (4%) | 11/24 (46%) | 20/24 | 0.412 | [0.7%, 20.2%] |
| GCN | 23/24 (96%) | 23/24 (96%) | 24/24 | 0.972 | [79.8%, 99.3%] |
| LSTM | 22/24 (92%) | 23/24 (96%) | 24/24 | 0.951 | [74.2%, 97.7%] |
| GCN+LSTM | 22/24 (92%) | 22/24 (92%) | 22/24 | 0.933 | [74.2%, 97.7%] |

Neural rows are the 3-seed mean-score ensemble; per-seed Top-1 counts were
GCN 23/23/24, LSTM 22/22/22, GCN+LSTM 20/20/22. Every neural Top-1 error is an
adjacent or near link; `s5-s6` (3 of 4 correct) and `s3-s4` (2 of 3 for LSTM
and GCN+LSTM) carry the misses. Seeds are repeated fits, not independent
test cases, and the Wilson intervals overlap heavily across the three neural
models and RF; nothing here establishes that one model is better than
another, and the 4-vs-8 ordering of the neural models differs (GCN+LSTM led
on 4 switches, GCN on 8), which is consistent with sampling noise at n=24/25.

RF's four Top-1 errors are all adjacent links (ranked 2 or 3), and both
`s7-s8` experiments were missed. The topology ranker collapses: with a link
down, every port downstream of the fault stops carrying traffic, so all
downstream links tie on the `link_anomaly` component; no port crossed the
training-normal threshold inside the window in most folds (`pair_onset` and
`propagation_margin` are uninformative), and the final order is decided by
endpoint-imbalance noise. This is a property of the fixed heuristic on a
longer chain, not a code change: the same code reproduces the four-switch
release exactly. Its MRR (0.412) is at chance (0.370).

### 12 switches (26 experiments, 11 candidates)

| Model | Top-1 | Top-2 | Top-3 | MRR | Top-1 Wilson 95% | Per-seed Top-1 |
|---|---:|---:|---:|---:|---|---|
| Random Forest | 19/26 (73%) | 21/26 (81%) | 24/26 | 0.824 | [53.9%, 86.3%] | n/a |
| Topology ranker | 1/26 (4%) | 2/26 (8%) | 2/26 | 0.200 | [0.7%, 18.9%] | n/a |
| GCN | 25/26 (96%) | 26/26 (100%) | 26/26 | 0.981 | [81.1%, 99.3%] | 25/22/25 |
| LSTM | 22/26 (85%) | 23/26 (88%) | 24/26 | 0.896 | [66.5%, 93.8%] | 21/21/20 |
| GCN+LSTM | 20/26 (77%) | 23/26 (88%) | 23/26 | 0.849 | [57.9%, 89.0%] | 13/13/17 |

Every held-out link now appears in training at least once (2-3 experiments
per link), so this is a legitimate but small grouped LOEO. Chance Top-1 is
1/11 and random MRR 0.275. RF's seven misses are mostly adjacent links; both
`s2-s3` and both `s4-s5` experiments were missed, so with only two
experiments per class single-link recall swings between 0 and 1. GCN's one
miss (202, `s2-s3` ranked second) and LSTM's four are adjacent or near links.
GCN+LSTM's seed-level Top-1 varies from 13 to 17 of 26 while the ensemble
reaches 20, i.e. its individual fits are unstable at this sample size. The
topology ranker is below chance (MRR 0.200 vs 0.275): with 11 candidates its
untriggered onset components and the imbalance term (see the 8-switch
investigation) leave the ranking to noise. With 26 experiments and 11
classes these are exploratory estimates with wide intervals; the model
intervals overlap except for the ranker.

## Independent audit and paired comparisons

`audit_topology_results.py` recomputed every reported number from the
per-experiment rows for all three topologies: 49/49 checks pass per topology
(grouped splits with the held-out experiment absent from every training list,
training size n-1, each experiment held out once, rankings are permutations
of the N-1 candidates, Top-k/MRR and denominators recomputed, chance levels
1/K, ensemble scores equal the per-seed means, RF/neural references agree,
XAI rankings and identities agree with the evaluation rows). Output:
`results/audit/methodology_audit.{json,md}`.

Seen versus unseen fault links: on all three topologies every held-out link
appears in training (0 unseen experiments); on 12 switches each held-out
class has only 1-2 training examples.

Paired experiment-level Top-1 comparisons (exact two-sided sign test on
discordant pairs, uncorrected for multiple testing):

| Topology | Pair | A right, B wrong | B right, A wrong | p |
|---|---|---:|---:|---:|
| 4 | RF vs topology ranker | 8 | 1 | 0.039 |
| 4 | RF vs GCN+LSTM | 0 | 3 | 0.250 |
| 4 | GCN vs GCN+LSTM | 1 | 4 | 0.375 |
| 4 | LSTM vs GCN+LSTM | 0 | 5 | 0.062 |
| 4 | topology ranker vs GCN+LSTM | 0 | 10 | 0.002 |
| 8 | RF vs topology ranker | 20 | 1 | < 0.001 |
| 8 | RF vs GCN | 0 | 3 | 0.250 |
| 8 | GCN vs GCN+LSTM | 1 | 0 | 1.000 |
| 8 | topology ranker vs each neural model | 1 | 22-23 | < 0.001 |
| 12 | RF vs topology ranker | 18 | 0 | < 0.001 |
| 12 | RF vs GCN | 0 | 6 | 0.031 |
| 12 | RF vs LSTM | 0 | 3 | 0.250 |
| 12 | RF vs GCN+LSTM | 2 | 3 | 1.000 |
| 12 | GCN vs GCN+LSTM | 5 | 0 | 0.062 |
| 12 | GCN vs LSTM | 3 | 0 | 0.250 |
| 12 | topology ranker vs each neural model | 0 | 19-24 | < 0.001 |

The paired differences that survive on every topology are between the
topology ranker and the learned models. Among RF, GCN, LSTM, and GCN+LSTM the
only pair below p = 0.05 is RF vs GCN on 12 switches (0 vs 6 discordant
experiments, p = 0.031, uncorrected for the ten comparisons per topology);
with a Bonferroni-style correction it does not survive, and GCN's advantage
is not consistent across topologies (RF vs GCN is 3 vs 3 on 4 switches). The
reordering of the three neural models across topologies is within sampling
noise. No model is declared superior.

### Why the topology ranker fails on 8 switches

`results/audit/topology_ranker_8sw_investigation.md` documents the mechanism:
the training-normal 95th-percentile threshold (2.56-2.58) is never crossed by
fault-window ports (anomaly 1.1-1.2, because per-port normal standard
deviations are of the same order as the mean rate), so the onset and
propagation components are constants; the actual link and all downstream
links share the same anomaly (traffic stops beyond the fault); the actual
link is first by `link_anomaly` alone in 17/24 experiments but has a larger
endpoint imbalance than fully dead downstream links, so the imbalance
component cancels its advantage and ties are decided by noise. Port mapping,
candidate generation, window, and tie-breaking were verified correct. The
heuristic was not modified, because any change favouring the most upstream
anomalous link would be tuned to these outcomes.

## Explainability (XAI)

No explanation code existed before this work; RF scores were `predict_proba`
vote fractions and neural scores softmax outputs, neither calibrated. The new
layer (`explain_rca.py`) produces, per held-out experiment and model, a JSON
and a Markdown report with the predicted ranking and scores, the ground
truth, Top-1 status, the main supporting evidence, the relevant switches and
ports, the method, its limitations, and the score semantics.

| Model | Method | Validation checks | 4 switches | 8 switches | 12 switches |
|---|---|---|---|---|---|
| Random Forest | shap.TreeExplainer exact Shapley values on the refit fold model (same seed, same features; refit ranking asserted equal to the saved one) | additivity: base + ΣSHAP = predicted vote fraction (error < 1e-6); deletion: neutralizing the top-3 positive-SHAP features at the training mean lowers the predicted-class score at least as much as 3 random features (20 draws) | 25/25 pass | 23/24 pass (one deletion-check failure) | 26/26 pass |
| Topology ranker | exposure of the four components, their rank utilities, the equal-weight aggregate, endpoint anomaly/onset values, and leave-one-component-out sensitivity | rank_score recomputed as the mean of utilities; ranking identical to the saved evaluation | 25/25 pass | 24/24 pass | 26/26 pass |
| GCN / LSTM / GCN+LSTM | integrated gradients (512 steps, zero baseline in normalized space) through the 3-seed mean-softmax ensemble on the actual fault-window graph sequence; node, edge (GCN models only), and timestep occlusion deltas; recomputed ensemble scores asserted equal to the saved ones | completeness: ΣIG = f(x) − f(baseline) within 5% relative (or 1e-3 absolute); deletion: zeroing the top-2 positive-IG switches lowers the score at least as much as 2 random switches (20 draws) | GCN 24/25, LSTM 23/25, GCN+LSTM 22/25 pass | GCN 22/24, LSTM 23/24, GCN+LSTM 23/24 pass (all completeness checks pass; 4 deletion-check failures) | GCN 24/26, LSTM 25/26, GCN+LSTM 25/26 pass (all completeness checks pass; deletion-check failures on experiments 205 and 238 for GCN, 239 for LSTM, 231 for GCN+LSTM) |

Twelve-switch detail: the two largest-|IG| switches coincide with the
predicted link's endpoints in 27% (GCN), 19% (LSTM), and 12% (GCN+LSTM) of
experiments; as on 8 switches, attributions spread along the chain where
traffic disappears.

Eight-switch detail: mean |IG| per switch is spread along the chain for all
three models (GCN 0.16-0.27 per switch, GCN+LSTM 0.15-0.38), and the two
largest-|IG| switches coincide with the predicted link's endpoints in 12%
(GCN), 38% (LSTM), and 33% (GCN+LSTM) of experiments. The models separate
links mainly through where along the chain traffic disappears, not through
the two endpoint switches alone. RF's global mean |SHAP| is dominated by the
`s1_*` statistics (0.012-0.017), i.e. the ingress switch's anomaly summary.

Four-switch detail: with 64 IG steps the completeness gap reached 0.59 on
these piecewise-linear ensembles; 512 steps closes it (74/75 within 5%, worst
9.6%). The deletion check fails in 5/75 neural cases, i.e. the attributed
switches were not more "deletable" than random ones; those cases are listed
per experiment in `results/xai/topology_4_switches/xai_summary.json`. The
fraction of neural explanations whose two largest |IG| switches are exactly
the predicted link's endpoints is 36% (GCN), 16% (LSTM), 32% (GCN+LSTM):
attributions are spread along the chain, consistent with the whole downstream
path losing traffic.

GNNExplainer (PyG) was not applied: it expects a single-graph
`forward(x, edge_index)`, whereas these models consume a sequence of graphs;
applying it to a time-averaged input would explain a different function. The
limitation is documented in every neural report. No explanation is causal
evidence; attributions describe each model's score function on
oracle-selected windows.

## Runtime and resources

| Item | Measured |
|---|---|
| Live run duration | 84-100 s per run (8 and 12 switches); 60 s traffic + setup/teardown |
| Collector sweep (idle) | 0.20 s (8 switches), 0.31-0.37 s (12 switches) |
| RF/topology LOEO | < 1 min per topology |
| Neural LOEO, 4 switches, 225 fits | 4,744 s with a second job competing |
| Neural LOEO, 8 switches, 216 fits | wall clock 49,383 s, but the laptop slept twice during the run; the CPU-only estimate from unaffected folds is about 90-200 s per fold (GCN+LSTM mean fit 126 s) |
| Neural LOEO, 12 switches, 234 fits (final, 26 experiments) | wall clock 68,349 s including a host sleep after the collection window; not a compute estimate (the 81-fit run on 9 experiments took 665 s alone) |
| XAI, 4 switches, 25 experiments, 5 models, 512 IG steps | about 25 min while sharing the CPU (64 steps alone: 360 s) |
| XAI, 12 switches, 26 experiments, 5 models, 512 IG steps | 685 s |
| XAI, 8 switches, 24 experiments, 5 models | wall clock 18,675 s, inflated by a laptop sleep; the 12-switch rate implies roughly 10 minutes of compute |
| Comparison table and plot | `results/comparison_4_8_12/` (`comparison_table.md/.csv`, `comparison.json`, `comparison.png`) |
| VM | 1 vCPU, 2 GB RAM, Ubuntu 20.04, OVS 2.13.1, iperf2 2.0.13, clock not NTP-synced |

## What this does and does not show

- The generalized pipeline (topology, runner, builder, graph, five models,
  LOEO, XAI) works end to end on 8 and 12 switches with real Mininet runs.
- On 8 switches RF remains strong (20/24 Top-1 against a 1/7 chance level);
  the fixed topology heuristic does not transfer to a longer chain.
- On 8 switches all three neural models and RF localize well above chance
  (22-23/24 and 20/24 Top-1 against 1/7); their intervals overlap.
- On 12 switches (26 experiments, 2-3 per link) RF, GCN, LSTM, and GCN+LSTM
  are again far above the 1/11 chance level, with wide, overlapping
  intervals; the fixed heuristic is at or below chance on both larger
  topologies.
- No claim is made that any model "scales better"; the candidate count,
  sample size, class support, and snapshot count all change with topology.
- All results remain conditional on oracle fault windows and one controlled
  emulated topology family.
