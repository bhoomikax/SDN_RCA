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
