# SDN RCA recollection and evaluation protocol

## Scope and safeguards

The historical files for logical experiments 3 and 10 remain invalid as paired telemetry/phase records. Do not repair them in place. The existing `master_dataset.csv`, historical `experiments/` files, checkpoints, and result CSVs are immutable inputs.

The opt-in runner is `experiment_runner_recollection.py` in `/home/mininet/sdn_project`. Its default mode is read-only preflight. It writes only beneath `recollection_runs/`, refuses occupied output paths, and marks interrupted, incomplete, or invalid runs `FAILED_INVALID`. It never merges output into the historical experiment directory.

## Logical to physical run mapping

| Logical experiment | New physical run | Intended fault link | Existing role in audited split |
|---:|---:|---|---|
| 3 | 23 (reserved after physical 22 was found provisional) | s3-s4 | Training |
| 10 | 21 | s2-s3 | Held-out test |
| 26 | 30 | s2-s3 | Traffic-profile pilot only; never admit as a v3 experiment |

The intended links preserve the current dataset annotations and split roles. The new metadata records logical and physical IDs separately; the collector's `experiment_id` is the physical ID. This is a new recording, not recovered historical telemetry. The mapping is also written in each run's `run_metadata.json` and phase event rows. Runtime truth for the injected interface is resolved from Mininet's live links and checked against `ovs-ofctl show` output. The runner uses observed OpenFlow port numbers (not fixed port assumptions), requires complete switch-interface coverage, rejects duplicate or contradictory mappings, and checks both target interfaces against reciprocal runtime mapping rows before starting collection or fault injection. It records both the full mapping and the validated target rows. Logical 26 / physical 30 is reserved solely for the new traffic-profile pilot.

Physical 20 for logical 3 failed timestamp coverage and must never be reused. Physical 22 for logical 3 has `COMPLETE` in its original metadata, but its iperf client/server completion and transfer duration are unproven; its forensic disposition is `PROVISIONAL` and it is excluded from primary evaluation. Its six raw artifacts remain preserved under `/home/mininet/sdn_project/recollection_runs/physical_22_logical_3/`. Physical 23 and 21 have already been used for the valid recollections mapped to logical 3 and 10; all v3 data remains frozen. Before any future run, require a fresh read-only preflight and stop if a safety check fails.

## Future traffic-profile pilot (not run)

The local runner requires `traffic_profiles/udp_6mbps_v1.json`: UDP offered load 6 Mbps on the configured 10 Mbps s2-s3 bottleneck (60% of capacity, below the 70% ceiling), iperf2 default payload sizing, and 20 seconds per normal/fault/recovery phase. The runner validates the configured topology/capacity, requires iperf2, records the profile hash and parsed sender/receiver final rates, and rejects phase durations that differ from the frozen profile. The profile and runner edits have passed local Windows tests, but have not been copied to or executed on the VM. The SSH attempt to `mininet@127.0.0.1:2222` was denied (`Permission denied (publickey,password)`); do not claim a pilot or collect v4 until authorized VM access is restored and a new preflight succeeds.

Once access is restored and the runner/profile are deployed and hash-verified, the preflight is read-only:

```bash
cd /home/mininet/sdn_project
sudo -n python3 experiment_runner_recollection.py --logical-id 26 --physical-id 30
```

Preflight checks the reserved logical/physical pair, profile/topology consistency, output and historical path availability, required source files, conflicting OVS switch names, iperf2 version, and the Ryu endpoint at `127.0.0.1:6633`. Resolve any failure before proceeding. Confirm no existing Mininet experiment is active and that the controller is healthy. The normal Ryu process may stay running; do not restart it.

Only after fresh preflight succeeds, run the isolated pilot:

```bash
sudo -n python3 experiment_runner_recollection.py --logical-id 26 --physical-id 30 --run
```

Review the pilot's status, phase timestamps, telemetry span, row IDs, runtime mapping, process exit codes, final sender/receiver summaries, and observed normal-phase rates. The configured 6 Mbps is only the offered load; it is not a measured delivered rate. On failure, preserve the run directory as `FAILED_INVALID`; do not retry into it or relabel it as complete. A later attempt needs a new physical ID and an explicit mapping approved before use. Never merge the pilot into v3; only consider a new, separately versioned dataset after the traffic profile has been validated and frozen.

The runner builds the same five-link topology, runs the existing collector for the requested phase durations plus five seconds, and captures timestamps after the normal, link-down, and link-up actions. It now waits up to 15 seconds for a parseable, schema-valid, correctly identified telemetry sample before recording `normal`. Before setting `COMPLETE`, it validates every sample timestamp and requires `first_sample <= normal < fault < recovery <= last_sample`. Missing or malformed timestamps fail closed. A success directory contains `telemetry.csv`, `phase_events.csv`, `runtime_port_mapping.csv`, `run_metadata.json`, and run-local iperf logs. These files are new evidence and are not automatically merged.

The original runner uses fixed module constants, writes to `experiments/`, does not distinguish logical from physical IDs, and records no runtime mapping. Do not use it for these recollections.

## Dataset admission after recollection

Before any model run, validate the two new run directories and the current 17-run candidate together:

1. Require one unique physical run per logical ID and a one-to-one mapping: `3 -> 23`, `10 -> 21`.
2. Require `COMPLETE`, valid telemetry schema, finite measurements, non-empty rows, unique `(physical_run_id, timestamp, switch, port)`, physical ID consistency, ordered phase events, and all three events inside the actual telemetry sample range.
3. Require all expected switch/port mappings to be present, and verify the two ends of the configured fault link against the runtime mapping file.
4. Ensure logical fault labels match the predeclared intended links. If they do not, stop and resolve the experimental protocol; do not relabel after seeing model scores.
5. Build a **new** candidate file and provenance manifest. Never overwrite `master_dataset.csv` or merge outputs.
6. Check that 19 logical experiments are present exactly once and no telemetry recordings are byte-identical duplicates. This recovers the logical 13-train/6-test roles while evaluating new physical recordings for logical 3 and 10.

## Evaluation protocol

### Fixed split and fair comparison

Treat the physical run as the independent observation and the logical ID as the predeclared split role. Use the established training logical IDs `{1,2,3,4,5,6,7,8,9,13,14,17,19}` and held-out logical IDs `{10,11,12,15,16,18}`. For a future validated reconstruction, logical 3 is assigned physical 23 and logical 10 physical 21. Exclude provisional physical 22. Assert no physical recording appears in both sets, every logical ID occurs once, and all three link classes occur in both groups. Do not move runs or tune parameters against held-out labels.

Fit RF and topology-aware normal baselines, feature scaling, and any anomaly threshold on training-normal samples only. Keep existing RF and topology ranking weights fixed for the first comparison. Evaluate both methods on the same six logical test experiments, report Top-1/Top-2/Top-3, per-class metrics, per-experiment rankings, and the exact physical recording IDs. Save to a new results filename.

### Conditional fault localization (oracle-assisted)

This answers: *given a known fault event and its event window, which link is the cause?* The exact `fault` event timestamp may define the first ten seconds after injection, but this use of the phase annotation must be disclosed as oracle-assisted. Exclude recovery samples. Do not call this online detection or end-to-end online RCA. It is comparable to prior conditional-localization results only if the feature/window definitions and split are otherwise held fixed; the changed event-time labels should be reported as a new evaluation version.

### Online detection and localization

This answers: *from telemetry available at time t, can a fault be detected and then localized without knowing the event time?*

- Construct causal rolling windows from telemetry ordered by timestamp. A prediction at time `t` may use observations at or before `t` only.
- Never use `phase`, `fault_type`, `fault_location`, logical/physical IDs, or event timestamps as predictor columns. Use phase/event records only after predictions are frozen to generate offline target labels and metrics.
- Do not select the test window's start from its fault label/event timestamp. Begin at a predeclared telemetry-relative time or evaluate the full causal stream.
- Train a detection stage with normal versus fault targets and a localization stage for link identity. Evaluate detection delay/false alarms separately from link Top-k accuracy conditional on detected faults.
- Exclude recovery observations from fault-localization features and training windows. If recovery performance is studied, score it as a separate task with a fixed, causal rule.
- Fit all normal baselines and thresholds from training runs only. Use held-out runs once for final results; do not calibrate the threshold or ranking weights on them.

The conditional-localization evaluator selects rows with `phase == "fault"` and starts its ten-second window at the first such timestamp. It therefore implements oracle-assisted localization. Its label fields are excluded from sensor predictor columns, but its window selection is not an online protocol. A separate timestamp-causal detector baseline is implemented in `evaluate_online_fault_detection.py`; it detected 0/25 held-out fault windows and is a failed baseline, not a validated online system. Do not silently reinterpret conditional-localization results as online metrics.

## Current state and stop point

Implemented locally: an explicit-ID runner with read-only preflight by default, isolated output paths, runtime port mapping capture, bounded first-sample waiting, strict phase/sample timestamp coverage validation, failed-run invalidation, a hash-recorded traffic profile, iperf2 checks, and final sender/receiver rate parsing; offline regression tests; and this protocol document.

Physical 20 for logical 3 remains preserved as `FAILED_INVALID`. Physical 22 remains preserved with metadata `COMPLETE`, but is forensically `PROVISIONAL` because iperf completion was not recorded. The loopback-only iperf2 2.0.13 smoke test verifies the parser, not the network pilot. The 6 Mbps profile is local-only and unvalidated on Mininet because SSH authentication is denied. Logical 26 / physical 30 remains pilot-only and must not enter v3. Do not use physical 20 or 22 in primary data. The runner and full Windows suite pass locally; the VM remains untested.
