# Experiment protocol and safety

## Evidence classes

Every run is classified as valid, invalid, or provisional based on original evidence. A `COMPLETE` metadata field alone is insufficient if process completion, phase coverage, telemetry, or target mapping cannot be independently verified. Preserve raw files; write derived datasets to new paths.

## Recollection runner

`experiment_runner_recollection.py` requires distinct physical and logical identifiers, a fresh run directory, controller/topology preflight, runtime switch-port mapping, and target-link/interface/peer consistency before fault injection. It waits for a valid first telemetry sample before normal-phase timing. Phase events are checked against actual first/last valid sample timestamps. Bounded process waits and cleanup retain logs and mark failures `FAILED_INVALID`. Iperf completion requires both process outcomes and valid summaries/durations under the selected iperf2 mode.

The locally prepared `traffic_profiles/udp_6mbps_v1.json` limits UDP offered load to 6 Mbps on the configured 10 Mbps s2-s3 bottleneck and fixes normal/fault/recovery phases at 20 seconds each. The runner checks the offered-load ceiling, requires iperf2, records the profile hash and final sender/receiver rates, and rejects runtime phase durations that differ from the profile. Logical 26 / physical 30 is reserved for this pilot only. These changes passed local tests but have not been deployed to the Mininet VM; SSH authentication is currently denied. No pilot has run, and the configured load is not evidence of measured delivery.

## Pre-run safety checklist

1. Confirm an unused physical ID and absent run/output paths.
2. Verify runner/test hashes match the reviewed code and run the offline suite.
3. Inspect controller, Mininet, OVS and traffic-process state read-only; do not disrupt unrelated state.
4. Confirm topology and runtime port mapping for the intended target.
5. Confirm collector schema/output path, available storage, requested durations and timeout bounds.
6. Record physical/logical IDs, configuration, fault type, target, clock context and actual event timestamps.
7. Run one bounded experiment only when explicitly authorized; preserve all artifacts even on failure.

## Post-run validation

Require process logs and exit outcomes; valid summaries and observed duration; ordered normal/fault/recovery timestamps covered by the actual telemetry first/last sample; expected schema and switch coverage; finite numeric values; duplicate-key checks; runtime target mapping consistency; cleanup outcome; and hashes for immutable raw artifacts. Failed or unexplained runs remain excluded.

## Current status

Runs 23 and 21 completed and their evidence is represented in v3; run 21's original status remains `FAILED_INVALID` while its preserved evidence was separately re-audited. Run 22 remains provisional. Physical 30 has not been used. The latest local Windows suite passes 69 tests, including 39 runner tests; the VM is not reachable with the available SSH credentials, so the updated runner/profile remain untested there. No automatic merge into the historical master dataset is permitted.
