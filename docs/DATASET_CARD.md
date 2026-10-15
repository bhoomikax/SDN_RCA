# Dataset card: validated candidate v2

## Identity

- Path: `derived_datasets/candidate_with_reaudited_physical21_and_physical23_v2/candidate_dataset.csv`
- SHA-256: `914fd551778b0eb918a1d74b1fc2476c0ab533909cab0d28a56303255a8bf916`
- Rows: 12,912; logical experiments: 1–19; columns: 17.
- Source inputs: immutable 11,604-row historical candidate plus validated new physical runs 21 and 23.
- Historical source candidate SHA-256: `e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2`.

## Labels and distribution

Fault-link labels: `s1-s2`, `s2-s3`, `s3-s4`. Candidate fault-link row counts from provenance are 1,356; 1,572; and 1,332 respectively across the assembled dataset. Phase counts in the assembled data: normal 5,340; fault 4,260; recovery 3,312. The unit for evaluation is experiment, not row.

## Collection and admission

Physical 21 → logical 10 and physical 23 → logical 3. Run 23 was runner-complete with runtime-verified s3-s4 map (s3 port 2/interface s3-eth2 ↔ s4 port 1/interface s4-eth1), 648 telemetry rows and valid process/time evidence. It had severe sequence-count packet loss: 30,379 sequence-accounted nonlost of 133,746 sent. Run 21 raw metadata remains `FAILED_INVALID`; separate re-audit admitted its preserved evidence after checking process outcomes, durations, matching receiver summaries, telemetry, phase coverage, and mapping. The original failure and counter difference remain recorded in candidate provenance.

## Exclusions and protected evidence

- Historical logical 3: out-of-range phases and byte-identical telemetry attributed to logical 4; excluded as a historical recording. New physical 23 is separate evidence.
- Historical logical 10: phase events outside telemetry range; excluded. New physical 21 is separate evidence.
- Physical 20: invalid first-sample/normal marker ordering; excluded.
- Physical 22: `PROVISIONAL`, missing trustworthy process completion proof; excluded.
- `master_dataset.csv` is the immutable historical source and was not replaced. Recorded SHA-256: `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`.

## Limitations and intended use

Small controlled topology and experiment count; three link classes; repeated conditions may limit independence. Telemetry-derived RX features were historically all-zero in older CSV datasets. TX packet rate and throughput are highly correlated in training-normal telemetry (diagnostic Pearson approximately 0.999999 and Spearman approximately 0.995819), but that alone does not prove universal interchangeability. Fault-phase annotations are oracle information for current localization. Historical port mappings are setup-inferred. Use for method development and controlled comparisons, not production deployment or general-network performance claims.
