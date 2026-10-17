# Dataset card: balanced recollection candidate v3

## Artifact identity

- CSV: `derived_datasets/balanced_recollection_20261015_v3/candidate_dataset.csv`
- SHA-256: `b63d04572b7b97b8451be33174c8813d76af53e3f49f40e5e41b682b1e19b29a`
- Rows: 16,956 across 25 logical experiments, IDs 1–25.
- Phase counts: normal 6,708; fault 5,544; recovery 4,704.
- Fault-phase rows: s1–s2 1,776; s2–s3 2,004; s3–s4 1,764.
- Historical source: the 11,604-row audited 17-experiment candidate, SHA-256 `e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2`.
- Recollection map: physical 23→logical 3; 21→10; 24→20; 25→21; 26→22; 27→23; 28→24; 29→25.
- Machine-readable forensic ledger: `derived_datasets/balanced_recollection_20261015_v3/experiment_admission_ledger_v2.csv`.
- Provenance: `provenance.json`; rejected and historical excluded evidence is recorded in `exclusion_report.csv` and the ledger.

## Admission and data quality

The candidate builder independently validates each added run's schema, physical/logical identity, unique observation keys, numeric fields, timestamp coverage, phase ordering, runtime OVS mapping, process exit status, iperf summary and duration. The original master dataset remains unchanged; its SHA-256 is `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`.

Run 21 retains raw metadata status `FAILED_INVALID`; its separate re-audit status is `VALID`, and the evidence is included with both facts recorded. Run 23 is included despite high UDP loss under the predeclared criterion (traffic delivery must be nonzero; no upper loss cutoff was set): 30,379 sequence-accounted nonlost of 133,746 sent. Added runs 24–29 also show substantial loss; each has client/server exit code 0 and a parseable matching summary, but delivery ranged from 19,651/66,023 to 31,761/133,749 for these runs. This is a major traffic-quality limitation and may affect model features. No runs were selectively removed after observing model scores.

Historical logical IDs 3 and 10 are excluded in their original form and represented by separate physical recollections 23→3 and 21→10. Physical run 20 remains `FAILED_INVALID` and excluded. Physical run 22's raw metadata says `COMPLETE`, but independent process completion evidence is missing; derived status remains `PROVISIONAL / UNVERIFIED`, and it is excluded. The ledger includes remote-measured hashes for preserved runs 20 and 22; physical 20's raw copy is not mirrored into this Windows workspace.

## Scope and limitations

Labels are links (`s1-s2`, `s2-s3`, `s3-s4`). Existing localization evaluation uses annotated fault phase to select the first ten seconds of a known fault window. It is conditional localization, not online detection. Phase-event/telemetry alignment is validated for new recollections, while historical port mappings remain inferred from setup and telemetry. The graph builder excludes LOCAL rows and sums numbered switch ports; host telemetry remains zero-filled because it is not collected. Three links and 25 logical experiments are still a small, controlled testbed. Traffic delivery loss is substantial, and confidence intervals are wide.

Across all 6,708 v3 normal-phase rows, TX packet rate (packets/second) and TX throughput (megabits/second) had Pearson correlation 0.99999953 and Spearman correlation 0.99910814, with 557 and 629 distinct values, zero missing values, and neither constant. This descriptive calculation was not used for feature selection or tuning. The collector derives packet rate from packet-counter deltas and throughput from byte-counter deltas. They are nearly redundant under the fixed-size iperf datagrams used here, but packet-size variation would distinguish them.

## RX acquisition-era shift

All RX counters and RX-derived rates/throughput are zero for the 17 historical source experiments; all eight recollections (logical IDs 3, 10, and 20–25) have nonzero RX measurements. The acquisition cause is unknown. RX-derived features therefore have a cohort-dependent distribution and should not be interpreted as consistently measured across all 25 experiments.

An exploratory same-split 25-fold LOEO direction ablation is preserved at `evaluations/v3_sensor_direction_ablation_20261015_2230/`. TX-only retained RF Top-1/Top-2 at 80%/88% (matching the all-feature result), while the topology ranker changed from 52%/88% with all features to 36%/64% TX-only. RX-only scored 20%/60% for RF and 36%/72% for the topology ranker. Treat these as sensitivity checks under the acquisition shift, not confirmatory estimates.

The 6 Mbps UDP profile was used for a separate, single engineering pilot: logical 27 / physical 31 completed after logical 26 / physical 30 remained `FAILED_INVALID`. Both runs are preserved and excluded from v3. The run-31 criteria were selected after the run-30 outcome and are exploratory, not preregistered. Its iperf summary is whole-run only and cannot separate baseline loss from the deliberate outage; no independent post-run cleanup snapshot is preserved. The VM was not NTP-synchronized, so no cross-machine timing claim is supported. See `TRAFFIC_PROFILE_PILOT_AUDIT.md` and `TRAFFIC_PROFILE_REPEATABILITY_PROTOCOL.md`. No pilot output belongs in v3.
