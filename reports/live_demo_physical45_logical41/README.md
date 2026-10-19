# Isolated live engineering demo — logical 41 / physical 45

**Status:** one valid exploratory live run, carried end to end from raw evidence
through candidate, graph, and held-out RF inference. It is **not** part of frozen
v3, not a repeatability result, and not a model-validation estimate.

## Run identity and outcome

| Item | Value |
|---|---|
| Logical / physical ID | 41 / 45 (`run_purpose: isolated_live_demo_only`) |
| Fault | `link_failure` on `s2-s3`; runtime mapping `s2-eth2/ofport 2 ↔ s3-eth1/ofport 1` |
| Profile | `udp_6mbps_s2s3_10mbps_v1` (SHA-256 `35ddddc9…a42b384`), 20 s normal / 20 s fault / 20 s recovery |
| Runner metadata status | `COMPLETE` |
| iperf | both processes exit 0; sender 60.0 s at 6.29 Mbps; receiver (client Server Report and server log agree) 58.3 s at 4.18 Mbps |
| Receiver sequence accounting | 11,378 / 32,099 datagrams lost (35%) over the **whole run**, including the deliberate outage — not a baseline-loss estimate |
| Telemetry | 636 finite, non-negative rows; 53 timestamps; switches s1–s4; no duplicate timestamp/switch/port keys; all three phase events inside the telemetry window |
| VM clock | `NTPSynchronized=no`; VM timestamps (2026-10-15/16) lag the Windows date. Only within-run ordering is used |

The duration fix (sender duration must be 60 ± 2 s; client-side and server-side
receiver reports must agree within 0.25 s with identical lost/total counts; the
receiver span may be shorter when packets are lost) is regression-tested in
`test_recollection_runner.test_receiver_interval_may_be_shorter_than_sender_duration`.
For this run the receiver span (58.3 s) would also have passed the earlier ±2 s
receiver rule, so the fix did not decide this outcome.

## Commands (Windows, repository root)

The raw evidence was copied read-only from
`/home/mininet/sdn_project/live_demo_20261018_41_45/recollection_runs/physical_45_logical_41/`
(VM originals hash-identical to `live_evidence_physical45_logical41/SHA256SUMS.txt`).
The VM-side command was:

```sh
sudo -n python3 -B experiment_runner_recollection.py --logical-id 41 --physical-id 45 --normal-seconds 20 --fault-seconds 20 --recovery-seconds 20 --run
```

Reproduce the derived artifacts into **new** paths (existing paths are refused):

```powershell
.\venv\Scripts\python.exe build_validated_candidate.py --run-dir live_evidence_physical45_logical41 --output-dir derived_datasets\NEW_LIVE_CANDIDATE
.\venv\Scripts\python.exe build_graph_multi.py --input derived_datasets\NEW_LIVE_CANDIDATE\candidate_dataset.csv --output derived_graphs\NEW_LIVE_GRAPH\graph_dataset.json
.\venv\Scripts\python.exe demo_rca_v3.py --mode fresh-inference --experiment-id 41 --method rf_baseline --dataset derived_datasets\live_demo_physical45_logical41\candidate_dataset.csv
```

Verified on 2026-10-19 in a scratch directory: the candidate CSV
(`bf8e6154…2cb1f0c`) and exclusion report were byte-identical, the provenance
and graph JSON differed only in recorded absolute paths, and the inference JSON
was byte-identical to `fresh_inference_rf_baseline.json`.

## Inputs and outputs

- Raw evidence: `live_evidence_physical45_logical41/` (+ `SHA256SUMS.txt`).
- Candidate: `derived_datasets/live_demo_physical45_logical41/` — the protected
  clean-17 historical candidate (`run22_milestone_20261014T182846Z/inputs/candidate_master_dataset.csv`,
  logical 1–19 minus 3 and 10) plus run 41; 12,240 rows, 18 experiments.
  The builder's default historical base is used, so v3 recollections are not
  inputs. v3 is untouched.
- Graph: `derived_graphs/live_demo_physical45_logical41/graph_dataset.json`, 1,020 snapshots, source hash matches the candidate.
- Inference report: `fresh_inference_rf_baseline.json` in this directory.
- Hashes of all derived files: `SHA256SUMS.txt` in this directory.

## Result

RF refit on the 17 historical experiments only (experiment 41 is held out and
absent from `training_experiment_ids`). The 10-second window starts at the
annotated fault phase.

| Rank | Link | Uncalibrated RF score |
|---|---|---|
| 1 | s2-s3 | 0.823 |
| 2 | s1-s2 | 0.167 |
| 3 | s3-s4 | 0.010 |

Retrospective label: `s2-s3`, so the run is a Top-1 hit. The fault window
shows downstream TX collapse at s2/s3/s4 (≈ −3.7 Mbps vs. training-normal
mean). These are descriptive deltas, not feature attributions.

## Limits

- One run, one link: a demonstration that the live → candidate → graph →
  inference path works, not an accuracy estimate and not repeatability.
- The window is selected by the annotated phase (oracle). This is retrospective
  conditional localization, not online detection and not causal discovery.
- The 17 training experiments have zero RX counters while this run has nonzero
  RX (the same acquisition-era shift documented for v3). The model's active
  metrics are TX-only (`tx_packet_rate;tx_throughput_mbps`), but the shift
  still limits interpretation.
- Physical 45 was the final authorized attempt. No further physical run is
  authorized. Physical 44 / logical 40 remains `FAILED_INVALID`, is preserved
  in `live_evidence_physical44_logical40/`, and is never a model input.
