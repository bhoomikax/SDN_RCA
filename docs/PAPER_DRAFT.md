# Topology-Aware Fault Localization in Software-Defined Networks — Draft

> Research draft for internal review. Results are preliminary; the work does not establish online detection, causal discovery, or topology-method superiority.

## Abstract

We describe a Mininet/Open vSwitch/Ryu testbed and a provenance-aware pipeline for conditional localization of failed inter-switch links from switch-port telemetry. The pipeline validates event timing, process completion, schemas, run identifiers, and runtime port mappings before constructing a separate derived dataset. On the 25-experiment v3 candidate, grouped leave-one-experiment-out evaluation yields RF 20/25 Top-1 and 22/25 Top-2, topology ranking 13/25 and 22/25, graph-only 20/25 and 23/25, temporal-only 18/25 and 21/25, and graph-temporal 23/25 and 23/25. These small neural comparisons are exploratory, not confirmatory evidence of superiority. All localization models use annotated fault phases to select windows, so the task is oracle-assisted conditional localization rather than phase-blind online RCA. A separate online detector detects 0/25 held-out fault windows and produces 21.6581 false-alarm episodes per observed nonfault hour after correcting the exposure denominator; it does not improve on an always-no-alarm comparator.

## 1. Introduction

Software-defined networking centralizes control and exposes topology and telemetry that may support diagnosis. Root-cause analysis must separate an initiating link failure from symptoms propagated to adjacent switches. This project investigates whether topology-aware, temporally informed evidence can improve link localization over a conventional baseline. The current evidence is a small controlled prototype, not a general deployment benchmark.

## 2. Problem formulation

Given a known topology with candidate links `{s1-s2, s2-s3, s3-s4}` and a telemetry segment selected from an annotated fault phase, produce an ordered list of candidate failed links. Current experiments evaluate conditional localization: the fault phase is known to the evaluator. Online detection and localization, where no phase/event oracle is available, are separate future tasks.

## 3. Research questions

RQ1 asks whether the measured telemetry supports localization across the configured link classes. RQ2 asks whether topology-based ranking improves on RF. RQ3 asks whether graph/temporal models improve root-cause localization rather than phase classification. The present results provide preliminary evidence for RQ1, do not support a positive RQ2, and do not answer RQ3.

## 4. Related work

SDN fault localization has been studied through location and time evidence; see the Berkeley report, “What, Where, and When: Software Fault Localization for SDN” ([EECS-2012-178](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2012/EECS-2012-178.html)). Falcon studies differential fault localization in the SDN control plane ([Computer Networks, DOI 10.1016/j.comnet.2019.07.007](https://www.sciencedirect.com/science/article/abs/pii/S1389128619300040)). Graph and causal RCA also appear in microservice systems, including work on neural Granger causal discovery ([AAAI 2024](https://ojs.aaai.org/index.php/AAAI/article/view/27772)); this is adjacent-domain context, not direct evidence for SDN data-plane localization. Bibliographic details should be checked against the final publisher records before submission.

## 5. System and data

The testbed uses a linear host-switch topology with four switches. OVS counters are collected by the telemetry pipeline; a safeguarded runner records phase events, traffic-process evidence, and runtime mappings. Candidate v3 has 16,956 rows and 25 logical experiments. Historical master data remains immutable. Historical logical 3/10 evidence is excluded; physical 20 is invalid and physical 22 provisional. See `DATASET_CARD_BALANCED_V3.md`.

## 6. Methodology

The RF baseline and topology-aware ranker use experiment-grouped splits. Training-normal port telemetry fits normal baselines; constant metrics are removed per training fold. Forbidden identifiers, phase labels, and fault annotations are not predictors. For conditional localization, the annotated fault phase selects the first ten seconds; labels are used after ranking for metrics. The topology ranker uses port anomaly scores, endpoint evidence, onset, and propagation margin with existing equal-weight rank aggregation. Weights were not tuned on test labels.

## 7. Results

On v3's 25-fold leave-one-logical-experiment-out evaluation, RF achieved Top-1 20/25 (80%) and Top-2 22/25 (88%); topology ranking achieved Top-1 13/25 (52%) and Top-2 22/25 (88%). Top-3 is 100% because three links are always ranked. The independently checked grouped graph/temporal evaluation uses the same held-out experiments: mean-score ensembles achieved graph-only 20/25 Top-1 and 23/25 Top-2 (MRR 0.8867), temporal-only 18/25 and 21/25 (MRR 0.8333), and graph-temporal 23/25 and 23/25 (MRR 0.9467); same-fold RF and topology baselines achieved 20/25 and 22/25, and 13/25 and 22/25, respectively. Three-seed score averaging does not increase the 25 independent test cases. These comparisons are exploratory, have broad uncertainty, and do not justify a superiority claim. Full metrics and artifact provenance are in `RESULTS_BALANCED_V3.md`.

## 8. Ablations and graph/temporal models

An exploratory same-split TX/RX direction ablation is preserved in `evaluations/v3_sensor_direction_ablation_20261015_2230/`: TX-only matches the full-feature RF result (80%/88% Top-1/Top-2), while the topology ranker changes from 52%/88% with all features to 36%/64% TX-only. RX-only results are weaker for RF (20%/60%) and score 36%/72% for the topology ranker. Because all RX fields are zero in the 17 historical experiments but nonzero in all eight recollections, this is an exploratory sensitivity analysis under acquisition-era shift, not confirmation. Diagnostics found that onset components often tied because threshold crossings were absent or simultaneous. The completed grouped v3 LOEO package compares graph-only, temporal-only, graph-temporal, RF, and topology rankings on identical experiment-level folds with training-only normalization and feature policy. The first attempt failed during ensemble serialization and is preserved separately; the verified retry is checked against its CSV predictions and summary. These results remain exploratory conditional localization, not phase-blind or causal RCA. Existing GCN/GCN+LSTM phase-classification results are not evidence of link localization.

## 9. Threats to validity

Only three links in one topology and 25 logical experiments are represented. Phase annotations provide oracle timing for conditional localization. Some historical endpoint mappings are inferred. RX features are zero for 17 legacy experiments and nonzero for eight recollections; the acquisition cause is unknown. TX rate and throughput are highly correlated in training-normal telemetry. V3 collection used 25 Mbps UDP against a configured 10 Mbps bottleneck and had substantial measured loss. A separate 6 Mbps profile passed a single engineering pilot at logical 27 / physical 31 after the first attempt (logical 26 / physical 30) failed validation; its criteria were chosen after the first attempt, its whole-run loss cannot isolate baseline delivery, and no independent cleanup snapshot is preserved. Neither run is admitted to v3 or model evaluation, and one pilot does not establish repeatability or generalization. The VM was not NTP-synchronized, precluding cross-machine timing claims. Re-audited physical run 21 retains its original FAILED_INVALID metadata; run 22 remains provisional. These factors restrict interpretation.

## 10. Limitations and conclusion

The current pipeline demonstrates evidence-preserving collection, validation, and conditional link-ranking comparison, but does not demonstrate online causal RCA or topology-aware improvement. Future work should collect balanced repeated trials with runtime mapping and synchronized ground truth, then evaluate a causal streaming detector and localizer without phase or recovery leakage. Only after that should graph-temporal methods and ablations be compared.
