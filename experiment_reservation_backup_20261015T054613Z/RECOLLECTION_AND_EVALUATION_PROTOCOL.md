# SDN RCA recollection and evaluation protocol

## Scope and safeguards

The historical files for logical experiments 3 and 10 remain invalid as paired telemetry/phase records. Do not repair them in place. The existing `master_dataset.csv`, historical `experiments/` files, checkpoints, and result CSVs are immutable inputs.

The opt-in runner is `experiment_runner_recollection.py` in `/home/mininet/sdn_project`. Its default mode is read-only preflight. It writes only beneath `recollection_runs/`, refuses occupied output paths, and marks interrupted, incomplete, or invalid runs `FAILED_INVALID`. It never merges output into the historical experiment directory.

## Logical to physical run mapping

| Logical experiment | New physical run | Intended fault link | Existing role in audited split |
|---:|---:|---|---|
| 3 | 22 (proposed; verified absent during the 2026-10-14 read-only audit) | s3-s4 | Training |
| 10 | 21 | s2-s3 | Held-out test |

The intended links preserve the current dataset annotations and split roles. The new metadata records logical and physical IDs separately; the collector's `experiment_id` is the physical ID. This is a new recording, not recovered historical telemetry. The mapping is also written in each run's `run_metadata.json` and phase event rows. Runtime truth for the injected interface is resolved from Mininet's live links and checked against `ovs-ofctl show` output. The runner uses observed OpenFlow port numbers (not fixed port assumptions), requires complete switch-interface coverage, rejects duplicate or contradictory mappings, and checks both target interfaces against reciprocal runtime mapping rows before starting collection or fault injection. It records both the full mapping and the validated target rows.

Physical 20 has been used by a run that failed timestamp coverage validation; its raw output is preserved at `/home/mininet/sdn_project/recollection_runs/physical_20_logical_3/` and its metadata is `FAILED_INVALID`. It must never be reused. During the 2026-10-14 read-only audit, the VM inventory contained no physical-22 run directory, metadata record, or historical `telemetry_22.csv` / `phases_22.csv`; physical 22 is therefore proposed for a new logical-3 recording. The runner reserves `3 -> 22` and keeps `10 -> 21`. Physical 21 remains unrun and blocked until logical 3 has a valid recording. This preparation does not authorize either live run.

## Required operator sequence (not executed)

The preflight commands are safe and do not start Mininet or inject faults:

```bash
cd /home/mininet/sdn_project
sudo -n python3 experiment_runner_recollection.py --logical-id 3 --physical-id 22
sudo -n python3 experiment_runner_recollection.py --logical-id 10 --physical-id 21
```

Preflight checks the reserved logical/physical pair, output and historical path availability, required source files, conflicting OVS switch names, and the Ryu endpoint at `127.0.0.1:6633`. Resolve any failure before proceeding. Confirm no existing Mininet experiment is active and that the controller is healthy. The normal Ryu process may stay running; do not restart it.

Only after explicit authorization to run fault injection, launch one run at a time:

```bash
sudo -n python3 experiment_runner_recollection.py --logical-id 3 --physical-id 22 --run
sudo -n python3 experiment_runner_recollection.py --logical-id 10 --physical-id 21 --run
```

Review each run's status, phase timestamps, telemetry span, row IDs, and runtime mapping before proceeding. Do not start the logical-10 run unless logical 3 has a valid `COMPLETE` recording and the protocol remains authorized. On failure, preserve the run directory as `FAILED_INVALID`; do not retry into it or relabel it as complete. A later attempt needs a new physical ID and an explicit mapping approved before use.

The runner builds the same five-link topology, runs the existing collector for the requested phase durations plus five seconds, and captures timestamps after the normal, link-down, and link-up actions. It now waits up to 15 seconds for a parseable, schema-valid, correctly identified telemetry sample before recording `normal`. Before setting `COMPLETE`, it validates every sample timestamp and requires `first_sample <= normal < fault < recovery <= last_sample`. Missing or malformed timestamps fail closed. A success directory contains `telemetry.csv`, `phase_events.csv`, `runtime_port_mapping.csv`, `run_metadata.json`, and run-local iperf logs. These files are new evidence and are not automatically merged.

The original runner uses fixed module constants, writes to `experiments/`, does not distinguish logical from physical IDs, and records no runtime mapping. Do not use it for these recollections.

## Dataset admission after recollection

Before any model run, validate the two new run directories and the current 17-run candidate together:

1. Require one unique physical run per logical ID and a one-to-one mapping: `3 -> 22`, `10 -> 21`.
2. Require `COMPLETE`, valid telemetry schema, finite measurements, non-empty rows, unique `(physical_run_id, timestamp, switch, port)`, physical ID consistency, ordered phase events, and all three events inside the actual telemetry sample range.
3. Require all expected switch/port mappings to be present, and verify the two ends of the configured fault link against the runtime mapping file.
4. Ensure logical fault labels match the predeclared intended links. If they do not, stop and resolve the experimental protocol; do not relabel after seeing model scores.
5. Build a **new** candidate file and provenance manifest. Never overwrite `master_dataset.csv` or merge outputs.
6. Check that 19 logical experiments are present exactly once and no telemetry recordings are byte-identical duplicates. This recovers the logical 13-train/6-test roles while evaluating new physical recordings for logical 3 and 10.

## Evaluation protocol

### Fixed split and fair comparison

Treat the physical run as the independent observation and the logical ID as the predeclared split role. Use the established training logical IDs `{1,2,3,4,5,6,7,8,9,13,14,17,19}` and held-out logical IDs `{10,11,12,15,16,18}`. For new data, logical 3 uses physical 22 and logical 10 uses physical 21. Assert no physical recording appears in both sets, every logical ID occurs once, and all three link classes occur in both groups. Do not move runs or tune parameters against held-out labels.

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

The current evaluator selects rows with `phase == "fault"` and starts its ten-second window at the first such timestamp. It therefore implements oracle-assisted localization. Its label fields are excluded from sensor predictor columns, but its window selection is not an online protocol. A separate online evaluator is required; do not silently reinterpret existing results as online metrics.

## Current state and stop point

Implemented: an explicit-ID runner with read-only preflight by default, isolated output paths, runtime port mapping capture, bounded first-sample waiting, strict phase/sample timestamp coverage validation, and failed-run invalidation; offline regression tests; and this protocol document.

Physical 20 for logical 3 was run under authorization, but post-run validation found its normal event at `2026-10-14T00:44:02.834921-07:00`, before the first telemetry sample at `2026-10-14T00:44:04.906729`. Its raw artifacts remain preserved and metadata is `FAILED_INVALID`. The updated runner and orchestration tests are verified offline; the live runtime port mapping check has not been validated against a newly created topology. The read-only audit found physical 22 unused and the runner now reserves it for logical 3. Physical 21 has not been run and remains sequentially blocked. No candidate was rebuilt, and no model was trained or evaluated. This protocol update prepares the proposed ID only; live execution still requires separate explicit authorization.
