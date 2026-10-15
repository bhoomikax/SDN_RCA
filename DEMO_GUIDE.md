# SDN Root-Cause Analysis: Five-Minute Progress Demo

**Repository:** `C:\Users\ASUS\sdn-ml`  
**Demo environment:** existing `venv` (Python 3.13.7), Windows PowerShell  
**Purpose:** show the current research pipeline and verified held-out results without training models or regenerating artifacts.

## Project objective and architecture

The project investigates topology- and temporally-aware root-cause analysis for software-defined networks. The current pipeline has two related branches:

1. Switch-port telemetry and experiment labels are stored in `master_dataset.csv`. The graph representation in `graph_dataset_multi.json` contains host/switch nodes, topology edges, time snapshots, and telemetry features.
2. The RCA branch compares an experiment-level Random Forest link classifier against a topology-aware link ranker. The RF ranks the three fault-link classes from early-fault switch features. The topology ranker scores inferred link endpoints using port anomalies and timing components.
3. A separate graph-model branch uses the graph snapshots for normal/fault phase classification. `gcn_multi.pth` and `gcn_lstm.pth` are existing checkpoints. They are not the link-level RCA comparison shown in the saved topology result CSV.

The saved topology evaluation reproduces a stratified split with 13 training experiments and six held-out experiments: **10, 11, 12, 15, 16, and 18**. The split is experiment-level. The evaluator fits the RF and the topology normal baselines using training experiments only.

## Five-minute sequence

| Time | Show | Suggested narration |
|---|---|---|
| 0:00–0:45 | Open this guide, then `master_dataset.csv` and `graph_dataset.json` | “The project starts from switch-port telemetry and experiment labels, with a separate graph snapshot representation for topology-based models.” |
| 0:45–1:30 | Open `evaluate_topology_link_rca.py`; point out the split constants, RF baseline, and separate topology ranking path | “The link RCA evaluation holds out whole experiments and compares the same six cases for both methods.” |
| 1:30–2:30 | Open `topology_link_rca_results.csv`; run the summary command below | “On these six experiments, RF gets 5 of 6 correct at rank one and all 6 within the top two. The topology-aware ranker gets 3 of 6 at rank one and 5 of 6 within the top two.” |
| 2:30–3:30 | Open `diagnose_topology_link_rca_results.csv`; filter experiment 10 with the command below | “This diagnostic exposes each candidate link’s endpoint evidence and four component ranks. In these selected cases, the timing components do not discriminate because no endpoint crosses the training-normal threshold.” |
| 3:30–4:20 | Open `topology_link_rca_second_stage_diagnostic.md` to the TX and timing sections | “TX rate and throughput are nearly perfectly correlated because both derive from counter deltas, although throughput retains packet-size information. The phase window may also be early relative to the actual link failure.” |
| 4:20–5:00 | Show the limitations and proposed next steps below | Give the short faculty explanation at the end of this guide. |

### Read-only commands verified in this repository

Run these in PowerShell from the repository directory. They inspect the existing environment and saved outputs; they do not train models or write files.

```powershell
& .\venv\Scripts\python.exe --version

Import-Csv .\topology_link_rca_results.csv |
  Where-Object { $_.record_type -eq 'overall_metric' } |
  Select-Object method,test_support,top1_accuracy,top2_accuracy,top3_accuracy |
  Format-Table -AutoSize

Import-Csv .\topology_link_rca_results.csv |
  Where-Object { $_.record_type -eq 'experiment' -and $_.method -eq 'rf_baseline' } |
  Select-Object experiment_id,actual_link,rank1_link,rank2_link,top1_hit,top2_hit |
  Format-Table -AutoSize

Import-Csv .\diagnose_topology_link_rca_results.csv |
  Where-Object { $_.experiment_id -eq '10' } |
  Select-Object experiment_id,candidate_link,rank_link_anomaly,rank_endpoint_imbalance,
    rank_pair_onset,rank_propagation_margin,final_aggregate_score,final_score_tied |
  Format-Table -AutoSize
```

**Verified here:** the interpreter command and the PowerShell CSV queries above were run successfully against the existing files. The saved evaluation rows were also checked against `master_dataset.csv`: both methods contain exactly the six held-out IDs, and all recorded actual labels match the dataset. The aggregate Top-1/Top-2 counts below were recomputed from those six saved rankings.

**Source-inspected, not run for this demo:** graph building and model-training commands are described below. Do not run them during the five-minute presentation.

## Verified saved RCA results

| Method | Top-1 | Top-2 | Top-3 | Counts on six tests |
|---|---:|---:|---:|---|
| RF baseline | **83.33%** | **100%** | 100% | 5/6, 6/6, 6/6 |
| Topology-aware link ranker | **50%** | **83.33%** | 100% | 3/6, 5/6, 6/6 |

Top-3 is guaranteed to reach 100% here because the task ranks exactly three candidate links. It is not evidence that the ranking is useful; emphasize Top-1 and Top-2. These are results on only six held-out experiments, not a large independent evaluation.

## What the diagnostics found

- `tx_packet_rate` and `tx_throughput_mbps` have training-normal Pearson correlation **0.99999918** and Spearman correlation **0.99581913**. The collector derives both from packet/byte counter deltas over the same fixed interval. The features are not identical: throughput also reflects bytes per packet and traffic mix.
- RX rate features are constant zero in the training-normal data and are excluded from the topology anomaly score.
- The fixed training-normal 95th-percentile onset threshold is **1.4596229666**. There were zero strict threshold crossings among 2,880 annotated fault-phase port rows. Pair-onset and propagation components therefore tie across candidates in the selected experiments; they currently add no discriminating timing evidence.
- The annotated phase window is oracle information. The second-stage report found that the merger marks fault at elapsed 20 seconds, while runner timing implies the actual link disconnect may happen roughly five seconds later. Exact phase-log event timestamps for the saved runs are unavailable.

## Relevant files to open

- `master_dataset.csv` — merged switch-port telemetry and labels.
- `graph_dataset.json` and `graph_dataset_multi.json` — graph/topology snapshots; the latter is used by the multi-snapshot GCN path.
- `train_rca.py`, `train_rca_temporal.py` — earlier RF RCA implementations.
- `evaluate_topology_link_rca.py` — current RF/topology link comparison and fixed split.
- `topology_link_rca_results.csv` — saved per-experiment rankings and aggregate/class metrics.
- `diagnose_topology_link_rca.py`, `diagnose_topology_link_rca_results.csv` — endpoint-level evidence for experiments 10, 15, 16, and 18.
- `topology_link_rca_second_stage_diagnostic.md` — TX feature, onset, phase-timing, and port-mapping findings.
- `train_gcn_multi.py`, `gcn_lstm.py`, `gcn_multi.pth`, `gcn_lstm.pth` — separate graph phase-classification branch and existing checkpoints.

## Scripts and execution order

For tomorrow’s demonstration, **run no training or artifact-generation scripts**. Use the existing CSVs and the verified read-only commands above. The available Python is `venv\Scripts\python.exe`; activating the environment is unnecessary when invoking that interpreter by path.

For orientation only, the source-inspected build/training paths are:

- Graph branch: `build_graph_multi.py` reads `master_dataset.csv` and writes `graph_dataset_multi.json`; `train_gcn_multi.py` trains a 100-epoch phase classifier and writes `gcn_multi.pth`. `gcn_lstm.py` reads `graph_dataset_multi.json`, trains the temporal graph model, and writes `gcn_lstm.pth`.
- Link RCA branch: `train_rca.py` and `train_rca_temporal.py` fit and print RF evaluations from `master_dataset.csv`. The current standalone comparison is `evaluate_topology_link_rca.py`, which reads that dataset and writes `topology_link_rca_results.csv`.
- Diagnostic: `diagnose_topology_link_rca.py` reads the dataset and writes its diagnostic CSV.

These are not demo commands. Training scripts can overwrite checkpoints or generated graph data. Both standalone evaluators use exclusive output creation: because their result CSVs already exist, rerunning them refuses to overwrite the files. The diagnostic script stops immediately when its output CSV already exists. The saved results have already been checked, so rerunning is unnecessary.

## Limitations and blockers

1. The RF/topology comparison has only six held-out experiments.
2. OpenFlow port-to-Mininet-interface mapping is inferred from link order and port numbering; no runtime port/interface crosswalk is saved.
3. The source merger’s fixed elapsed-time phase labels may precede actual link failure by roughly five seconds.
4. Current timing components do not discriminate: selected candidate links receive identical no-crossing onset and propagation values.
5. The provided telemetry source has a filename mismatch that can block a fresh merge. `experiment_runner.py` and `experiment_runner_batch.py` compute `experiments/telemetry_<id>.csv` but launch `telemetry.py` without passing that path. The collector writes the fixed filename `telemetry_features.csv`, while `merge_experiments.py` expects `experiments/telemetry_<id>.csv`. The present merged dataset allows this demo to proceed, but the source path will not feed the merger as written without an external rename/copy step. The pipeline was not changed.
6. The project README contains only the project name; this guide documents the verified demo path. The source archive is outside the repository at `C:\Users\ASUS\Downloads\sdn_telemetry_source.tar.gz`.

The saved CSVs and Python environment are available, so none of these issues blocks the five-minute artifact-based demo. The telemetry filename mismatch blocks a clean rerun of collection-to-merge from the supplied source as written.

## Short progress explanation

“I have a working SDN telemetry dataset, graph representations, and baseline RCA experiments. On the same six held-out experiments, the RF baseline localizes the faulty link in the top two for all six cases; the current topology-aware ranker does so in five of six. The diagnostic work identified why temporal evidence is not helping yet: no fault-phase sample crosses the training-normal onset threshold, and phase labeling may start before the actual injected failure. The port mapping also needs runtime verification. My next steps are to correct and validate the collection-to-merge path, align labels to recorded fault-event timestamps, verify OpenFlow port mappings, then improve and evaluate link-level temporal RCA on a larger held-out set.”
