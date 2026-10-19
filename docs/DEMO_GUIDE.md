# Five-minute offline demo

Use saved outputs so the demo does not depend on VM state or launch experiments.

## Sequence

1. **Objective (30 s):** explain the path H1–S1–S2–S3–S4–H2 and the question: can telemetry rank the failed inter-switch link?
2. **Run the saved-artifact replay (60 s):** from the repo root run `.\venv\Scripts\python.exe demo_rca.py`. It checks the candidate hash against both provenance files, shows the topology, split, saved six-experiment rankings, and the oracle caveat. It performs no training or new inference.
3. **Data provenance (45 s):** open `derived_datasets/candidate_with_reaudited_physical21_and_physical23_v2/provenance.json`. Point out 19 logical experiments, separate physical IDs 21/23, preserved exclusions, and run 22 provisional status.
4. **Measured comparison (60 s):** open `evaluations/recollected_13_6_split_v4/topology_link_rca_results.csv` and `evaluation_provenance.json`. RF: Top-1 4/6, Top-2 6/6; topology ranker: Top-1 3/6, Top-2 6/6. Explain this is conditional localization using fault-phase oracle annotations.
5. **Generalization check (45 s):** open `evaluations/validated_candidate_physical23_loeo/evaluation_summary.json`. RF 15/18 Top-1; topology 10/18. Call out s2-s3 weakness and nondiscriminative Top-3.
6. **Honest next step (40 s):** show `docs/LIMITATIONS.md`: phase-blind online evaluation and more balanced runs are needed; do not claim topology gain. The separate physical-31 low-load pilot is engineering evidence only and is not in v3.

For a v3 replay, run `.\venv\Scripts\python.exe demo_rca_v3.py --experiment-id 20 --method rf_baseline`. This is **saved-result replay only**: it checks the input/result hashes and displays the recorded prediction; it does not fit or score a new model. For separate **fresh held-out inference**, run `.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 20 --method rf_baseline`. This refits the selected LOEO fold on the other 24 experiments, checks candidate provenance, and prints the actual ranking and descriptive measured telemetry. Experiment 20 is excluded from training, but the window is still selected with its annotated fault phase. The displayed differences are measurements, not explanations of the model output or causal evidence.

Both modes were separately verified on the current source. They agree on the ranking `s2-s3 > s3-s4 > s1-s2`; the retrospective label is `s1-s2`, which is missed at Top-2. The grouped graph/temporal results and their complete artifact checks are reported in [the v3 results](RESULTS_BALANCED_V3.md).

## Optional: the isolated live run (60 s)

Show `reports/live_demo_physical45_logical41/README.md`. Then run, without the VM:

```powershell
.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 41 --method rf_baseline --dataset derived_datasets\live_demo_physical45_logical41\candidate_dataset.csv
```

It ranks `s2-s3 > s1-s2 > s3-s4` and trains on 17 historical experiments without experiment 41. The retrospective label is `s2-s3`. Say clearly that this is one valid exploratory run, separate from v3, and not an accuracy estimate. The earlier attempt 40/44 is `FAILED_INVALID` and is not used.

## Optional offline verification

From PowerShell at the repository root:

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
```

The current Windows source suite passed 82 tests; current-source runner tests (41) and compilation also passed on the Ubuntu VM. The VM's full project suite was not run. See `EXECUTION_LOG.md` and the [end-to-end runbook](END_TO_END_RUNBOOK.md) for exact commands and live-run limitations. This is not needed during the five-minute presentation. Do not run experiment scripts during the demo. Evaluation rerun commands appear in the root README and write only to a new output directory.

## Claims to make precisely

“We have a tested telemetry pipeline, a provenance-aware candidate dataset, and experiment-grouped link-ranking evaluations. In the v3 conditional localization study, RF currently performs better than the topology ranker. The online detector is unsuccessful, and the separate low-load pilot is exploratory engineering evidence, not a model-evaluation cohort. Fresh inference and saved-result replay are distinct demo modes. The next step is a controlled, independently repeated traffic cohort and a separately validated phase-blind detector.”
