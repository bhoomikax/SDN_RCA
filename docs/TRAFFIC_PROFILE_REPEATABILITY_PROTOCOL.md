# Prospective 6 Mbps traffic-profile cohort protocol

## Status

This is a prospective design for a future controlled cohort. No cohort runs
have been collected, and the candidate IDs below are not reserved or
verified. Run a read-only VM inventory and ID preflight immediately before
allocation. Do not include any cohort artifacts in frozen v3.

The available runner does not currently support normal-only controls and the
VM currently rejects SSH with `Permission denied (publickey,password)`. Extend
and test the runner before collection; do not infer that a control is valid
from the fault/recovery runner's status alone.

## Fixed design

Use the existing 6 Mbps traffic settings unchanged (6 Mbps UDP, iperf2
default payload) and keep deliberate overload out of this cohort. A
normal-only control is a continuous 60-second sender with no injected fault;
fault/recovery trials use the profile's 20/20/20-second sequence. Collect
three independent normal-only controls and three
independent fault/recovery repetitions at each of the three existing link
locations. Each fault/recovery trial uses 20 seconds normal, 20 seconds
controlled outage, and 20 seconds recovery while the same sender runs
continuously. Collect one-second receiver intervals so packet delivery in
each phase can be measured separately.

| Logical ID (candidate) | Physical ID (candidate) | Condition |
|---|---:|---|
| 28 | 32 | Normal-only control 1 |
| 29 | 33 | Normal-only control 2 |
| 30 | 34 | Normal-only control 3 |
| 31 | 35 | Fault/recovery: s1-s2 |
| 32 | 36 | Fault/recovery: s1-s2 |
| 33 | 37 | Fault/recovery: s1-s2 |
| 34 | 38 | Fault/recovery: s2-s3 |
| 35 | 39 | Fault/recovery: s2-s3 |
| 36 | 40 | Fault/recovery: s2-s3 |
| 37 | 41 | Fault/recovery: s3-s4 |
| 38 | 42 | Fault/recovery: s3-s4 |
| 39 | 43 | Fault/recovery: s3-s4 |

IDs 28-39 / 32-43 are proposed placeholders only. Confirm they are unused in
both the VM and all local/persisted experiment indexes before assignment. If
any is occupied, select another non-overlapping range and record the
preflight evidence before running. Store this cohort in a new versioned
directory; preserve every attempt, including failed and excluded attempts.

Randomize run order within the constraints of clean startup/teardown, and
record the generated order before execution. The runner change must align
phase markers to actual sender start/end on the VM (or record a monotonic
sender-active interval); do not label setup delay as active normal traffic.
Restart or verify clean Mininet,
OVS, controller, and iperf state for every run. Persist sender/receiver
one-second reports, experiment event times, runtime port mapping, profile
hash, telemetry, process/bridge snapshots before and after, runner revision,
and host clock synchronization status. No claim requiring cross-machine clock
alignment is allowed unless synchronization is independently verified.

## Acceptance criteria (freeze before collecting)

An attempt is technically valid only if its unique IDs and profile hash match
the preflight record; the expected topology and runtime mapping are verified;
the sender covers the full intended active period; one-second receiver
intervals, telemetry, phase markers, and cleanup evidence are present; and
there are no unexplained missing or duplicate telemetry keys. Keep invalid
attempts with their original status and evidence.

The cohort supports a *stable low-load profile* claim only if all three
normal-only controls and all nine fault/recovery attempts are technically
valid, each control's mean receiver goodput is 5.4-6.6 Mbps, each control's
sequence-accounted packet loss is at most 1%, and the coefficient of
variation of the three control mean goodput values is at most 10%.

For each fault/recovery attempt, calculate delivery separately from the
one-second receiver intervals and sender sequence ranges. First verify on a
safe test that the iperf2 interval format can attribute missing UDP sequence
ranges to the intended phase; a gap during the outage may otherwise be
reported only when the receiver sees the next packet after recovery. If that
format cannot allocate losses to phase reliably, add same-host packet capture
or an equivalent sequence-aware measure before cohort collection. The
pre-outage normal period must have at most
1% sequence-accounted loss; the 20-second outage must have at least 90% loss;
and the last 10 seconds of recovery must achieve at least 90% of the median
normal-control receiver goodput with at most 1% loss. If the receiver's
interval format cannot assign sequence loss to these windows reliably, mark
the corresponding phase criterion unmeasurable and do not claim it passed.

Report every attempt and per-run values, not only cohort averages. If any
criterion fails, preserve the result and report the cohort as not meeting the
criterion; do not change thresholds after inspecting outcomes and then
describe the same runs as confirmatory. These criteria concern traffic and
telemetry reliability only; they do not validate an RCA model or causal claim.

## Required implementation and preflight before execution

1. Add a separately tested normal-only acquisition path and unique ID mapping.
   It must produce status, event, telemetry, and cleanup records without
   fabricating fault or recovery phases.
2. Add and test one-second iperf receiver interval collection and a parser
   that assigns sequence-loss counts to the correct phase windows.
3. Verify runner cleanup and artifact completeness on a disposable/safe test
   run before assigning cohort IDs.
4. On the VM, read-only inspect used logical/physical IDs, active processes,
   OVS bridges, controller, and clock synchronization; save this preflight
   before reserving candidate IDs.
5. Freeze and hash this protocol and the runner revision before the first
   cohort observation. Any post-observation protocol change creates a new,
   explicitly exploratory cohort version.

The prior pilot is not a control and must not be used to satisfy any of these
acceptance criteria. The current infrastructure blocker prevents execution;
do not create synthetic or simulated cohort records as substitutes.
