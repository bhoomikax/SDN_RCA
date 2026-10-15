# Results

All values below are read from saved evaluation outputs and provenance. They are not claims about online fault detection.

## Fixed 13/6 identity split on updated candidate

Output: `evaluations/recollected_13_6_split_v4/topology_link_rca_results.csv`; provenance records dataset and evaluator hashes. Train IDs: `[1,2,3,4,5,6,7,8,9,13,14,17,19]`; test IDs: `[10,11,12,15,16,18]`, two per fault link. The updated candidate incorporates physical runs 21 and 23, so this is not a byte-identical reproduction of the older dataset's scores.

| Method | Top-1 | Top-2 | Top-3 | MRR | Mean rank |
|---|---:|---:|---:|---:|---:|
| RF baseline | 4/6 (66.7%) | 6/6 (100%) | 6/6 (100%) | 0.833 | 1.333 |
| Topology link ranker | 3/6 (50.0%) | 6/6 (100%) | 6/6 (100%) | 0.750 | 1.500 |

Per-class Top-1 F1 (support 2 each): RF s1-s2 0.80, s2-s3 0.667, s3-s4 0.50; topology s1-s2 1.00, s2-s3 0.40, s3-s4 0.00. Top-3 is nondiscriminative because all three candidate links are returned.

## Leave-one-experiment-out on 18 experiments

Output: `evaluations/validated_candidate_physical23_loeo/`. Physical run 21 is excluded from this 18-experiment result. Each fold holds out one entire logical experiment; per class support is six.

| Method | Top-1 | Top-2 | Top-3 |
|---|---:|---:|---:|
| RF baseline | 15/18 (83.3%) | 16/18 (88.9%) | 18/18 (100%) |
| Topology link ranker | 10/18 (55.6%) | 14/18 (77.8%) | 18/18 (100%) |

Topology class-wise Top-1 F1: s1-s2 0.923, s2-s3 0, s3-s4 0.50. RF class-wise Top-1 F1: s1-s2 0.833, s2-s3 0.857, s3-s4 0.80. The ranker fails particularly on s2-s3. RF outperforms topology ranking on aggregate Top-1 in both saved comparisons.

## Interpretation boundaries

Both evaluations use the annotated fault phase to select the first ten seconds of the fault window. Test labels are joined after predictions for scoring; normal baselines are fit on training experiments only. This supports conditional localization only. Existing GCN and GCN+LSTM scores concern phase classification and are not comparable localization results. No evaluated online detector, graph-temporal link-localizer, or ablation establishes that propagation timing improves RCA.
