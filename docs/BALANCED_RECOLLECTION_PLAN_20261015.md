# Balanced recollection plan — physical runs 24–29

## Purpose and unit of identity

Add two new physical runs for each candidate fault location without replacing any prior recording. Each receives its own unused logical experiment ID, so no telemetry rows from distinct physical runs share an evaluation group. The physical ID identifies the collection; the logical ID is the new unique experiment group and determines only the configured target link.

## Preregistered assignments

| Physical run | Logical group | Fault | Durations |
|---:|---:|---|---|
| 24 | 20 | link failure s1-s2 | normal/fault/recovery: 20/20/20 s |
| 25 | 21 | link failure s1-s2 | 20/20/20 s |
| 26 | 22 | link failure s2-s3 | 20/20/20 s |
| 27 | 23 | link failure s2-s3 | 20/20/20 s |
| 28 | 24 | link failure s3-s4 | 20/20/20 s |
| 29 | 25 | link failure s3-s4 | 20/20/20 s |

Before the cohort, class counts were 6, 7, and 6 experiments respectively (s1-s2, s2-s3, s3-s4). After the six admitted runs they are 8, 9, and 8. This is a modest balance improvement, not a power justification.

## Preflight and stop rules

Read-only preflight on 2026-10-15 found physical run directories and legacy telemetry/phase filenames 24–29 unused, Ryu reachable at 127.0.0.1:6633, and no Mininet process, iperf process, or OVS bridge. The runner/test suite passed offline before deployment. Verify matching runner/test hashes, each ID/path, Ryu reachability, and empty Mininet/iperf/OVS state before every run. Do not proceed if any check fails. After each run require status COMPLETE, valid first/last telemetry coverage for ordered phase events, runtime reciprocal target mapping, both iperf process exit codes zero, valid final summaries and requested 60-second duration within the runner's 2-second tolerance, at least one sequence-accounted delivered datagram, schema/ID/numeric/duplicate checks, and clean bounded cleanup. A failure preserves artifacts and consumes that physical ID; never rerun into it.

No packet-loss upper bound is imposed because packet loss is an outcome of link failure and must be reported, not selectively used to remove inconvenient runs. Delivery count, duration, and process completion remain explicit admissibility checks.

## Reproducibility and data policy

Collection command per run:

```sh
sudo -n python3 -B experiment_runner_recollection.py --logical-id <LOGICAL> --physical-id <PHYSICAL> --normal-seconds 20 --fault-seconds 20 --recovery-seconds 20 --run
```

After all runs pass independent artifact validation, construct a new candidate by passing physical runs 21, 23, and 24–29 as additional inputs to the fail-closed builder. Preserve the historical master, candidate v2, prior evaluations, and all run artifacts. Evaluate using experiment-level grouped folds; do not mix rows from one logical group across folds. The six-test 13/6 evaluation remains a separate historical-comparison protocol and must not be tuned.

## Status

## Outcome

The six preregistered runs 24–29 were executed sequentially and passed independent artifact validation. Each has COMPLETE runner metadata, ordered phase-event coverage, matching physical/logical IDs, captured reciprocal runtime target mapping, and successful client/server process exit and summary checks. Candidate v3 includes the six runs as distinct logical groups and is described in `DATASET_CARD_BALANCED_V3.md`.

The measured traffic quality is a concern: the v3 runner's client requested `iperf -b 25M`, while the topology configures the s2–s3 bottleneck at 10 Mbps. For example physical run 28 reports a 12.5 Mbps sender rate, 4.58 Mbps receiver rate, and 63% sequence-count loss. This is consistent with oversubscription and is a plausible explanation, not proof of the only cause. The existing six runs are retained without exclusion. A versioned 6 Mbps profile was prepared for pilot-only logical 26 / physical 30. Its deployment and subsequent outcome are recorded in the dated update below.

## Status update — 2026-10-17

The initial isolated pilot (logical 26 / physical 30) was run and remains preserved as `FAILED_INVALID` because the runner's 15-second server-exit wait expired. After increasing the bounded wait to 20 seconds, a separate repeat (logical 27 / physical 31) completed and passed the profile checks. Neither run was admitted to v3 or used for model evaluation. See `docs/TRAFFIC_PROFILE_PILOT_PROTOCOL.md` and `PILOT_EVIDENCE_SHA256SUMS.txt` for the outcomes and preserved artifact hashes. The VM clock was not NTP-synchronized; absolute cross-machine wall-clock alignment remains unverified.
