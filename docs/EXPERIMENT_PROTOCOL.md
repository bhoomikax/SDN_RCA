# Experiment protocol and safety

## Evidence classes

Every run is classified as valid, invalid, or provisional based on original evidence. A `COMPLETE` metadata field alone is insufficient if process completion, phase coverage, telemetry, or target mapping cannot be independently verified. Preserve raw files; write derived datasets to new paths.

## Recollection runner

`experiment_runner_recollection.py` requires distinct physical and logical identifiers, a fresh run directory, controller/topology preflight, runtime switch-port mapping, and target-link/interface/peer consistency before fault injection. It waits for a valid first telemetry sample before normal-phase timing. Phase events are checked against actual first/last valid sample timestamps. Bounded process waits and cleanup retain logs and mark failures `FAILED_INVALID`. Iperf completion requires both process outcomes and valid summaries/durations under the selected iperf2 mode.

The frozen `traffic_profiles/udp_6mbps_v1.json` limits UDP offered load to 6 Mbps on the configured 10 Mbps s2-s3 bottleneck and fixes normal/fault/recovery phases at 20 seconds each. The runner checks the offered-load ceiling, requires iperf2, records the profile hash and final sender/receiver rates, and rejects runtime phase durations that differ from the profile. Logical 26 / physical 30 is preserved as `FAILED_INVALID` after the original 15-second iperf server-exit wait expired. The bounded wait was increased to 20 seconds and the separate logical 27 / physical 31 repeat completed engineering-pilot checks. Its independently recomputed sender-active mean bottleneck rates were 7.238 Mbps TX / 7.251 Mbps RX normal, 0.361 / 0.349 fault, and 7.363 / 7.376 recovery. These telemetry rates are not packet delivery. The iperf receiver summary is whole-run only (4.22 Mbps, 10,900/32,100 sequence-accounted datagrams lost), so baseline loss cannot be separated from intentional outage loss. Run-31 criteria were set after observing run 30; this is exploratory, not preregistered confirmatory evidence. No post-run process/bridge snapshot is in the artifact package, so independent cleanup is not established. Both runs are isolated pilot evidence, excluded from v3 and model evaluation; see `docs/TRAFFIC_PROFILE_PILOT_AUDIT.md` and `docs/TRAFFIC_PROFILE_PILOT_PROTOCOL.md`. The VM clock was observed with `NTPSynchronized=no`; do not make cross-machine alignment claims.

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

Runs 23 and 21 completed and their evidence is represented in v3; run 21's original status remains `FAILED_INVALID` while its preserved evidence was separately re-audited. Run 22 remains provisional. Pilot physical 30 remains `FAILED_INVALID`; physical 31 completed the pilot-only repeat. The latest Windows source suite passed 79 tests, including 40 runner regression tests; exact commands and the Ubuntu access/dependency limitation are recorded in `EXECUTION_LOG.md`. The runner and its 40-test subset were previously verified on VM Python 3.8.5 on the deployed revision, not the latest source. The original Ryu process was left running, and both pilot runs remain outside all datasets and model evaluations. No automatic merge into the historical master dataset is permitted.
