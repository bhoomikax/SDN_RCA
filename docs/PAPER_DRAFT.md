# Topology-Aware Fault Localization in Software-Defined Networks — Draft

> Research draft for internal review. Results are preliminary; the work does not establish online detection, causal discovery, or topology-method superiority.

## Abstract

We describe a Mininet/Open vSwitch/Ryu testbed and a provenance-aware pipeline for conditional localization of failed inter-switch links from switch-port telemetry. The pipeline validates event timing, process completion, schemas, run identifiers, and runtime port mappings before constructing a separate derived dataset. On the 25-experiment v3 candidate, experiment-level leave-one-experiment-out evaluation gives a Random Forest Top-1/Top-2 accuracy of 20/25 and 22/25; the topology-aware ranker scores 13/25 and 22/25. Both select windows using annotated fault phases, so these results are oracle-assisted conditional localization, not phase-blind online RCA. A separate online detector baseline detects 0/25 held-out fault windows. These results do not show an advantage for the topology ranker or a usable online detector.

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

On v3's 25-fold leave-one-logical-experiment-out evaluation, RF achieved Top-1 20/25 (80%) and Top-2 22/25 (88%); topology ranking achieved Top-1 13/25 (52%) and Top-2 22/25 (88%). Top-3 is 100% because three links are always ranked. Per-class results and output hashes are in `RESULTS_BALANCED_V3.md` and the evaluation provenance files. These small measurements favor RF at Top-1; no improvement claim is justified.

## 8. Ablations and graph/temporal models

An exploratory same-split TX/RX direction ablation is preserved in `evaluations/v3_sensor_direction_ablation_20261015_2230/`: TX-only matches the full-feature RF result (80%/88% Top-1/Top-2), while the topology ranker changes from 52%/88% with all features to 36%/64% TX-only. RX-only results are weaker for RF (20%/60%) and score 36%/72% for the topology ranker. Because all RX fields are zero in the 17 historical experiments but nonzero in all eight recollections, this is an exploratory sensitivity analysis under acquisition-era shift, not confirmation. Diagnostics found that onset components often tied because threshold crossings were absent or simultaneous. Existing GCN/GCN+LSTM checkpoints were evaluated for phase classification, not link localization, so their reported classification scores are omitted from the RCA comparison.

## 9. Threats to validity

Only three links in one topology and 25 logical experiments are represented. Phase annotations provide oracle timing for conditional localization. Some historical endpoint mappings are inferred. RX features are zero for 17 legacy experiments and nonzero for eight recollections; the acquisition cause is unknown. TX rate and throughput are highly correlated in training-normal telemetry. V3 collection used 25 Mbps UDP against a configured 10 Mbps bottleneck and had substantial measured loss. A 6 Mbps profile is prepared locally for a future pilot but is unvalidated because SSH authentication to the Mininet VM is denied. Re-audited physical run 21 retains its original FAILED_INVALID metadata; run 22 remains provisional. These factors restrict interpretation.

## 10. Limitations and conclusion

The current pipeline demonstrates evidence-preserving collection, validation, and conditional link-ranking comparison, but does not demonstrate online causal RCA or topology-aware improvement. Future work should collect balanced repeated trials with runtime mapping and synchronized ground truth, then evaluate a causal streaming detector and localizer without phase or recovery leakage. Only after that should graph-temporal methods and ablations be compared.
