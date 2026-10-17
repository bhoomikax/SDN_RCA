# 6 Mbps traffic-profile pilot protocol

## Scope and status

This is a bounded engineering pilot, not a v4 cohort or a model-evaluation experiment. It uses the existing H1–S1–S2–S3–S4–H2 topology and deliberately injects an s2–s3 link failure. All resulting data stays separate from v3.

The profile was frozen before pilot run 30 at `traffic_profiles/udp_6mbps_v1.json` (SHA-256 `35ddddc9b6a8903c5bfcdd4f58fdeba4de2b353ad9bf239e2f81db59aa42b384`). It offers 6 Mbps UDP against the configured 10 Mbps s2–s3 link, uses iperf2 default payload size, and runs 20-second normal, fault, and recovery phases. The offered rate is 60% of nominal link capacity; it is not itself evidence of delivered throughput.

Run 30 (logical 26 / physical 30) was the first deployment attempt. It is retained as `FAILED_INVALID`, not admitted, because the runner's 15-second wait expired before iperf2 server exit was observed. Its client and server logs both report 10,999/32,099 lost. The runner exit grace was extended in a subsequent code revision. The repeat (logical 27 / physical 31) used the same frozen profile and a distinct output path; it passed the runner's engineering checks below. An independent post-run audit refined the phase-rate calculations and identified evidence limits, documented in `TRAFFIC_PROFILE_PILOT_AUDIT.md`.

This repeat criterion was defined after inspecting failed run 30; it is a pilot validation rule, not a preregistered confirmatory study.

## Repeat acceptance checks

Admit the pilot as a successful profile check only if all checks pass:

1. Runner metadata reports `COMPLETE`; client and server exit normally; final iperf summaries agree on receiver totals and observed duration is within the runner's 2-second tolerance of 60 seconds.
2. All telemetry records use physical ID 31, have the expected schema and finite numeric values, have unique timestamp/switch/port keys, cover all four switches, and bracket ordered normal/fault/recovery events.
3. The runtime mapping independently resolves s2 port `s2-eth2` to s3 port `s3-eth1` and matches the injected link.
4. The whole-run client sender rate is within 10% of the configured 6 Mbps offered rate. This is a sender-side consistency check, not a delivered-rate claim.
5. For numbered ports at the 10 Mbps link, normal and recovery mean TX throughput remain below 9 Mbps; recovery differs from normal by no more than 25%; and fault-phase s3 ingress throughput is at most 20% of the mean normal/recovery s3 ingress throughput.
6. Preserve all raw files and hashes. Any failed check leaves the run excluded; do not rerun into physical ID 31 or change its status.

The 20-second link outage is intentional. Whole-run packet loss therefore includes packets sent while the link is down and is not a baseline-loss acceptance metric. Report phase-specific interface telemetry separately from the full-run iperf summary.

## Observed repeat outcome

Run 31 metadata reports `COMPLETE`; the client and server both exited 0. It produced 672 telemetry rows across four switches and 12 switch/port combinations, with unique keys, finite measurements, covered ordered events, and the expected reciprocal runtime mapping s2-eth2/ofport 2 ↔ s3-eth1/ofport 1. The sender ran for 60.0 seconds and reported 6.29 Mbps, 4.8% above the 6 Mbps offered setting. Declared event-window durations were 22.101 s normal, 20.086 s fault, and 20.086 s recovery; the normal event preceded sender start by about 2.019 s. Within the sender-active overlap, mean s2-eth2 TX / s3-eth1 RX telemetry was 7.238 / 7.251 Mbps normal, 0.361 / 0.349 Mbps fault, and 7.363 / 7.376 Mbps recovery. These are counter-derived throughput summaries, not packet delivery.

The full-run receiver summary reports 4.22 Mbps and 10,900 lost of 32,100 sequence-accounted datagrams (34.0%). This aggregate includes the deliberate outage and must not be interpreted as normal-path loss. No interval receiver reports were preserved, so baseline packet loss cannot be separated from the outage. The run metadata indicates `COMPLETE` without a cleanup failure, but the artifact package contains no independent post-run OVS/process snapshot; cleanup is therefore not independently verified. The evidence directories are `pilot_evidence_20261017_physical30_logical26/` (failed first attempt) and `pilot_evidence_20261017_physical31_logical27/` (completed repeat); `PILOT_EVIDENCE_SHA256SUMS.txt` records SHA-256 hashes for every retained artifact.

## Clock limitation

During the first attempt, the VM clock reported 2026-10-15 while the Windows session date was 2026-10-17, and `timedatectl` reported `NTPSynchronized=no`. The telemetry and phase timestamps are generated on the same VM and preserve within-run ordering, but absolute cross-machine wall-clock alignment is not established. Do not infer sub-second synchronization to Windows or external clocks. Correcting system time is outside this pilot and must be done through the VM's approved time-synchronization procedure, not by editing recorded timestamps.

## Interpretation boundary

Passing these checks supports only that the isolated low-load profile ran to completion and that telemetry changed during and after the injected link outage in this single testbed. The checks were specified after examining the failed first attempt and are an engineering repeat rule, not a preregistered confirmatory study. This does not establish repeatability, distinguish congestion from ordinary variance, validate an overload profile, support v4 dataset admission, or demonstrate root-cause model performance. The follow-on controlled cohort and frozen acceptance criteria are described separately in `TRAFFIC_PROFILE_REPEATABILITY_PROTOCOL.md`.
