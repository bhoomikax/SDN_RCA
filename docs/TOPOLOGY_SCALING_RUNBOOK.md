# Topology scaling runbook: 4, 8, and 12-switch linear topologies

This runbook covers the generalized linear topology, live collection of new
experiment sets on the Mininet VM, candidate construction, the five-model
grouped leave-one-experiment-out (LOEO) evaluation, the explainability layer,
and the cross-topology comparison. The four-switch study data, graphs, and
evaluations are frozen and are never rewritten by any command below
(`test_frozen_artifacts.py` checks their hashes).

Everything here is conditional fault-window localization with an
oracle-selected window. Nothing is online detection or causal root-cause
analysis. All model scores are uncalibrated ranking scores.

## 1. Topology definition

`linear_topology.py` defines `LinearTopology(N)`: hosts `h1`, `h2`; switches
`s1..sN` connected in order; `N-1` inter-switch candidate links
(`s1-s2`, ..., `s(N-1)-sN`); the 10 Mbps / 5 ms bottleneck on the middle
candidate link (`s2-s3`, `s4-s5`, `s6-s7` for N = 4, 8, 12); all other links
unconstrained. `LinearTopology(4)` reproduces the original study topology
exactly. Each size has a frozen traffic profile in `traffic_profiles/`
(`udp_6mbps_v1.json`, `udp_6mbps_8sw_v1.json`, `udp_6mbps_12sw_v1.json`),
identical except for the bottleneck link name: 6 Mbps UDP, 20/20/20 s phases.

Run registries (`topology_run_registry(N)`) are fixed: 8-switch logical
101-130 / physical 1101-1130, 12-switch logical 201-260 / physical 1201-1260,
fault links assigned round-robin so any prefix of the schedule is balanced.
Spare slots exist so invalid runs can be replaced without reusing an ID; the
12-switch registry was extended from 30 to 60 slots on 2026-10-24 (first 30
assignments unchanged) after a VM suspend and its aftermath consumed IDs
208-215.

**Admission rules added for the new topologies.** Besides the existing rules
(COMPLETE status, schema, finite values, duplicate keys, switch and mapping
coverage, reciprocal target mapping, ordered phase coverage, iperf process
records, sender duration 60 ± 2 s, matching receiver reports), a run is
rejected when the iperf sender's reported rate is outside ±10% of the
profile's 6 Mbps (`validate_offered_rate` in the runner, re-checked by the
batch and by `build_topology_candidate.py`). This caught three runs that
completed at about 3 Mbps (8-switch 1122; 12-switch 1210 and 1212, both
after the VM suspend). A correctly paced client reports 6.29 Mbit/s.

## 2. Windows checks (offline)

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
.\venv\Scripts\python.exe -m unittest test_linear_topology test_topology_candidate_builder test_evaluate_topology_loeo test_explain_rca test_frozen_artifacts -v
.\venv\Scripts\python.exe -m py_compile linear_topology.py experiment_runner_recollection.py telemetry.py build_topology_candidate.py evaluate_topology_loeo.py graph_temporal_topology.py evaluate_graph_temporal_topology_loeo.py explain_rca.py build_topology_comparison.py run_topology_batch.py
```

`shap==0.54.1` was added to the Windows environment for the RF explanations.

## 3. VM preflight (read-only)

```powershell
$VmKey = Join-Path $env:USERPROFILE ".ssh\mininet_vm_ed25519"
ssh -i $VmKey -p 2222 -o IdentitiesOnly=yes mininet@127.0.0.1 "ss -lnt | grep -E '6633|6653'; sudo -n ovs-vsctl list-br; ps -eo pid,args | grep -E '[r]yu-manager|[m]n |[i]perf'; timedatectl show -p NTPSynchronized --value"
```

Required: the Ryu listener is present, `ovs-vsctl list-br` is empty, no `mn`
or `iperf` process is running. Do not run `mn -c`. The VM clock is not NTP
synchronized; only within-run ordering is claimed.

Stage the runner in its own directory (the existing deployments are not
touched):

```powershell
$Stage = "/home/mininet/sdn_project/topology_scaling_20261023"
scp -i $VmKey -P 2222 -o IdentitiesOnly=yes experiment_runner_recollection.py telemetry.py telemetry_pipeline.py linear_topology.py run_topology_batch.py test_recollection_runner.py mininet@127.0.0.1:$Stage/
scp -i $VmKey -P 2222 -o IdentitiesOnly=yes traffic_profiles/*.json mininet@127.0.0.1:$Stage/traffic_profiles/
ssh -i $VmKey -p 2222 -o IdentitiesOnly=yes mininet@127.0.0.1 "cd $Stage && sha256sum experiment_runner_recollection.py telemetry.py linear_topology.py && python3 -B -m unittest test_recollection_runner"
```

Compare the printed hashes with `sha256sum` of the local files.

## 4. Verify a topology without injecting a fault

Starts the N-switch network, captures the runtime port mapping, pings, stops,
and writes nothing:

```sh
sudo -n python3 -B experiment_runner_recollection.py --switches 8 --verify-topology
sudo -n python3 -B experiment_runner_recollection.py --switches 12 --verify-topology
```

Expected: `observed_inter_switch_link_count` equals `N-1`, `ping_loss_percent`
0.0, `post_stop_bridges` empty. Measured on 2026-10-23: 7 and 11 links,
0% loss, collector sweep 0.2 s (8) and 0.3-0.4 s (12).

## 5. Live collection (one run, or the batch)

A single registered run (as root, inside the VM):

```sh
sudo -n python3 -B experiment_runner_recollection.py --switches 8 --logical-id 101 --physical-id 1101 --normal-seconds 20 --fault-seconds 20 --recovery-seconds 20 --run
```

Without `--run` the same command is a read-only preflight. The run directory
is `recollection_runs/topology_<N>_switches/physical_<p>_logical_<l>/` under
the staging directory; it is refused if it already exists.

Sequential batch until 25 valid runs (stops on three consecutive failures,
on stale bridges, or on a busy Mininet/iperf process):

```sh
cd /home/mininet/sdn_project/topology_scaling_20261023
sudo -n nohup python3 -B run_topology_batch.py --switches 8 --target-valid 25 > batch_8.log 2>&1 < /dev/null &
# after the 8-switch batch finishes:
sudo -n nohup python3 -B run_topology_batch.py --switches 12 --target-valid 25 > batch_12.log 2>&1 < /dev/null &
```

Never run two batches at once. `batch_log.jsonl` in the run root records every
attempt. Each run takes about 90 s (8 switches) to 100 s (12 switches).

**Keep the Windows host idle during collection.** The VM has one vCPU on the
same laptop. On 2026-10-24 the 12-switch batch failed repeatedly (iperf
sender under-paced at ~3 Mbps, sender durations of 73-81 s, an iperf server
that never exited) while two CPU-bound Python jobs ran on Windows and the
laptop was on battery; with the host idle the same VM paced 6.29 Mbps and
verified the topology normally. Run the neural evaluations and XAI only after
collection has finished, and keep the laptop on mains power.

## 6. Export raw evidence to Windows (immutable copy)

```powershell
ssh -i $VmKey -p 2222 -o IdentitiesOnly=yes mininet@127.0.0.1 "sudo -n tar czf /tmp/export_8.tgz -C $Stage/recollection_runs topology_8_switches && sudo -n chown mininet /tmp/export_8.tgz"
scp -i $VmKey -P 2222 -o IdentitiesOnly=yes mininet@127.0.0.1:/tmp/export_8.tgz $env:TEMP\export_8.tgz
# Git Bash: tar --force-local -xzf "$TEMP/export_8.tgz" -C raw_evidence/
```

`raw_evidence/topology_<N>_switches/` holds one directory per run plus
`batch_log.jsonl`; `SHA256SUMS.txt` is written by the export step in section 8.

## 7. Candidate, graph, evaluations, explanations, comparison (Windows)

All output directories must not exist yet.

```powershell
# 8 switches
.\venv\Scripts\python.exe build_topology_candidate.py --switches 8 --runs-root raw_evidence\topology_8_switches --output-dir results\topology_8_switches\candidate
.\venv\Scripts\python.exe build_graph_multi.py --switches 8 --input results\topology_8_switches\candidate\candidate_dataset.csv --output results\topology_8_switches\graph\graph_dataset.json
.\venv\Scripts\python.exe evaluate_topology_loeo.py --switches 8 --candidate-dir results\topology_8_switches\candidate --output-dir results\topology_8_switches\loeo_rf_topology
.\venv\Scripts\python.exe evaluate_graph_temporal_topology_loeo.py --switches 8 --graph results\topology_8_switches\graph\graph_dataset.json --candidate results\topology_8_switches\candidate\candidate_dataset.csv --reference-dir results\topology_8_switches\loeo_rf_topology --output-dir results\topology_8_switches\loeo_neural --save-checkpoints
.\venv\Scripts\python.exe explain_rca.py --switches 8 --candidate-dir results\topology_8_switches\candidate --graph results\topology_8_switches\graph\graph_dataset.json --rf-eval-dir results\topology_8_switches\loeo_rf_topology --neural-eval-dir results\topology_8_switches\loeo_neural --output-dir results\xai\topology_8_switches
```

Repeat with `12` for the 12-switch set. For the frozen four-switch data the
same tools run with the static setup-inferred mapping (the historical runs
have no captured runtime mapping):

```powershell
.\venv\Scripts\python.exe evaluate_topology_loeo.py --switches 4 --candidate-dir derived_datasets\balanced_recollection_20261015_v3 --static-four-switch-mapping --output-dir results\topology_4_switches_regression\loeo_rf_topology
.\venv\Scripts\python.exe evaluate_graph_temporal_topology_loeo.py --switches 4 --graph derived_graphs\balanced_recollection_v3_portsum\graph_dataset.json --candidate derived_datasets\balanced_recollection_20261015_v3\candidate_dataset.csv --reference-dir results\topology_4_switches_regression\loeo_rf_topology --output-dir results\topology_4_switches_regression\loeo_neural --save-checkpoints
.\venv\Scripts\python.exe explain_rca.py --switches 4 --candidate-dir derived_datasets\balanced_recollection_20261015_v3 --static-four-switch-mapping --graph derived_graphs\balanced_recollection_v3_portsum\graph_dataset.json --rf-eval-dir results\topology_4_switches_regression\loeo_rf_topology --neural-eval-dir results\topology_4_switches_regression\loeo_neural --output-dir results\xai\topology_4_switches
```

The four-switch regression must reproduce the frozen release: RF 20/25 and
22/25, topology ranker 13/25 and 22/25 with identical per-experiment rankings
(asserted by `test_evaluate_topology_loeo.py`), and the neural ensemble
23/20/18 Top-1 for GCN+LSTM/GCN/LSTM.

Comparison table and plot:

```powershell
.\venv\Scripts\python.exe build_topology_comparison.py
```

Writes `results/comparison_4_8_12/comparison_table.{md,csv}`,
`comparison.json`, and `comparison.png`. Missing evaluations print as
"not run"; nothing is filled in.

## 7b. Independent methodology audit

Recomputes every reported number from the per-experiment rows (grouped
splits, leakage, denominators, candidate counts, ranking permutations,
Top-k/MRR, chance levels, seed-ensemble means, RF/neural reference agreement,
XAI/evaluation agreement, SHAP additivity and IG completeness identities, and
paired experiment-level sign tests):

```powershell
.\venv\Scripts\python.exe audit_topology_results.py
```

Writes `results/audit/methodology_audit.{json,md}` and exits non-zero if any
check fails. The 8-switch topology-ranker investigation is in
`results/audit/topology_ranker_8sw_investigation.md`.

## 8. Recording hashes

```powershell
Get-ChildItem -Recurse raw_evidence\topology_8_switches -File | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $($_.Path)" } | Set-Content raw_evidence\topology_8_switches\SHA256SUMS.txt
```

Every evaluation summary records the candidate SHA-256, the evaluator
protocol, seeds, software versions, and (for the neural run) checkpoint
hashes. `results/comparison_4_8_12/comparison.json` cites each source.

## 9. Troubleshooting

- `Existing OVS bridges conflict`: a previous network is still up; identify
  its owner, never clear OVS blindly.
- A run marked `FAILED_INVALID` with "iperf sender duration ... outside
  requested 60s ± 2s" is an iperf client stall; the ID is consumed, the batch
  continues with the next registered ID, and the builder excludes the run.
- `Candidate-link endpoint mapping differs between runs`: Mininet assigned
  ports differently; the builder refuses to merge rather than guess.
- `Refusing to overwrite`: choose a new output directory.
- A run left as `RUNNING_INVALID_UNTIL_COMPLETE` with stale bridges means the
  runner was killed before its `finally` cleanup (observed once on 2026-10-24
  for 12-switch run 1208 after the VM was suspended mid-run; the batch then
  stopped fail-closed). Remove only that run's recorded resources with the
  evidence-driven tool, never `mn -c` (it kills the shared Ryu):

  ```sh
  sudo -n python3 -B cleanup_abandoned_run.py --run-dir recollection_runs/topology_12_switches/physical_1208_logical_208          # dry run
  sudo -n python3 -B cleanup_abandoned_run.py --run-dir recollection_runs/topology_12_switches/physical_1208_logical_208 --apply
  ```

  It refuses to act on a COMPLETE run or while any Mininet/iperf process is
  alive, and lists bridges it will not touch. Re-launch the batch afterwards;
  it skips every existing run directory and the abandoned ID stays consumed.
- Persistent iperf failures after a host suspend (sender 73-163 s, clients
  pacing ~3 Mbps, servers that never exit) with a healthy loopback test and a
  passing `--verify-topology`: on 2026-10-25 the guest kernel log showed
  `soft lockup - CPU#0 stuck for 9842s` and `rcu_sched self-detected stall`
  from the suspends, i.e. damaged guest timekeeping. Four relaunches produced
  3 valid runs in 13 attempts. The remedy is a guest reboot, which also
  restarts the shared Ryu controller (start it again with
  `cd /home/mininet/sdn_project && /home/mininet/.local/bin/ryu-manager controller.py`
  in a dedicated terminal), so it needs explicit approval. **Performed with
  approval on 2026-10-25:** the documented `sudo reboot` did not take effect
  because systemd's bus was wedged (`timedatectl` timed out, SSH logins took
  minutes); `sudo -n sync; sudo -n reboot -f` rebooted the guest. Post-reboot:
  0 kernel warnings, clean ext4 mount, no bridges, Ryu restarted detached
  (`nohup ... ryu-manager controller.py > ryu_<date>.log 2>&1 &`), both
  listeners up, loopback 6.29 Mbps, 12-switch verification 11 links / 0% loss.
  The batch then completed 17 valid runs in 17 attempts. Before any new
  collection also close the VS Code remote-SSH session to the VM (its
  `node` server consumed up to 89% of the single vCPU in bursts) and keep the
  Windows host awake and on mains (its AC sleep timeout is 5 minutes).
