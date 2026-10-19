# 6 Mbps traffic-profile pilot: independent artifact audit

## Classification and scope

Physical run 31 (logical experiment 27) is one engineering pilot. It is not a
repeatability study, a new dataset, or model-validation evidence. Physical run
30 (logical experiment 26) remains `FAILED_INVALID`; its original files are
preserved and excluded. Neither attempt is part of frozen v3.

Run-31 acceptance criteria were recorded after the run-30 outcome was known and
before run 31. They are an exploratory engineering repeat rule, not a
pre-registered confirmatory protocol. The audit script reads both evidence
directories and does not modify them:

```powershell
python audit_traffic_profile_pilot.py
python -m pytest test_audit_traffic_profile_pilot.py
```

The audit verifies the declared file sets and hashes, run/logical IDs and
statuses, traffic-profile hash, CSV schema and numeric fields, unique telemetry
keys, expected switch/port coverage, event/phase alignment, runtime port
mapping, and iperf summaries. For port mapping it checks that the full mapping
CSV agrees with metadata and with the expected reciprocal topology links.
There is no separate OVS command transcript in the preserved package, so this
audit checks recorded mapping consistency rather than rebuilding live OVS
state independently. `PILOT_EVIDENCE_SHA256SUMS.txt` is the preserved
manifest for the original raw evidence.

## Run 31 evidence

- 672 telemetry rows: 56 snapshots across four switches and eight numbered
  switch ports, with expected switch/port coverage and no duplicate
  switch-port-timestamp keys.
- Declared event windows: normal 22.101 s, fault 20.086 s, recovery 21.833 s.
  The sender began about 2.019 s after the normal event was recorded. The
  offered-traffic overlap was 20.082 s normal, 20.086 s fault, and 20.021 s
  recovery; event timestamps must not be treated as sender-active time.
- During the sender-active overlap, mean s2-eth2 TX telemetry was 7.238 Mbps
  normal, 0.361 Mbps fault, and 7.363 Mbps recovery. Mean s3-eth1 RX telemetry
  was 7.251, 0.349, and 7.376 Mbps, respectively. These are telemetry
  throughput summaries, not packet-delivery measurements.
- Iperf's whole-run sender summary was 6.29 Mbps for 60 seconds. Its
  whole-run receiver summary was 4.22 Mbps with 10,900 of 32,100
  sequence-accounted datagrams reported lost (about 34%). These aggregate
  summaries span normal, intentional outage, and recovery. The persisted
  output does not provide interval loss, so baseline loss cannot be separated
  from outage loss.
- The run metadata says `COMPLETE` and reports no cleanup failure. The artifact
  package does not include a post-run bridge/process snapshot; therefore,
  independent cleanup is not established by this package.

## Run 30 exclusion

Run 30 remains `FAILED_INVALID`, with its original 624 telemetry rows and
whole-run iperf evidence intact. The client log says it sent 32,099 datagrams
at 6.29 Mbps for 60 seconds and embeds a receiver report of 4.22 Mbps with
10,999/32,099 lost; the separate server log reports the same receiver totals.
The failure was the original bounded wait expiring before the iperf2 server
exit was observed. As with run 31, there are no persisted interval loss
reports to isolate baseline delivery from intentional-outage loss. Do not
relabel, repair, or pool this attempt with run 31.

## Timing and interpretation limits

The VM was previously observed with `NTPSynchronized=no`; cross-machine clock
alignment is unverified. Interpret event/telemetry alignment only within the
available run artifacts, not as a synchronized multi-host latency measurement.
The earlier VM SSH attempt without explicitly selecting the non-default key
was denied (`Permission denied (publickey,password)`). A later read-only
connection using the existing `mininet_vm_ed25519` key succeeded. It confirmed
the controller is listening and there are no OVS bridges or active Mininet/
iperf processes. It also confirmed `NTPSynchronized=no`. No new physical
execution was launched because all runner-registered ID pairs have already
been used and the prospective cohort still lacks required runner features.

This evidence demonstrates that the runner produced a pilot artifact package
and that telemetry reflected a link outage and recovery. It does not establish
repeatability, baseline packet loss, a validated dataset, detector performance,
or causal root-cause identification.
