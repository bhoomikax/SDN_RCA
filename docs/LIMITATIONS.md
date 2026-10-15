# Limitations and unresolved work

- The fixed test set contains six experiments (two per link); estimates have substantial uncertainty and are sensitive to individual runs.
- Current task is conditional localization: annotated phase labels and fault-phase start select the window. There is no validated phase-blind online detector/localizer.
- The fixed-split result uses the original ID membership on a revised dataset with new physical evidence; it is not an exact re-run on the historical data.
- The topology ranker trails RF: 3/6 vs 4/6 Top-1 on the updated fixed split, and 10/18 vs 15/18 in the saved LOEO comparison. It has a class-specific failure on s2-s3.
- Top-3 is 100% by construction with three candidates.
- Onset/propagation components often do not discriminate: threshold crossings can be absent or align at the same sample. Annotated fault-phase timing can differ from the real causal onset.
- Historical switch-port-to-link mappings are setup-derived, not runtime verified. New runs 21/23 have captured runtime mappings.
- RX counters/rates/throughput are zero in the 17 historical source experiments but nonzero in all eight recollections. This acquisition-era shift is real in the stored data, but its cause is unknown and limits cross-cohort interpretation of RX-dependent results. Same-split ablation shows RF unchanged by removing RX (80%/88% Top-1/Top-2), while the topology ranker changes from 52%/88% with all features to 36%/64% TX-only; RX-only results are also weak. Treat these as exploratory sensitivity results, not a fix or confirmation.
- TX rate and throughput are nearly perfectly correlated in training-normal telemetry; feature redundancy must be assessed by context and measurement generation.
- Run 23's link-failure trial had roughly 77% UDP sequence loss. Valid process completion is not equivalent to a healthy traffic path.
- Run 21's original run metadata remains FAILED_INVALID; its inclusion in one candidate depends on separate preserved-evidence re-audit and revised iperf2 parser semantics. Do not treat the original metadata status as repaired.
- Run 22 is provisional because trustworthy process exit/final-summary/duration evidence is absent. Run 20 is invalid.
- GCN/GCN+LSTM phase-classification results are not evidence of root-cause localization. No fair graph-only/temporal-only/graph-temporal localization comparison exists.
- Small single-topology controlled experiments do not establish broad SDN generalization or causal propagation.
- A lower-load 6 Mbps UDP profile and pilot-only reservation (logical 26 / physical 30) are prepared locally but not deployed. SSH authentication to the Mininet VM is denied, so there is no pilot result or validation of the new profile.

## Highest-value next research step

Collect a preregistered, balanced set of repetitions across all three link locations with runtime mapping, synchronized event timing, reliable traffic completion and an explicit phase-blind evaluation stream. Then compare online detection and conditional localization separately using experiment-grouped splits. Do not tune against the six existing test experiments.
