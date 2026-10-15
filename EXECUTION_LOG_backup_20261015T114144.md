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
