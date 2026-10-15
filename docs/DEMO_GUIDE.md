# Five-minute offline demo

Use saved outputs so the demo does not depend on VM state or launch experiments.

## Sequence

1. **Objective (30 s):** explain the path H1–S1–S2–S3–S4–H2 and the question: can telemetry rank the failed inter-switch link?
2. **Run the saved-artifact replay (60 s):** from the repo root run `.\venv\Scripts\python.exe demo_rca.py`. It checks the candidate hash against both provenance files, shows the topology, split, saved six-experiment rankings, and the oracle caveat. It performs no training or new inference.
3. **Data provenance (45 s):** open `derived_datasets/candidate_with_reaudited_physical21_and_physical23_v2/provenance.json`. Point out 19 logical experiments, separate physical IDs 21/23, preserved exclusions, and run 22 provisional status.
4. **Measured comparison (60 s):** open `evaluations/recollected_13_6_split_v4/topology_link_rca_results.csv` and `evaluation_provenance.json`. RF: Top-1 4/6, Top-2 6/6; topology ranker: Top-1 3/6, Top-2 6/6. Explain this is conditional localization using fault-phase oracle annotations.
5. **Generalization check (45 s):** open `evaluations/validated_candidate_physical23_loeo/evaluation_summary.json`. RF 15/18 Top-1; topology 10/18. Call out s2-s3 weakness and nondiscriminative Top-3.
6. **Honest next step (40 s):** show `docs/LIMITATIONS.md`: phase-blind online evaluation and more balanced runs are needed; do not claim topology gain.

## Optional offline verification

From PowerShell at the repository root:

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
```

This command was executed successfully on the current Windows checkout (50 tests). It is not needed during the five-minute presentation. Do not run experiment scripts during the demo. Evaluation rerun commands appear in the root README and write only to a new output directory.

## Claims to make precisely

“We have a validated telemetry pipeline, a provenance-aware candidate dataset, and two experiment-level link-ranking evaluations. In this small conditional localization study, RF currently performs better than the topology ranker. The temporal/onset evidence does not yet improve discrimination, and the next step is phase-blind online evaluation with more balanced, runtime-mapped runs.”
