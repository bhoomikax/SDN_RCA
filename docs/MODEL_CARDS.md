# Model cards

These models address conditional link localization from telemetry in an annotated fault window. The phase annotation selects that window; none is an online detector. The 25-fold v3 LOEO comparison evaluates the RF and fixed topology ranker. The graph, temporal, and graph-temporal neural results below are exploratory results on the separate fixed 13/6 split.

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
- **Use limits:** exploratory only, very small held-out set and wide uncertainty. No v3 LOEO neural comparison was run, and these numbers do not show improvement over RF or establish causal propagation.

## Baselines

Uniform random ranking has expected Top-1 1/3 and Top-2 2/3. A majority-prior ranking on v3 has Top-1 9/25 and Top-2 17/25. These baselines establish that the RF exceeds simple priors on this dataset, but the test set is still small and shares the same controlled topology and traffic profile.

## Online anomaly detector

- **Input:** current timestamp's numbered-port telemetry, scored with means/scales fitted on training-normal rows. The threshold is the 99th percentile of training-normal timestamp maximum anomaly scores. Prediction-time scoring does not read phase labels, fault annotations, or future samples.
- **Evaluation:** 25-fold LOEO; training-phase labels select normal fit rows, while held-out phase annotations are joined afterward only to measure detection and false alarms. The future-invariance test passed.
- **Result:** 0/25 fault windows detected, 6 false-alarm episodes, and 14.14 false alarms per observed nonfault hour. This negative baseline does not produce a root-cause link.
- **Use limits:** the threshold is a fixed exploratory choice, not selected from held-out results. No online detector improvement is claimed.
