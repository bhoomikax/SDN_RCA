# SDN_RCA execution log

This log records verified work and decisions for the autonomous completion effort. Historical data and prior outputs remain read-only.

## 2026-10-15 — Run 23 and current audit

- Repository: `C:\Users\ASUS\sdn-ml`, branch `main`. Most project files/results are untracked; nothing was reset or cleaned.
- Windows Python 3.13.7 environment works. The full offline suite passed **43/43** with `venv\Scripts\python.exe -m unittest discover -v`.
- The isolated loopback iperf2 smoke used earlier produced successful sender/receiver summaries; parser now handles iperf2's padded `0.0- 4.0 sec` interval format.
- The current Ubuntu runner/test hashes were checked against the Windows copies before the authorized run: runner `1a956943244e05c065a3c3295d81bad91bdc8443935693f9805b545ad8acccc2`; tests `68ad088a703ef9f42be2fff48e553816877c83af5fff5388b67e4b44302d89aa`.
- Read-only preflight found physical ID 23 unused, project-local Ryu reachable on 6633, and no existing Mininet, iperf, or OVS bridges. Preflight passed without creating files.
- Exactly one run was launched: logical 3 / physical 23, link failure on s3-s4, 20 s normal + 20 s fault + 20 s recovery. Command:

  ```sh
  sudo -n python3 -B experiment_runner_recollection.py --logical-id 3 --physical-id 23 --normal-seconds 20 --fault-seconds 20 --recovery-seconds 20 --run
  ```

- Runner exited 0 and wrote `/home/mininet/sdn_project/recollection_runs/physical_23_logical_3/`; status `COMPLETE`. Six artifacts were mirrored byte-for-byte to `run23_raw_evidence_physical23_logical3/` for offline validation.
- Runtime s3-s4 mapping verified from live Mininet/OVS state: s3 port 2 `s3-eth2` ↔ s4 port 1 `s4-eth1`.
- Telemetry: 648 rows, 54 timestamps, all four switches, exact 15-column schema, valid finite numeric fields, no duplicate `(timestamp,switch,port)` keys. Actual coverage was 2026-10-14 13:43:43.643921–13:44:47.692854 UTC; normal/fault/recovery events were ordered and covered.
- iperf client/server both exited 0; client sender and both receiver summaries report 60 s and matching totals: 133,746 sent, 30,379 received, 103,367 lost. The runner's process-completion proof passes; severe packet loss remains an explicit experimental outcome, not evidence of good delivery.
- Run 22's six artifact hashes remained identical to the forensic baseline. `master_dataset.csv` remains SHA256 `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`. No residual iperf/Mininet processes or OVS bridges were present after run 23.
- No dataset was merged, no model retrained, and no historical output changed.

## Evidence policy and remaining work

- Run 20 remains `FAILED_INVALID`; run 22 remains `PROVISIONAL` and excluded from primary data. Run 23 has valid runner/process/timestamp/mapping evidence and is pending canonical dataset-builder validation.
- The historical clean 17-run candidate and audit manifest are inputs only. A new logical-18 candidate must be emitted under a new filename with the physical-to-logical mapping and raw hashes preserved.
- Existing conditional localization metrics use annotated fault phases to select windows and must not be described as online detection. The old 13/6 split is not reproducible after exclusions/recollection; grouped LOEO is the supported current split for a revised analysis.
- Existing graph/temporal checkpoints and metrics must be audited for their actual task. No graph-temporal localization claim is made without a matching evaluated task.

## 2026-10-15 — Forensic parser correction, dataset re-audit, evaluation, documentation

- Run 21 remains preserved with original `FAILED_INVALID` status and artifacts. Its failure was a strict equality check between the client sent count and the server's iperf2 sequence-derived UDP Lost/Total count. The iperf2 maintainer documents that these sequence counters can differ from sender count because packets may be in flight, including the final UDP packet. Parser behavior was corrected and tested without rerunning the experiment; candidate admission uses independent re-audit and preserves the original failure reason/status.
- Runner and regression tests were backed up and synchronized to Ubuntu. Ubuntu syntax checks and the full offline suite passed 44 tests. Current runner/test hashes are recorded in `project_inventory.json`.
- Candidate v2: 12,912 rows, 19 logical IDs, SHA-256 `914fd551778b0eb918a1d74b1fc2476c0ab533909cab0d28a56303255a8bf916`. Physical 21 maps to logical 10 and physical 23 to logical 3. Run 20 remains invalid; run 22 provisional. Master hash remains `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`.
- Fixed identity split on the revised candidate (train 1–9,13,14,17,19; test 10,11,12,15,16,18): RF Top-1 4/6, Top-2 6/6; topology ranker Top-1 3/6, Top-2 6/6. LOEO over 18 experiments (physical 21 excluded): RF 15/18 and 16/18 Top-1/Top-2; topology 10/18 and 14/18. Both are oracle-assisted conditional localization, not online detection. No method improvement is claimed.
- Created documentation in `docs/` covering architecture, methodology, dataset card, experiment protocol, results, limitations, offline demo, review slides, and a cautious manuscript draft. Replaced the 9-byte placeholder README after retaining `README_backup_20261015.md`.
- Windows verification after implementation: full offline suite passed 50 tests; syntax checks are run in this completion pass. No live experiment, merge to master, model retraining, commit, or push was performed.

## Final completion pass — offline demo and verification

- Added `demo_rca.py`, a read-only saved-results replay. It verifies the candidate dataset SHA-256 against both evaluation and dataset provenance before displaying recorded per-experiment rankings. It does not train or make fresh predictions. Added two tests covering replay output and hash mismatch rejection.
- Added nine technical/research documents under `docs/` and replaced the placeholder README; the original placeholder was retained as `README_backup_20261015.md`.
- Final Windows verification: `venv\\Scripts\\python.exe demo_rca.py` completed; `venv\\Scripts\\python.exe -m unittest discover -v` passed 52 tests; `py_compile` passed for the demo, dataset builder, evaluators, runner, and tests. `project_inventory.json` parses successfully.
- Final Ubuntu verification: runner/test SHA-256 values match the local copies; `python3 -m py_compile experiment_runner_recollection.py test_recollection_runner.py` passed; `python3 -m unittest discover -v` passed 44 tests. This was offline only.
- Final integrity check: master dataset SHA-256 remains `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`; final candidate SHA-256 remains `914fd551778b0eb918a1d74b1fc2476c0ab533909cab0d28a56303255a8bf916`. No live experiment, merge, training, commit, or push occurred in this pass.

## 2026-10-15 — Balanced recollections and v3 evaluation

- Completed the remaining preauthorized physical runs sequentially: physical 28→logical 24 (s3-s4) and physical 29→logical 25 (s3-s4). Both passed read-only preflight, runner status, process cleanup, phase/timestamp/artifact checks, runtime mapping checks, and independent Windows candidate-builder validation. Telemetry rows: 684 and 672. Their iperf2 client/server exits were 0, but sequence-accounted loss was substantial; delivery was 23,547/63,649 and 23,066/62,551 respectively. No other runs were launched.
- Independently verified physical 27→logical 23 raw artifacts (672 rows, mapping s2 port 2↔s3 port 1). Physical runs 24–29 raw evidence copies and transfer archives are preserved in distinct locations.
- Built candidate v3 from historical source plus physical 21, 23, and 24–29: 16,956 rows, 25 logical experiments, SHA-256 `b63d04572b7b97b8451be33174c8813d76af53e3f49f40e5e41b682b1e19b29a`. Phase counts normal/fault/recovery: 6,708/5,544/4,704. Fault rows s1-s2/s2-s3/s3-s4: 1,776/2,004/1,764. Master hash remains `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`.
- Added the 29-row machine-readable admission ledger. It distinguishes raw run status from derived admission, includes raw artifact hashes, records run 21 as raw `FAILED_INVALID` but derived `VALID`, run 20 as `FAILED_INVALID`, and run 22 as raw `COMPLETE` but derived `PROVISIONAL / UNVERIFIED` because process completion is not evidenced.
- Built corrected v3 graph snapshots from all numbered non-LOCAL ports (1,413 snapshots; candidate source hash matches). Fixed the evaluator wrapper's captured default dataset bug, added a generalized grouped evaluator and mixed-precision ISO timestamp parsing, and verified 25 LOEO folds (24 train/1 held out). RF: Top-1 20/25 (80%), Top-2 22/25 (88%); topology ranker: Top-1 13/25 (52%), Top-2 22/25 (88%). Wilson 95% intervals for Top-1: RF [60.9%, 91.1%], topology [33.5%, 70.0%]. Results are conditional fault-window localization, not online detection.
- Replayed and preserved the existing exact 13/6 comparison; v3 subset IDs 1–19 were row-for-row equal to the prior candidate. Existing neural localization results remain exploratory: graph-only 5/6 Top-1 and Top-2; temporal-only 4/6 Top-1 and mean 5.67/6 Top-2; graph-temporal 4/6 Top-1 and mean 5.33/6 Top-2 across seeds. They do not prove improvement over RF and are not v3 LOEO neural results.
- Added a v3 dataset card, results report, hash-sealed saved-results demo, and README reproduction commands. The first v3 LOEO wrapper output and a later stale-summary output are marked invalid, not deleted. The fixed-split rerun against all 25 IDs refused by design; its duplicate recomputation was stopped before outputs. Existing fixed-split results apply to the verified identical 1–19 rows.
- Windows: `venv\\Scripts\\python.exe -m unittest discover -v` passed 63 tests; targeted `py_compile` passed; v3 saved-results replay succeeded. The first discovery pass included an old backup test and failed because that backup asserted an obsolete ID map; backup test files were renamed (contents preserved) so active source tests are discovered only.
- Ubuntu: runner/test hashes match Windows (`dc374f19…` / `8d255ddd…`); `python3 -m unittest discover -v` passed 44 offline tests. No VM service was started or stopped during this verification.
- Protected original datasets, checkpoints, and prior result folders were preserved. No merge to master, model retraining on new data, commit, or push was performed.
- Added a separate phase-blind, timestamp-causal anomaly detector for the online detection task. Training-normal-only statistics and a fixed q99 threshold are used per LOEO fold; training phase labels select training-normal fit rows; held-out phase annotations join only after prediction. Future-data invariance tests pass. The measured detector missed all 25 fault windows, with six false-alarm episodes (14.14 per observed nonfault hour); this negative result is preserved without test-set threshold tuning.
- Added a v3 saved-results replay with hash checks for candidate, predictions, splits, feature policy, and summary. The physical/logical 20 held-out example replay shows the saved ranking, annotated ten-second window and measured features; it is explicitly not fresh inference.
- Final Windows offline suite after these additions: 65 tests passed. Runner/test VM hashes still match the local copies; VM offline suite remains 44 passed. Original candidate v2 hash, master hash, and graph-temporal checkpoint hashes were verified unchanged.

## Latest offline validation and traffic-profile status

- Audited RX feature distributions in frozen v3: all RX counters and RX-derived rate/throughput fields are zero for the 17 historical source experiments, while all eight recollections (logical IDs 3, 10, 20–25) contain nonzero RX measurements. The cause is unknown; this is treated as an acquisition-era distribution shift, not evidence that either cohort is defective.
- Ran a same-split exploratory 25-fold feature-direction ablation. Full-feature results were RF 80%/88% and topology 52%/88% Top-1/Top-2; TX-only was RF 80%/88% and topology 36%/64%; RX-only was RF 20%/60% and topology 36%/72%. Outputs and manifest are preserved under `evaluations/v3_sensor_direction_ablation_20261015_2230/`. They do not replace the primary evaluation.
- Prepared `traffic_profiles/udp_6mbps_v1.json`: UDP offered load 6 Mbps (60% of configured 10 Mbps s2-s3 capacity, below the 70% limit), iperf2 default payload sizing, and 20-second normal/fault/recovery phases. The runner validates the profile/topology relationship, checks iperf2, records its version and profile hash, parses actual sender/receiver final-summary rates, and enforces the frozen phase durations. Logical 26 / physical 30 is reserved for this pilot only.
- SSH to `mininet@127.0.0.1:2222` was denied with `Permission denied (publickey,password)`. No VM run, deployment, service change, or v4 collection occurred. The profile is proposed and locally tested, not empirically validated.
- Latest local verification: `venv\\Scripts\\python.exe -m unittest -v test_recollection_runner` passed 39 tests; `venv\\Scripts\\python.exe -m unittest discover -v` passed 69 tests; `py_compile` passed for the runner and its test module. A prior Ubuntu suite passed 44 tests on the earlier runner revision; it does not validate the latest changes.
- Rechecked SHA-256: v3 candidate remains `b63d04572b7b97b8451be33174c8813d76af53e3f49f40e5e41b682b1e19b29a`; historical master remains `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`. Updated runner/test/profile hashes are recorded in `project_inventory.json`. No candidate, historical data, or prior primary result was modified; no commit or push was made.
