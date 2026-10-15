# Topology Link RCA: Second-Stage Diagnostic

## Scope and method

This review did not change the evaluator, ranking method, thresholds, data, checkpoints, or earlier diagnostic output. Numerical checks read `master_dataset.csv`, reproduce the existing stratified experiment split (13 training, 6 held out), fit the same per-port baseline from training-normal rows, and apply the fixed 95th-percentile threshold. Held-out link labels were not used to select features, calculate telemetry scores, change the threshold, or tune ranking weights. The annotated `phase` field selects the fault window; this is oracle phase information and is discussed below.

The telemetry source was inspected in memory from the user-provided archive `C:\Users\ASUS\Downloads\sdn_telemetry_source.tar.gz`; it was not extracted or modified. The archive contains `telemetry.py`, `experiment_runner.py`, `experiment_runner_batch.py`, `network_metrics.py`, and `merge_experiments.py`.

## 1. TX feature relationship

Training-normal physical-port telemetry contains **1,976 rows** from 13 training experiments: 247 rows for each of the eight switch/port pairs. `LOCAL` rows are excluded, matching the diagnostic's feature path.

| Feature | Meaning from collector formula | Nonmissing | Unique values | Zeros | Min / median / mean / max |
|---|---|---:|---:|---:|---|
| `tx_packet_rate` | packets per second | 1,976 | 267 | 522 | 0 / 1 / 371.1614 / 2,733 |
| `tx_throughput_mbps` | decimal megabits per second | 1,976 | 307 | 522 | 0 / 0.00472 / 4.4837 / 33.058368 |

Neither feature is missing or constant in this training-normal sample. Pearson correlation is **0.99999918** and Spearman correlation is **0.99581913**. Among positive-rate rows Pearson correlation is **0.99999931**. The correlation is not uniform across port groups: it is about 0.955–0.961 on switch port 1 and about 0.9999997 on switch port 2. This cautions against treating the pooled correlation as a universal relationship.

The collector code explains the close relationship. In `telemetry.py`, with `INTERVAL = 1`, it calculates:

```python
tx_packet_rate = max(0, current_tx_packets - previous_tx_packets) / INTERVAL
tx_throughput_mbps = max(0, current_tx_bytes - previous_tx_bytes) * 8 / INTERVAL / 1000000
```

Thus, for a sample, throughput is packet rate multiplied by the mean bytes per packet and by eight bits per byte, with the decimal megabit conversion. This same-counter-delta construction, fixed divisor, and workload packet-size mix account for much of the observed correlation. In 1,872 adjacent training-normal counter transitions, the stored rates matched these formulas exactly for packet rate and to floating-point precision for throughput. The observed median timestamp interval was about 1.064 seconds, while the collector divides by a fixed one-second interval.

The features are still not identical in these data. There are 40 of 266 distinct positive packet-rate values for which multiple throughput values occur; those rate values cover 1,022 positive-rate rows. The implied bytes-per-packet ratio varies (common values include approximately 42, 316, 590, and 1,512 bytes). Throughput therefore carries packet-size / byte-volume information that packet rate alone does not encode. It may add only a small amount of information in this particular pooled sample, but correlation does not establish interchangeability across traffic mixes, ports, or future measurements.

## 2. Anomaly threshold and onset behavior

The existing threshold is the training-normal score 95th percentile: **1.4596229666**. The anomaly score remains the evaluator's mean of absolute standardized deviations over the active TX features; the threshold and scoring method were not changed.

| Scored group | Rows | Scores strictly above threshold | Median | 90th percentile | 95th percentile | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Training-normal physical ports | 1,976 | 58 | 0.739426 | 1.449676 | 1.459623 | 4.332963 |
| All annotated fault-phase physical ports | 2,880 | 0 | 0.813597 | 1.450971 | 1.459623 | 1.459623 |

The fault-phase maximum equals the threshold, but the evaluator uses a strict `>` crossing rule, so equality is not an onset. No scored fault-phase row in the dataset crosses the threshold. The 58 training-normal exceedances are expected from a sample quantile with ties; the empirical exceedance count need not be exactly five percent.

For experiments 10, 15, 16, and 18, the evaluator selects a 10-second window beginning at the first timestamp marked `phase=fault`. Each candidate endpoint has 10 rows in that window. No endpoint or remote switch crosses the threshold, so no crossing timestamp exists. “None” below means no threshold crossing, rather than a missing telemetry row.

| Experiment | Candidate | Endpoint mean anomaly (A, B) | Window max anomaly (A, B) | Endpoint onset (A, B) |
|---:|---|---|---|---|
| 10 | s1-s2 | 1.293161, 0.505201 | 1.345155, 0.813597 | None, none |
| 10 | s2-s3 | 1.042222, 0.510657 | 1.459623, 0.822443 | None, none |
| 10 | s3-s4 | 1.038220, 0.512454 | 1.450971, 0.825524 | None, none |
| 15 | s1-s2 | 0.208495, 0.505201 | 0.224251, 0.813597 | None, none |
| 15 | s2-s3 | 0.961778, 0.510657 | 1.459623, 0.822443 | None, none |
| 15 | s3-s4 | 0.959598, 0.512454 | 1.450971, 0.825524 | None, none |
| 16 | s1-s2 | 0.486379, 0.449405 | 1.391253, 0.813597 | None, none |
| 16 | s2-s3 | 0.653641, 0.454200 | 0.748152, 0.822443 | None, none |
| 16 | s3-s4 | 1.022596, 0.455612 | 1.450971, 0.825524 | None, none |
| 18 | s1-s2 | 0.760281, 0.376566 | 0.794831, 0.813597 | None, none |
| 18 | s2-s3 | 0.752466, 0.380551 | 0.773529, 0.822443 | None, none |
| 18 | s3-s4 | 1.040236, 0.381629 | 1.450971, 0.825524 | None, none |

The endpoint order is the evaluator's inferred mapping: `s1:2`/`s2:1`, `s2:2`/`s3:1`, and `s3:2`/`s4:1`. Every pair onset therefore receives the same no-detection sentinel (999 seconds). Every remote onset receives the no-detection sentinel (11 seconds), making every propagation margin -10 seconds. With three candidates sharing the same pair-onset and propagation values, average-tie ranking assigns rank 2 to both components for every candidate. These equal ranks mean the timing evidence is absent under this threshold; they do not establish simultaneous fault propagation.

### Oracle window and phase-label caveat

The timestamps below are the first merged-dataset timestamps annotated as fault; they are the window anchors used above:

| Experiment | First annotated fault timestamp |
|---:|---|
| 10 | 2026-10-06 10:54:30.389087 |
| 15 | 2026-10-06 11:32:52.134840 |
| 16 | 2026-10-06 11:34:07.081309 |
| 18 | 2026-10-06 11:36:34.671838 |

The archive's `merge_experiments.py` assigns `phase=fault` at elapsed time **20 seconds** and `phase=recovery` at 40 seconds. It reads the phase log's fault location but does not use the phase log's event timestamp to set the phase boundary. In `experiment_runner.py` and `experiment_runner_batch.py`, telemetry starts before a 3-second wait, traffic setup includes a 2-second wait, and the actual link disconnect follows a further 20-second normal period. The source therefore implies the merged 20-second fault boundary may precede the actual disconnect by roughly five seconds. The exact event-to-sample offset for each experiment cannot be verified because the corresponding phase log files are not present here. This is a code-supported timing hypothesis, not a measured per-experiment event timestamp. It may further weaken the first-10-second onset window; separately, the measured scores show no threshold crossing in any annotated fault phase.

## 3. Port-mapping evidence

The archive's experiment runners define this Mininet link order:

1. `h1`–`s1`
2. `s1`–`s2`
3. `s2`–`s3`
4. `s3`–`s4`
5. `s4`–`h2`

Their fault-injection code names the inter-switch interfaces explicitly: `s1-eth2`/`s2-eth1`, `s2-eth2`/`s3-eth1`, and `s3-eth2`/`s4-eth1`. This verifies the intended Mininet interface endpoints from the available source.

The collector runs `ovs-ofctl -O OpenFlow13 dump-ports <switch>`, parses the printed numeric port identifier, and writes that identifier to the CSV `port` field. It does not record an interface name, query or save an `ovs-ofctl show` / port-description crosswalk, or persist runtime `ofport` assignments. The saved `master_dataset.csv` schema includes `switch` and `port`, but no interface-name field; `final_dataset.csv` likewise has `switch` and `port` without an OpenFlow-to-interface crosswalk. The graph dataset records topology edges but does not attach ports to edges.

Therefore, the link-to-Mininet-interface mapping is supported by the runner source, and the numeric port mapping is consistent with sequential Mininet port allocation and observed CSV port numbers, but the numeric OpenFlow-port-to-interface mapping is **not runtime-verified by the available artifacts**. The port-specific endpoint evidence remains inferred.

The archive also reveals a collection/merge path discrepancy: the runner computes an `experiments/telemetry_<id>.csv` filename but does not pass it to the collector; `telemetry.py` writes the fixed name `telemetry_features.csv`. Meanwhile, `merge_experiments.py` expects `experiments/telemetry_<id>.csv`. The available repository contains the merged datasets, not those experiment CSVs, so this source path alone does not reproduce or prove the exact provenance of the checked-in/working datasets. `network_metrics.py` is a separate host-level metric collector and does not provide the switch-port mapping.

## 4. Evidence and limits

**Measured:** TX feature counts, distributions, correlations, counter-formula agreement, training-normal threshold, anomaly-score distributions, and endpoint window scores/crossings above were computed from the available CSVs. The split was reproduced using the established stratified split. No held-out fault-link labels were used to adjust any analysis choice.

**Supported by source, but not live-verified:** collector formulas, Mininet link order, intended fault interfaces, fixed-time phase merge rules, and the approximate phase-boundary offset follow from the supplied source archive. There was no VM access or live Open vSwitch inspection during this diagnostic.

**Unknown:** exact runtime OpenFlow port/interface assignments; actual disconnect timestamps for these four archived runs; whether the present master dataset was produced through an unrecorded copy/rename step that resolves the runner/merger filename mismatch; and whether the feature relationship holds under other traffic mixes.

## Files

Created during this review: `topology_link_rca_second_stage_diagnostic.md` and the Python import cache `__pycache__/diagnose_topology_link_rca.cpython-313.pyc`. No additional numerical-output file was needed. The cache file for the evaluator predates this review. Existing datasets, checkpoints, evaluator code, prior results, and the previous diagnostic CSV were not modified.
