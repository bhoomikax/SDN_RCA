# Run 22 Dataset and RCA Milestone Review

## Final disposition

The telemetry and phase-event checks pass, and the candidate/evaluation artifacts were generated in this isolated directory. However, the run's iperf logs are incomplete: both contain startup and connection messages but no final client/server interval or summary statistics. The recollection runner starts iperf in the background with a 60-second duration and does not wait for or record its exit status before Mininet cleanup. Therefore traffic-process completion is **not verified**.

Following the fail-closed requirement, this candidate is **provisional and not approved as a validated replacement dataset**. The grouped metrics below are measured from the files but are exploratory only. Do not merge the candidate or present these scores as confirmatory evidence until the traffic/log gap is resolved using trusted evidence or a separately authorized recollection.

## Raw run audit

- Metadata status: `COMPLETE`; logical ID 3, physical ID 22; target `s3-s4`.
- Telemetry: 672 rows, 56 timestamps, four switches, unique `(timestamp, switch, port)` keys; schema and finite, nonnegative numeric values passed.
- Phase order and coverage passed: first sample 2026-10-14 08:35:50.514877 UTC; normal 08:35:50.644628 UTC; fault 08:36:12.752691 UTC; recovery 08:36:32.917019 UTC; last sample 08:36:54.677955 UTC.
- Runtime target mapping passed: `s3-eth2`, OpenFlow port 2, peer `s4-eth1`; `s4-eth1`, OpenFlow port 1, peer `s3-eth2`.
- Log presence passed; log completeness failed/not verified. No final iperf summary or process exit status is recorded.
- Original run artifacts were copied byte-for-byte to `audit/raw_run22/`; hashes are in `audit/run22_raw_provenance.json`.

## Candidate and exploratory evaluation

The new candidate has 12,276 rows and 18 logical experiments. Physical run 22 is represented as logical experiment 3 in the established schema. Logical experiment 10 remains excluded. Candidate phase counts are normal 5,112, fault 4,068, recovery 3,096. The run-22 additions are 672 rows: normal 228, fault 204, recovery 240. The existing candidate (11,604 rows) and historical master remain separate and unchanged.

The leave-one-logical-experiment-out evaluation used 18 folds (17 train, one held out). RF: Top-1 15/18, Top-2 16/18, Top-3 18/18. Topology ranker: Top-1 10/18, Top-2 14/18, Top-3 18/18. The three candidate links are always ranked, so Top-3 is guaranteed. The phase labels select the first ten seconds of the known fault window; this is oracle-assisted conditional localization, not online detection. These results are exploratory pending log-completeness resolution.

## Protected inputs and tests

The existing VM candidate SHA-256 remains `e9796f11603275e7f9a51f2195ede571637c3919905928b56879c5470102c5c2`; audit manifest remains `80f12f94a7fb0dd6b648126d1021993e78616aad0daf2ab7f4c1d423c8e16d7c`; master dataset currently hashes to `7fbfcc51dc3c5af122c28b52e558e3e037ad9367fde1b15bf0d25ff0faf9de64`.

- New grouped regression tests: 7 passed.
- Existing Ubuntu offline suite: 37 passed.
- Python syntax checks: passed.
- A Windows invocation of the existing suite failed in 10 tests because the POSIX runner tests patch `os.geteuid`, which is unavailable on Windows; the suite passed in its intended Ubuntu environment.
- No live experiment was run for this milestone; no dataset was merged and no model checkpoint was changed.

## Next required action

Inspect or recover trusted evidence that the background iperf client completed and produced its final output. If none exists, a new physical run would require separate explicit authorization; do not repair run 22's logs or status retroactively.
