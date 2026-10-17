# Model cards

These models address conditional link localization from telemetry in an annotated fault window. The phase annotation selects that window; none is an online detector. The v3 grouped LOEO artifact package evaluates RF, topology ranking, and three neural paths on identical 25 experiment-held-out folds. All reported neural metrics remain exploratory; the small number of independent experiments and single topology do not support a superiority claim.

## Random Forest link classifier

- **Input:** switch-level aggregates of four active telemetry metrics (`rx_packet_rate`, `tx_packet_rate`, `rx_throughput_mbps`, `tx_throughput_mbps`) and train-fitted baseline deviations/statistics.
- **Target:** one of three faulty links.
- **Fit policy:** experiment-level LOEO; RF, active features, means/standard deviations and feature choices use training runs only. Test labels are joined after rankings for metrics.
- **v3 result:** 20/25 Top-1 (80%), 22/25 Top-2 (88%); class support s1-s2 8, s2-s3 9, s3-s4 8. Top-3 is 100% but nondiscriminative.
- **Use limits:** conditional localization only. TX packet rate and throughput are strongly correlated in training-normal telemetry. Large iperf loss may alter observed features. It is not calibrated for production confidence.

## Fixed topology link ranker

- **Input:** port anomaly scores, endpoint/link aggregation, and fixed topology evidence; training-normal telemetry fits anomaly baselines and threshold separately inside each LOEO fold.
- **Output:** ordered three-link ranking, not a fault probability.
- **v3 result:** 13/25 Top-1 (52%), 22/25 Top-2 (88%). The weak s2-s3 Top-1 recall is 2/9.
- **Use limits:** its temporal/progression components are limited by the available timing and sample density. Runtime port mapping exists for recollections; historical mapping remains inferred. The score is uncalibrated.

## Graph-only GCN, temporal-only LSTM, combined GCN+LSTM

- **Input:** corrected time-varying graph snapshots built by summing all numbered non-LOCAL switch ports; hosts are zero-filled because host telemetry is absent. Four telemetry features; labels are targets only.
- **Window:** first ten seconds of the annotated fault interval. This is oracle-assisted conditional localization.
- **Split:** fixed experiment split, 13 training / 6 test, three initialization seeds. Seed repeats do not increase independent support beyond six.
- **Results:** graph-only mean Top-1/Top-2 5/6 / 5/6; temporal-only 4/6 / 5.67/6; graph-temporal 4/6 / 5.33/6. RF on the same split measured 4/6 / 6/6.
- **Grouped v3 LOEO result:** at `evaluations/graph_temporal_v3_grouped_loeo_verified/`, the mean-score ensemble gives graph-only 20/25 Top-1 and 23/25 Top-2 (MRR 0.8867); temporal-only 18/25 and 21/25 (MRR 0.8333); graph-temporal 23/25 and 23/25 (MRR 0.9467). Same-fold RF is 20/25 and 22/25; topology ranker is 13/25 and 22/25.
- **Fit/evaluation policy:** 25 LOEO folds, 24 train / 1 held out, three fixed initialization seeds, training-only normalization and feature policy. Independent artifact checks validated split membership, predictions, rank metrics, and hashes. The first failed serialization attempt is retained separately and excluded.
- **Use limits:** these are exploratory, oracle-window conditional localization results on 25 independent experiments in one topology. Seed repeats do not add test support. A numerical advantage in this evaluation is not confirmatory evidence of general superiority and does not establish causal propagation or online detection. The earlier fixed 13/6 results above remain a distinct, small exploratory comparison.

## Baselines

Uniform random ranking has expected Top-1 1/3 and Top-2 2/3. A majority-prior ranking on v3 has Top-1 9/25 and Top-2 17/25. These baselines establish that the RF exceeds simple priors on this dataset, but the test set is still small and shares the same controlled topology and traffic profile.

## Online anomaly detector

- **Input:** current timestamp's numbered-port telemetry, scored with means/scales fitted on training-normal rows. The threshold is the 99th percentile of training-normal timestamp maximum anomaly scores. Prediction-time scoring does not read phase labels, fault annotations, or future samples.
- **Evaluation:** 25-fold LOEO; training-phase labels select normal fit rows, while held-out phase annotations are joined afterward only to measure detection and false alarms. The future-invariance test passed.
- **Result:** 0/25 fault windows detected and 6 false-alarm episodes. Correcting the observed-nonfault exposure denominator gives 21.6581 false-alarm episodes per observed nonfault hour. The always-no-alarm comparator also detects 0/25 and has no false alarms, so this detector is not useful at the measured operating point. The old output remains preserved; corrected output is `evaluations/online_fault_detection_v3_exposure_audit/`.
- **Use limits:** the threshold is a fixed exploratory choice, not selected from held-out results. No online detector improvement is claimed.
