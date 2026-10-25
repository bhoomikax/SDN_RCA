# Cross-topology comparison (grouped LOEO, conditional fault-window localization)

Top-k and MRR are not comparable across topologies at face value: the candidate count grows with topology size, so chance Top-1 is 1/3, 1/7, and 1/11 and random MRR is 0.611, 0.370, and 0.275 for 4, 8, and 12 switches. Seeds and folds are not independent experiments; the independent unit is the experiment. Scores are uncalibrated ranking scores and the fault window is oracle-selected.

| Topology | Valid experiments | Candidates | Model | Top-1 | Top-2 | MRR | Top-1 Wilson 95% CI | Chance Top-1 / MRR | XAI status |
|---|---:|---:|---|---:|---:|---:|---|---|---|
| 4 switches | 25 | 3 | Random Forest | 20/25 (80%) | 22/25 (88%) | 0.8800 | [60.9%, 91.1%] | 0.333 / 0.611 | tested: 25/25 sanity checks pass |
| 4 switches | 25 | 3 | Topology ranker | 13/25 (52%) | 22/25 (88%) | 0.7400 | [33.5%, 70.0%] | 0.333 / 0.611 | tested: 25/25 sanity checks pass |
| 4 switches | 25 | 3 | GCN | 20/25 (80%) | 23/25 (92%) | 0.8867 | [60.9%, 91.1%] | 0.333 / 0.611 | tested: 24/25 sanity checks pass |
| 4 switches | 25 | 3 | LSTM | 18/25 (72%) | 21/25 (84%) | 0.8333 | [52.4%, 85.7%] | 0.333 / 0.611 | tested: 23/25 sanity checks pass |
| 4 switches | 25 | 3 | GCN+LSTM | 23/25 (92%) | 23/25 (92%) | 0.9467 | [75.0%, 97.8%] | 0.333 / 0.611 | tested: 22/25 sanity checks pass |
| 8 switches | 24 | 7 | Random Forest | 20/24 (83%) | 23/24 (96%) | 0.9097 | [64.1%, 93.3%] | 0.143 / 0.370 | tested: 23/24 sanity checks pass |
| 8 switches | 24 | 7 | Topology ranker | 1/24 (4%) | 11/24 (46%) | 0.4122 | [0.7%, 20.2%] | 0.143 / 0.370 | tested: 24/24 sanity checks pass |
| 8 switches | 24 | 7 | GCN | 23/24 (96%) | 23/24 (96%) | 0.9722 | [79.8%, 99.3%] | 0.143 / 0.370 | tested: 22/24 sanity checks pass |
| 8 switches | 24 | 7 | LSTM | 22/24 (92%) | 23/24 (96%) | 0.9514 | [74.2%, 97.7%] | 0.143 / 0.370 | tested: 23/24 sanity checks pass |
| 8 switches | 24 | 7 | GCN+LSTM | 22/24 (92%) | 22/24 (92%) | 0.9333 | [74.2%, 97.7%] | 0.143 / 0.370 | tested: 23/24 sanity checks pass |
| 12 switches | 26 | 11 | Random Forest | 19/26 (73%) | 21/26 (81%) | 0.8237 | [53.9%, 86.3%] | 0.091 / 0.275 | tested: 26/26 sanity checks pass |
| 12 switches | 26 | 11 | Topology ranker | 1/26 (4%) | 2/26 (8%) | 0.1998 | [0.7%, 18.9%] | 0.091 / 0.275 | tested: 26/26 sanity checks pass |
| 12 switches | 26 | 11 | GCN | 25/26 (96%) | 26/26 (100%) | 0.9808 | [81.1%, 99.3%] | 0.091 / 0.275 | tested: 24/26 sanity checks pass |
| 12 switches | 26 | 11 | LSTM | 22/26 (85%) | 23/26 (88%) | 0.8955 | [66.5%, 93.8%] | 0.091 / 0.275 | tested: 25/26 sanity checks pass |
| 12 switches | 26 | 11 | GCN+LSTM | 20/26 (77%) | 23/26 (88%) | 0.8494 | [57.9%, 89.0%] | 0.091 / 0.275 | tested: 25/26 sanity checks pass |
