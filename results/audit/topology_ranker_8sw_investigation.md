# Why the topology ranker scores 1/24 Top-1 on the 8-switch topology

Source: `results/topology_8_switches/loeo_rf_topology/topology_ranker_components.csv`
and `grouped_evaluation.csv` (24 admitted experiments, 7 candidate links).
The same code reproduces the frozen four-switch release exactly (13/25 Top-1,
50/50 identical rankings), so the behaviour below is the algorithm's, not a
generalization bug.

## Checks performed

| Item | Finding |
|---|---|
| Port mapping | Candidate endpoints come from the recorded runtime OVS mapping, identical across all 24 runs: `s_k` port 2 faces `s_{k+1}` port 1 for every candidate. Correct. |
| Candidate generation | All 7 inter-switch links are scored in every experiment (168 component rows, positions 1-7). Correct. |
| Evidence window | First 10 s of the annotated fault phase; 7-9 snapshots per experiment. As designed. |
| Anomaly threshold | Training-normal 95th percentile of the per-port anomaly score, 2.56-2.58 in every fold. In the fault window the per-port anomaly score is only ~1.1-1.2 on affected ports, because the per-port normal baseline's standard deviation (which includes the zero-rate first sample and ramp-up) is of the same order as the mean rate. **No port crossed the threshold in any of the 24 experiments**, so `pair_onset_seconds` is 999 and `propagation_margin_seconds` is -10 for every candidate: two of the four equal-weight components are constants. |
| Downstream-link logic | When link `s_k-s_{k+1}` goes down, traffic still flows from h1 up to `s_k` and nothing flows beyond it, so the actual link and every downstream link show the same anomaly (actual 1.147, links at/after the fault 1.122, links before it 0.340 on average). The actual link is nevertheless the highest `link_anomaly` in 17/24 experiments (mean rank 1.42 by that component alone). |
| Imbalance component | `endpoint_imbalance` prefers candidates whose two endpoints are equally anomalous. The actual link has a *larger* imbalance (one endpoint still receives traffic) than fully dead downstream links (0.01-0.03 vs 0.001-0.01), so the component ranks the actual link low and cancels the `link_anomaly` advantage. |
| Tie-breaking | Equal-weight rank aggregation produces exact ties (all 7 candidates tied on `rank_score` in 8 experiments); ties break by `link_anomaly`, then `endpoint_mean_anomaly`, then insertion order, as in the original implementation. Ties are recorded in `score_ties`. |

## Conclusion

The heuristic was designed for a three-candidate chain where at most one
link lies downstream of the fault. On a seven-candidate chain its onset and
propagation components never activate (threshold never crossed), and its
imbalance component systematically penalizes the true link. The single hit
(experiment 105) is a seven-way tie resolved by `link_anomaly`. This follows
from the algorithm as frozen in the four-switch study; it was not changed,
because any change that favours "the most upstream anomalous link" would be
tuning to the observed 8-switch outcomes. The component table and the
leave-one-component-out sensitivity in `results/xai/topology_8_switches/`
expose this per experiment.
