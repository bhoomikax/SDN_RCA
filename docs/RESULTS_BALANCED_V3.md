# Results: balanced recollection candidate v3

All reported primary metrics are from experiment-level conditional link localization. Fault-phase labels select the first 10 seconds of each annotated fault window. They are oracle window selection and are not available to an online detector. No test labels enter feature selection, thresholds, model fitting, or ranking weights.

## Primary evaluation: 25-fold LOEO

Output: `evaluations/balanced_recollection_v3_loeo_release/`. Dataset SHA-256: `b63d04572b7b97b8451be33174c8813d76af53e3f49f40e5e41b682b1e19b29a`. Each fold holds out one logical experiment and trains on the other 24. Per-link support is 8, 9, and 8. Training-normal baselines and active-feature choices are recomputed from each fold's training experiments only.

| Method | Top-1 | Wilson 95% CI | Top-2 | Wilson 95% CI | Top-3 |
|---|---:|---:|---:|---:|---:|
| Random uniform expectation | 8.33/25 (33.3%) | — | 16.67/25 (66.7%) | — | 100% by definition |
| Majority prior (s2–s3 first) | 9/25 (36.0%) | — | 17/25 (68.0%) | — | 100% |
| RF baseline | 20/25 (80.0%) | [60.9%, 91.1%] | 22/25 (88.0%) | [70.0%, 95.8%] | 25/25 |
| Topology link ranker | 13/25 (52.0%) | [33.5%, 70.0%] | 22/25 (88.0%) | [70.0%, 95.8%] | 25/25 |

Top-3 is nondiscriminative because every method returns all three candidates. Per-link Top-1 recall: RF s1–s2 0.750, s2–s3 0.778, s3–s4 0.875; topology ranker s1–s2 0.750, s2–s3 0.222, s3–s4 0.625. RF performed better at Top-1; both methods tied at Top-2. The intervals reflect only 25 independent logical experiments and do not establish broad generalization.

## Fixed 13/6 comparison and graph/temporal models

The v3 rows for IDs 1–19 were compared after sorting and are identical to the prior candidate used by the saved fixed-split outputs. The established split has 13 training IDs and test IDs `[10,11,12,15,16,18]`, two per link. Existing verified RF/topology output (`evaluations/recollected_13_6_split_v4/`) measured RF 4/6 Top-1 and 6/6 Top-2; topology ranker 3/6 Top-1 and 6/6 Top-2.

The corrected graph artifact and neural evaluation (`derived_graphs/candidate_v2_portsum/graph_dataset.json`, `evaluations/graph_temporal_link_localization_v2/`) use the same 13/6 data and selection window. Across three initialization seeds: graph-only mean Top-1 5/6 (83.3%), Top-2 5/6 (83.3%); temporal-only mean Top-1 4/6 (66.7%), Top-2 5.67/6 (94.4%); combined graph-temporal mean Top-1 4/6 (66.7%), Top-2 5.33/6 (88.9%). Seed repeats are not independent experiments. These exploratory results are uncertain (n=6) and do not establish that graph-only is better than RF; the RF still had higher Top-2. The neural results are not v3 LOEO results.

The new full-v3 graph snapshots are in `derived_graphs/balanced_recollection_v3_portsum/graph_dataset.json` (1,413 snapshots, source hash matches v3). No neural model was trained on v3. Existing phase-classification GCN/LSTM accuracy is not a link-localization result.

## Online fault-detection baseline

Output: `evaluations/online_fault_detection_v3_verified/`. In each LOEO fold, feature means/scales and a fixed 99th-percentile threshold are fit from training-normal data only. Each held-out timestamp is scored from that timestamp's telemetry; training phase labels select normal fit rows; held-out phase annotations are joined only after prediction to measure onset and false alarms. The future-invariance unit test passed.

Measured result: 0/25 fault windows detected, 25 missed, 6 false-alarm episodes, event precision/recall/F1 all 0, and 14.14 false-alarm episodes per observed nonfault hour. Median delay is undefined because no event was detected. The detector is a failed simple baseline, not a usable system; its threshold was not tuned against held-out labels.

## RX/TX acquisition-era shift and exploratory ablation

RX counters, rates, and throughput are zero throughout the 17 historical source experiments in v3, while all eight recollections (logical IDs 3, 10, and 20–25) contain nonzero RX measurements. This creates a strong acquisition-era feature-distribution shift. The cause is not established; metrics that depend on RX therefore cannot be assumed comparable across these cohorts.

The same 25-fold LOEO split was rerun as an exploratory feature-direction ablation in `evaluations/v3_sensor_direction_ablation_20261015_2230/`. Full-feature results were RF 80%/88% and topology 52%/88% Top-1/Top-2; TX-only results were RF 80%/88% and topology 36%/64%; RX-only results were RF 20%/60% and topology 36%/72%. TX-only retains RF's headline accuracy, but topology results vary substantially with feature direction. These are sensitivity diagnostics, not independent confirmation or grounds to suppress RX features.

## Invalid attempts retained for audit

`evaluations/balanced_recollection_v3_loeo/` used a wrapper whose imported function had captured the older 18-run default dataset; it is explicitly marked invalid. `balanced_recollection_v3_loeo_final/` had stale 18-fold text in its summary and is superseded by `balanced_recollection_v3_loeo_release/`. Fixed-split reruns against the full 25-ID dataset correctly refused the unsupported split; a later duplicate recomputation was stopped after prolonged CPU use without producing metrics. Existing saved fixed-split results remain applicable because the 1–19 table values are identical to the evaluated prior candidate.

## Interpretation

Results support preliminary conditional localization on a small testbed. The separately evaluated simple online detector did not detect any held-out fault window. The models do not demonstrate calibrated confidence, causal discovery, or a repeatable propagation sequence. The topology ranker is weak on s2-s3 in LOEO. V3 was collected with a 25 Mbps UDP offered load against the configured 10 Mbps s2-s3 link; physical run 28 measured 12.5 Mbps at the sender and 63% sequence-count loss. Oversubscription is a plausible contributor, not a proven sole cause. A separate 6 Mbps traffic profile has since been prepared locally for a pilot, but it was not deployed or used to collect v3 and has not yet been validated on the VM. Across all v3 normal-phase rows, TX packet rate and throughput correlation was Pearson 0.99999953 and Spearman 0.99910814; this descriptive diagnostic was not used for feature selection. The RX acquisition-era shift, only three links, limited independent runs, inferred historical port mappings, redundant TX metrics, and oracle fault-window selection also constrain conclusions.
