# Architecture and data flow

## Components

1. **Emulated network:** Mininet creates hosts, switches, and links; Open vSwitch exposes per-port counters. Ryu manages the SDN control plane.
2. **Collection:** `telemetry.py` requests/reads switch port statistics and writes rows through `telemetry_pipeline.py`. The schema includes timestamp, switch, port, packet/byte/drop counters, derived rates/throughput, experiment ID, phase, fault type, and fault location.
3. **Experiment orchestration:** `experiment_runner.py` and `experiment_runner_batch.py` are the earlier experiment entry points. `experiment_runner_recollection.py` captures isolated per-run telemetry, phase events, iperf logs/process outcomes, runtime port mappings, metadata, and cleanup state. Run directories are unique by physical and logical ID.
4. **Dataset validation:** `build_validated_candidate.py` joins only explicitly admitted evidence, validates schema, timestamps, IDs, duplicate keys, mapping, phase coverage, process records, and hashes, then writes a separate candidate and provenance/exclusion records. It does not replace `master_dataset.csv`.
5. **RCA:** `evaluate_topology_link_rca.py` derives training-normal port baselines, scores anomalous port measurements, aggregates switch/link evidence, and compares RF and a topology-aware ranker. Wrapper scripts direct the unchanged ranking implementation to selected datasets/output directories and record provenance.
6. **Legacy graph models:** GCN and GCN+LSTM scripts/checkpoints represent phase classification experiments. They have not been evaluated as link-localization methods on the validated experiment-grouped protocol.

## Provenance boundary

Physical run IDs identify a specific collection execution; logical experiment IDs identify the intended scenario/class. Physical 21 maps to logical 10 and physical 23 maps to logical 3. This does not retroactively make the historical recordings for logical 10 or 3 valid: the physical runs are new evidence admitted as new rows after independent validation. Physical 22 remains provisional.

## Evaluation boundary

Current localization evaluators use the annotated `phase == fault` window to choose data, then compare predicted link rankings to the fault link. This is conditional localization with oracle phase information. An online system would need to detect an anomaly causally from data available up to the current time, then localize without phase labels, event timestamps, recovery samples, or future observations. That system is not validated here.
