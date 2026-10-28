# Professor demo script (about 12 minutes)

Before the session: VM running, Ryu listening, backend started
(`.\venv\Scripts\python.exe dashboard\backend\serve.py`), frontend started
(`cd dashboard\frontend; npm run dev`), browser on http://localhost:3000,
laptop on mains, nothing else CPU-heavy running.

| Step | Click | Say |
|---|---|---|
| 1 | **System Health** | "Every row is tested now: SSH into the Mininet VM, the Ryu controller on 6633 checked from inside the VM, OVS and Mininet present, no stale bridges, the deployed runner's hash equals the source in this repository, checkpoints for all three topologies present." |
| 2 | **Network Topology**, choose 12 switches | "A linear chain h1–s1…s12–h2 with 11 candidate links. The bottleneck s6–s7 (10 Mbps, 5 ms) is amber; the fault link is dashed red. Chance Top-1 here is 1/11, so a 73 % Top-1 on 12 switches means more than 80 % on 4." |
| 3 | **Live Demo** → 12 switches → **Run preflight** | "IDs are validated against a fixed registry; 248/1248 was already run, so the preflight refuses to reuse the directory. I take the next free pair. The preflight is read-only: the runner itself reports the output directory, fault link and controller reachability." |
| 4 | **Start experiment** → tick the acknowledgement → confirm | "This is the real `experiment_runner_recollection.py --run` inside the VM. 20 s normal traffic, then both ends of the configured link go down for 20 s, then recovery. The dashboard holds a lock so two runs cannot overlap." |
| 5 | Watch **Experiment lifecycle** and the charts (≈100 s) | "Phase boundaries come from the runner's own phase_events.csv; progress is the VM clock minus the event time. In the fault phase the TX throughput of every switch downstream of the fault collapses to zero: that is the symptom, and every downstream switch looks anomalous. Localisation must find the boundary." |
| 6 | When state = **complete**, **Fetch run and rank candidate links** | "The six raw files are copied into an isolated folder and admitted by the same validation rules as the research data, including the ±10 % offered-rate rule. Random Forest and the heuristic are refit on the 26 admitted research runs; the three neural models use saved fold checkpoints that never saw this run. Ground truth is shown separately and only after ranking." |
| 7 | Point at the ranking cards | "Scores are ranking scores, not probabilities. The learned models put the true link first; the fixed heuristic does not on long chains, and the saved audit explains why. TreeSHAP shows which per-switch anomaly statistics moved the RF score; this is model attribution, not causation." |
| 8 | **Model Comparison** | "Saved, audited results. Read every bar against its chance level. Intervals of the learned models overlap; we make no superiority claim. The topology ranker collapses from 13/25 to 1/24 and 1/26." |
| 9 | **XAI / Explainability**, 8 switches, experiment 104 | "Each model's explanation is validated: additivity for SHAP, completeness for integrated gradients, and a deletion test against random features. Attributions spread along the chain where traffic disappears." |
| 10 | **Saved Experiments** | "Every VM run with status and failure reason; 18 of 44 twelve-switch attempts were rejected, each with its reason. Dashboard runs stay in dashboard_runs/ and are never merged into the research datasets." |

If the VM is unavailable: steps 1, 8, 9 and 10 still work from saved results
(Health shows Disconnected / Not Tested truthfully); step 6 works for the
already fetched run 248 by selecting it in "Select VM run".
