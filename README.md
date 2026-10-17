# SDN_RCA

Research prototype for topology-aware, temporally informed root-cause analysis (RCA) in software-defined networks. The current validated task is **conditional fault-window link localization** on a four-switch Mininet/Ryu topology. It ranks the three inter-switch links; it does not yet provide a validated online detector.

## Research question

Does topology and temporal telemetry evidence help identify the initiating failed link more accurately than a conventional Random Forest baseline? Current results do not show that the implemented topology ranker beats RF. They are preliminary, use a small test set, and rely on a known fault phase to select the evaluation window.

## Architecture

Mininet/Open vSwitch generates switch-port counters; the Ryu-side collector records telemetry; experiment runners capture phase events, process evidence, and runtime port mappings; a deterministic builder validates raw evidence and emits a separate candidate dataset; evaluators produce link rankings and provenance. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Earlier v2 evidence (superseded by the v3 results below)

- Derived candidate: `derived_datasets/candidate_with_reaudited_physical21_and_physical23_v2/candidate_dataset.csv`, 12,912 rows, 19 logical experiments, SHA-256 `914fd551778b0eb918a1d74b1fc2476c0ab533909cab0d28a56303255a8bf916`.
- Fixed historical-ID 13/6 split on the updated candidate: RF Top-1 4/6 (66.7%), Top-2 6/6; topology ranker Top-1 3/6 (50.0%), Top-2 6/6. This is the same split membership as the historical comparison, but a revised dataset; do not present it as an unchanged-data replication.
- 18-run leave-one-experiment-out evaluation excluding physical run 21: RF Top-1 15/18 (83.3%), Top-2 16/18; topology ranker Top-1 10/18 (55.6%), Top-2 14/18.
- Run 21 was originally retained as `FAILED_INVALID`; its preserved process/log evidence passed a separate forensic re-audit under corrected iperf2 sequence-statistic semantics. The builder records that original status and reason rather than changing raw metadata.
- Physical run 22 remains `PROVISIONAL` and excluded. Run 20 remains invalid. Original master dataset is untouched.

These are conditional localization results, not online fault detection. Top-3 is necessarily 100% because all three candidate links are returned. The sample is small and the topology ranker currently trails RF.

## Environment and commands

The recorded Windows environment is Python 3.13.7 in `venv/`; core evaluation dependencies are pandas, NumPy, and scikit-learn. The Ubuntu testbed uses Python 3.8.5 and the VM-specific Mininet/Ryu/OVS stack. See [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) for short, non-destructive demo steps.

From the repository root on Windows:

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
.\venv\Scripts\python.exe -m py_compile build_validated_candidate.py evaluate_topology_link_rca.py evaluate_validated_candidate.py evaluate_recollected_fixed_split.py
```

The tests are offline. Do not run the physical experiment runner as part of routine verification. Existing evaluation output directories refuse reuse; choose a new output directory when explicitly regenerating results:

```powershell
.\venv\Scripts\python.exe evaluate_validated_candidate.py --dataset derived_datasets\candidate_with_reaudited_physical21_and_physical23_v2\candidate_dataset.csv --output-dir evaluations\new_loeo_run
.\venv\Scripts\python.exe evaluate_recollected_fixed_split.py --dataset derived_datasets\candidate_with_reaudited_physical21_and_physical23_v2\candidate_dataset.csv --output-dir evaluations\new_fixed_split_run
```

The commands above are source-verified interfaces; the successful measured runs are the existing directories documented in [docs/RESULTS.md](docs/RESULTS.md). A rerun creates new output and should be checked against the recorded provenance before interpretation.

Read-only, saved-artifact demo (prints the existing six-test rankings and checks dataset hashes):

```powershell
.\venv\Scripts\python.exe demo_rca.py
```

## Project map

- `telemetry.py`, `telemetry_pipeline.py`: collection and CSV processing.
- `experiment_runner*.py`: historical runners and safeguarded recollection runner.
- `build_validated_candidate.py`: validation and deterministic candidate construction from preserved run evidence.
- `evaluate_topology_link_rca.py`: established RF and topology-link ranking implementation.
- `evaluate_validated_candidate.py`: grouped leave-one-logical-experiment-out analysis.
- `evaluate_online_fault_detection.py`: separate timestamp-causal anomaly baseline; current result is negative and it does not localize a link.
- `evaluate_graph_temporal_grouped_loeo.py`: fold-isolated graph-only, temporal-only, graph-temporal, RF, and topology comparison on the v3 experiment groups.
- `evaluate_recollected_fixed_split.py`: established 13/6 split membership on the current candidate.
- `demo_rca.py`: read-only replay of a saved evaluation; it does not train or make a new prediction.
- `demo_rca_v3.py`: hash-verified replay of one v3 LOEO result with its measured feature window; no training or live inference.
- `gcn_model.py`, `gcn_lstm.py`, `train_gcn*.py`: phase classification experiments, not current link-localization comparators.
- `docs/`: methodology, data card, protocol, results, limitations, demo, review outline, and paper draft.
- `project_inventory.json`, `EXECUTION_LOG.md`: machine-readable inventory and chronological evidence log.

## Research integrity

Raw experiment evidence, historical datasets, checkpoints, and previous result files are retained. New derived datasets and evaluations use distinct paths and provenance. Never describe phase-oracle localization as online detection, or phase-classification accuracy as RCA accuracy. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) and [docs/DATASET_CARD.md](docs/DATASET_CARD.md).

## Latest verified balanced candidate

The latest candidate is [balanced recollection v3](derived_datasets/balanced_recollection_20261015_v3/candidate_dataset.csv), 16,956 rows across 25 logical experiments. Its forensic admission ledger is `derived_datasets/balanced_recollection_20261015_v3/experiment_admission_ledger_v2.csv`. The protected `master_dataset.csv` remains unchanged. See [v3 dataset card](docs/DATASET_CARD_BALANCED_V3.md) and [v3 results](docs/RESULTS_BALANCED_V3.md).

Reproduce the candidate, graph, and 25-fold RF/topology evaluation into fresh output paths:

```powershell
.\venv\Scripts\python.exe build_validated_candidate.py --run-dir run23_raw_evidence_physical23_logical3 --extra-run-dir run21_failed_raw_evidence_physical21_logical10 --extra-run-dir run24_raw_evidence_physical24_logical20 --extra-run-dir run25_raw_evidence_physical25_logical21 --extra-run-dir run26_raw_evidence_physical26_logical22 --extra-run-dir run27_raw_evidence_physical27_logical23 --extra-run-dir run28_raw_evidence_physical28_logical24 --extra-run-dir run29_raw_evidence_physical29_logical25 --output-dir derived_datasets\NEW_CANDIDATE_DIR
.\venv\Scripts\python.exe build_experiment_admission_ledger.py --candidate-dir derived_datasets\NEW_CANDIDATE_DIR --source run22_milestone_20261014T182846Z\inputs\candidate_master_dataset.csv --manifest run22_milestone_20261014T182846Z\inputs\audit_manifest.csv --output derived_datasets\NEW_CANDIDATE_DIR\experiment_admission_ledger.csv
.\venv\Scripts\python.exe build_graph_multi.py --input derived_datasets\balanced_recollection_20261015_v3\candidate_dataset.csv --output derived_graphs\NEW_GRAPH_DIR\graph_dataset.json
.\venv\Scripts\python.exe evaluate_validated_candidate.py --dataset derived_datasets\balanced_recollection_20261015_v3\candidate_dataset.csv --output-dir evaluations\NEW_EVALUATION_DIR
.\venv\Scripts\python.exe evaluate_online_fault_detection.py --dataset derived_datasets\balanced_recollection_20261015_v3\candidate_dataset.csv --output-dir evaluations\NEW_DETECTION_DIR
.\venv\Scripts\python.exe evaluate_graph_temporal_grouped_loeo.py --output-dir evaluations\NEW_GRAPH_TEMPORAL_LOEO_DIR
.\venv\Scripts\python.exe -m unittest discover -v
```

These commands use exclusive output paths and intentionally fail if a target exists. The measured v3 LOEO output is `evaluations/balanced_recollection_v3_loeo_release/`; the grouped graph/temporal command evaluates the three neural paths against RF/topology on identical held-out experiments. Run 22 remains excluded despite its raw metadata saying `COMPLETE`, because trustworthy iperf process-completion evidence is absent. Localization remains conditional on the annotated fault window. A separate phase-blind online detector was evaluated but failed to detect any of the 25 held-out fault windows; see the results report.

The v3 candidate has an RX acquisition-era shift: all RX-derived fields are zero in its 17 historical source experiments, while all eight recollections have nonzero RX. The saved exploratory direction ablation and its limits are documented in the v3 dataset card and results. A separate 6 Mbps UDP engineering pilot completed at logical 27 / physical 31 after the initial logical 26 / physical 30 attempt was preserved as `FAILED_INVALID`. Neither pilot is part of v3 or model evaluation. The independent audit and prospective repeatability protocol are in [the pilot audit](docs/TRAFFIC_PROFILE_PILOT_AUDIT.md), [the pilot protocol](docs/TRAFFIC_PROFILE_PILOT_PROTOCOL.md), and [the cohort protocol](docs/TRAFFIC_PROFILE_REPEATABILITY_PROTOCOL.md); hashes are in `PILOT_EVIDENCE_SHA256SUMS.txt`.

The completed grouped v3 neural evaluation is preserved at `evaluations/graph_temporal_v3_grouped_loeo_verified/` and independently checked for all 25 24/1 experiment splits, 225 per-seed predictions, 75 score ensembles, prediction/rank consistency, summary metrics, and source/output hashes. Mean-score ensemble results: graph-only 20/25 Top-1 and 23/25 Top-2; temporal-only 18/25 and 21/25; graph-temporal 23/25 and 23/25. Same-fold RF scores 20/25 and 22/25; topology ranking scores 13/25 and 22/25. The three seed fits are not extra independent test cases. These small-sample results are exploratory and do not establish model superiority; all models use annotated fault windows, so these are not online or causal RCA results. The earlier serialization-failed attempt remains separately preserved and excluded. See [the v3 results](docs/RESULTS_BALANCED_V3.md) for intervals, provenance, and limitations.

Replay a v3 held-out experiment from saved results, without training or inference:

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --experiment-id 20 --method rf_baseline
```

The replay checks hashes for the candidate, predictions, split, feature policy, and summary, then prints the selected experiment's annotated ten-second window, measured feature means, saved ranking, and retrospective label.

To perform fresh grouped inference for that held-out experiment (refitting the fold on the other 24 experiments) and print descriptive measurement deltas:

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 20 --method rf_baseline
```

This is offline held-out inference, not online detection. The fault window is selected using the annotated phase; displayed telemetry deltas are descriptive associations, not model attributions or causal evidence.

The v3 online q99 detector remains unsuccessful: it detected 0/25 held-out fault windows and generated 21.6581 false-alarm episodes per observed nonfault hour after correcting the nonfault exposure denominator. An always-no-alarm comparator also detects 0/25, with no false alarms; the detector does not improve on this operating point. The corrected audit output is `evaluations/online_fault_detection_v3_exposure_audit/`. See the updated [results](docs/RESULTS_BALANCED_V3.md) and [limitations](docs/LIMITATIONS.md).
