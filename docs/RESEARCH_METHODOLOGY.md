# Research methodology

## Objective and questions

The project studies whether telemetry from an SDN topology can localize a failed inter-switch link, and whether explicit topology and temporal/propagation evidence improves localization over a conventional classifier.

- **RQ1:** Can telemetry distinguish the three configured inter-switch fault locations?
- **RQ2:** Does the current topology-aware ranker improve link ranking over RF?
- **RQ3:** Do graph/temporal models provide evidence for link RCA beyond phase classification?

Current measurements answer RQ1 only provisionally and do not support a positive RQ2 claim. The graph/temporal methods now have a grouped v3 LOEO comparison path; interpret its measured results from `RESULTS_BALANCED_V3.md`. Neither phase-classification accuracy nor oracle-window localization establishes online or causal RCA.

## Unit of analysis and labels

The evaluation unit is a logical experiment/scenario, grouped so rows from one experiment never split across train and test. Labels are fault-link strings (`s1-s2`, `s2-s3`, `s3-s4`). These are scenario annotations, not inferred online labels.

## Current protocol

The retained protocols are:

1. **Fixed identity split:** train logical IDs 1–9, 13, 14, 17, 19; test IDs 10, 11, 12, 15, 16, 18. There are two test experiments per link. Physical run 21 supplies new logical-10 evidence and physical 23 new logical-3 evidence. This preserves split membership, not the original dataset version.
2. **Earlier leave-one-logical-experiment-out:** 18 experiments, excluding physical 21 from this specific result; each fold tests one whole experiment and trains on the other 17. This is the `validated_candidate_physical23_loeo` output.
3. **Primary v3 LOEO:** 25 logical experiments; each fold tests one whole experiment and trains on the other 24. RF and topology baselines use training-only feature selection, normal baselines, and ranking within each fold.
4. **Graph/temporal v3 LOEO:** the same 25 held-out experiments and 24-training-experiment folds as the primary comparison. Neural normalization and feature policy are fitted independently using each fold's training experiments. Initialization seeds are repeated fits, not extra independent test experiments. The known annotated fault phase still selects each ten-second input sequence.

In each fold, normal baselines and feature-variation decisions are fitted on training-normal port telemetry only. Fault labels and experiment identifiers are excluded from predictors. The fault phase label selects the first ten seconds of the annotated fault phase for conditional localization; recovery samples are not used. Test labels are joined only for final scoring. Thus these evaluations are not online detection.

## Metrics and comparison

Top-k is whether the true link appears among the first k candidates. Report Top-1, Top-2, per-link precision/recall/F1, mean rank, and mean reciprocal rank where present. Since there are exactly three candidate links, Top-3 is guaranteed if all candidates are ranked and is not discriminative. RF and topology ranker use the same folds and candidate evidence in each comparison. No test-label parameter tuning was performed; topology score components/weights were retained.

## Graph and temporal claims

Runtime topology/port evidence is available for new physical runs 21 and 23-29; historical endpoint mappings remain inferred from the setup because their telemetry lacks per-run runtime maps. The current ranker includes anomaly/onset-related components, but diagnostics found threshold/onset components often nondiscriminative. Existing GCN/GCN+LSTM phase-classification scores are not RCA results. The v3 online q99 detector is unsuccessful (0/25 detections; corrected false-alarm rate 21.6581 per observed nonfault hour) and does not localize links. No online causal propagation claim is established.
