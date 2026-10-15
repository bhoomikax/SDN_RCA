# SDN_RCA

Research prototype for topology-aware, temporally informed root-cause analysis (RCA) in software-defined networks. The current validated task is **conditional fault-window link localization** on a four-switch Mininet/Ryu topology. It ranks the three inter-switch links; it does not yet provide a validated online detector.

## Research question

Does topology and temporal telemetry evidence help identify the initiating failed link more accurately than a conventional Random Forest baseline? Current results do not show that the implemented topology ranker beats RF. They are preliminary, use a small test set, and rely on a known fault phase to select the evaluation window.

## Architecture

Mininet/Open vSwitch generates switch-port counters; the Ryu-side collector records telemetry; experiment runners capture phase events, process evidence, and runtime port mappings; a deterministic builder validates raw evidence and emits a separate candidate dataset; evaluators produce link rankings and provenance. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Current evidence

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
- `evaluate_recollected_fixed_split.py`: established 13/6 split membership on the current candidate.
- `demo_rca.py`: read-only replay of a saved evaluation; it does not train or make a new prediction.
- `gcn_model.py`, `gcn_lstm.py`, `train_gcn*.py`: phase classification experiments, not current link-localization comparators.
- `docs/`: methodology, data card, protocol, results, limitations, demo, review outline, and paper draft.
- `project_inventory.json`, `EXECUTION_LOG.md`: machine-readable inventory and chronological evidence log.

## Research integrity

Raw experiment evidence, historical datasets, checkpoints, and previous result files are retained. New derived datasets and evaluations use distinct paths and provenance. Never describe phase-oracle localization as online detection, or phase-classification accuracy as RCA accuracy. See [docs/LIMITATIONS.md](docs/LIMITATIONS.md) and [docs/DATASET_CARD.md](docs/DATASET_CARD.md).
