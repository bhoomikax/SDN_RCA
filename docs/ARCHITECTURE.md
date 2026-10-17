# Architecture and data flow

## Components

1. **Emulated network:** Mininet creates hosts, switches, and links; Open vSwitch exposes per-port counters. Ryu manages the SDN control plane.
2. **Collection:** `telemetry.py` requests/reads switch port statistics and writes rows through `telemetry_pipeline.py`. The schema includes timestamp, switch, port, packet/byte/drop counters, derived rates/throughput, experiment ID, phase, fault type, and fault location.
3. **Experiment orchestration:** `experiment_runner.py` and `experiment_runner_batch.py` are the earlier experiment entry points. `experiment_runner_recollection.py` captures isolated per-run telemetry, phase events, iperf logs/process outcomes, runtime port mappings, metadata, and cleanup state. Run directories are unique by physical and logical ID. The 6 Mbps profile was exercised in a single engineering pilot, not a repeatability cohort; its evidence audit is separate and it is excluded from v3.
4. **Dataset validation:** `build_validated_candidate.py` joins only explicitly admitted evidence, validates schema, timestamps, IDs, duplicate keys, mapping, phase coverage, process records, and hashes, then writes a separate candidate and provenance/exclusion records. It does not replace `master_dataset.csv`.
5. **RCA:** `evaluate_topology_link_rca.py` derives training-normal port baselines, scores anomalous port measurements, aggregates switch/link evidence, and compares RF and a topology-aware ranker. `evaluate_online_fault_detection.py` is a separate causal timestamp-level anomaly baseline; it is unsuccessful (0/25 fault windows detected) and does not localize links.
6. **Graph/temporal evaluation:** `evaluate_graph_temporal_link_rca.py` provides graph-only, temporal-only, and combined neural localization; `evaluate_graph_temporal_grouped_loeo.py` applies experiment-grouped folds with training-only normalization/feature policy and same-fold RF/topology baselines. This remains conditional localization because the annotated fault phase selects the model window. See current v3 results for its empirical status.

## Provenance boundary

Physical run IDs identify a specific collection execution; logical experiment IDs identify the intended scenario/class. Physical 21 maps to logical 10 and physical 23 maps to logical 3. This does not retroactively make the historical recordings for logical 10 or 3 valid: the physical runs are new evidence admitted as new rows after independent validation. Physical 22 remains provisional.

## Evaluation boundary

Current localization evaluators use the annotated `phase == fault` window to choose data, then compare predicted link rankings to the fault link. This is conditional localization with oracle phase information. An online system would need to detect an anomaly causally from data available up to the current time, then localize without phase labels, event timestamps, recovery samples, or future observations. That system is not validated here.

The pilot raw evidence is held outside the v3 data flow. Its whole-run iperf receiver loss combines baseline, intentional outage, and recovery, so no baseline-only loss claim can be derived. A future low-load cohort requires a separate normal-only runner path, one-second receiver intervals, preflighted unique identifiers, and its own versioned storage; the design is in `TRAFFIC_PROFILE_REPEATABILITY_PROTOCOL.md`.
