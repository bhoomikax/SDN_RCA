"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, errorText, usePoll, METHOD_LABELS, METHOD_ORDER } from "@/lib/api";
import { useSelectedRun, runPath, RunRef } from "@/lib/run-selection";
import { TopologyDiagram, TopologyLegend } from "@/components/TopologyDiagram";
import { PhaseTimeline, StateBadge, StatusLike } from "@/components/PhaseTimeline";
import { TelemetryChart } from "@/components/TelemetryChart";
import { RankingTable, ScoreCaveat } from "@/components/RankingTable";
import { ConfirmPanel, ErrorBox, KeyValue, PageHeader, SourceTag, SwitchSelect } from "@/components/ui";

const DEFAULTS: Record<number, { logical: number; physical: number }> = {
  12: { logical: 248, physical: 1248 },
  8: { logical: 128, physical: 1128 },
  4: { logical: 0, physical: 0 },
};

type Pending = null | "verify" | "start";

export default function LiveDemoPage() {
  const { run, setRun } = useSelectedRun();
  const [switches, setSwitches] = useState(12);
  const [logical, setLogical] = useState(DEFAULTS[12].logical);
  const [physical, setPhysical] = useState(DEFAULTS[12].physical);
  const [preflight, setPreflight] = useState<Record<string, unknown> | null>(null);
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [verifyResult, setVerifyResult] = useState<Record<string, unknown> | null>(null);
  const [launch, setLaunch] = useState<Record<string, unknown> | null>(null);

  const topology = usePoll(`/api/topology?switches=${switches}`, 60000);
  const registry = usePoll(`/api/experiments/registry?switches=${switches}`, 30000, switches !== 4);
  const health = usePoll("/api/health", 20000);
  const isSelected = !!run;
  const status = usePoll<StatusLike>(run ? `${runPath(run)}/status?telemetry=true` : null, 4000);
  const statusData = status.data;

  useEffect(() => {
    setLogical(DEFAULTS[switches].logical);
    setPhysical(DEFAULTS[switches].physical);
    setPreflight(null);
    setPreflightError(null);
  }, [switches]);

  const registryEntry = useMemo(() => {
    const rows = (registry.data?.registry ?? []) as Array<{ logical_experiment_id: number; physical_run_id: number; fault_link: string; vm_status: string | null }>;
    return rows.find((r) => r.logical_experiment_id === logical) ?? null;
  }, [registry.data, logical]);
  const nextFree = registry.data?.next_free as { logical_experiment_id: number; physical_run_id: number; fault_link: string } | null | undefined;
  const controllerStatus = health.data?.controller?.status ?? (health.error ? "Not Tested" : "Unknown");

  async function doPreflight() {
    setBusy("preflight");
    setPreflightError(null);
    setActionError(null);
    try {
      const result = await apiPost("/api/experiments/preflight", { switches, logical_id: logical, physical_id: physical, confirm: false });
      setPreflight(result);
    } catch (err) {
      setPreflight(null);
      setPreflightError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function doVerify() {
    setBusy("verify");
    setActionError(null);
    try {
      const result = await apiPost("/api/experiments/verify-topology", { switches, confirm: true });
      setVerifyResult(result.result);
      setPending(null);
    } catch (err) {
      setActionError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function doStart() {
    setBusy("start");
    setActionError(null);
    try {
      const result = await apiPost("/api/experiments/start", { switches, logical_id: logical, physical_id: physical, confirm: true });
      setLaunch(result);
      setPending(null);
      setRun({ switches, logical, physical });
      setPreflight(null);
    } catch (err) {
      setActionError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  const configuredFault = (preflight?.registry_fault_link as string) ?? registryEntry?.fault_link ?? null;
  const diagramState = {
    switches: run && statusData ? run.switches : switches,
    configuredFault: run && statusData ? (statusData.configured_fault_link ?? statusData.fault_link_from_events ?? null) : configuredFault,
    observedFault: statusData?.fault_link_from_events ?? null,
    phase: statusData?.phase ?? null,
    bottleneck: topology.data?.bottleneck_link ?? null,
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Live Demo"
        subtitle="Conditional faulty-link localisation on the Mininet / OVS / Ryu testbed. Everything below is read from the VM or computed by the research code; nothing is simulated."
        right={<ErrorBox error={health.error} action="Start the backend: venv\Scripts\python.exe dashboard\backend\serve.py" />}
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* ---------------------------------------------------------------- control panel */}
        <div className="card xl:col-span-1">
          <div className="card-title">Experiment control panel</div>
          <div className="space-y-3">
            <div>
              <span className="label">Topology</span>
              <SwitchSelect value={switches} onChange={setSwitches} />
            </div>
            {switches === 4 ? (
              <div className="callout callout-warn">
                The four-switch run registry is exhausted (all authorised physical IDs were consumed by the research collection). New
                four-switch live runs are not available; saved four-switch results and explanations are.
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="label">Logical experiment ID</span>
                  <input className="input mono" type="number" value={logical} onChange={(e) => setLogical(Number(e.target.value))} />
                </div>
                <div>
                  <span className="label">Physical run ID</span>
                  <input className="input mono" type="number" value={physical} onChange={(e) => setPhysical(Number(e.target.value))} />
                </div>
              </div>
            )}
            {switches !== 4 && (
              <div className="note">
                Registered pairs only: logical {topology.data?.registry?.logical_range?.join("–")} with physical = logical +{" "}
                {topology.data?.registry?.physical_offset}.{" "}
                {registryEntry ? (
                  <>
                    Selected pair → configured fault <span className="mono">{registryEntry.fault_link}</span>; VM status:{" "}
                    <span className="mono">{registryEntry.vm_status ?? "unused"}</span>.
                  </>
                ) : (
                  <span style={{ color: "var(--fault)" }}>This logical ID is not in the registry.</span>
                )}{" "}
                {registryEntry?.vm_status && nextFree && (
                  <button
                    className="underline"
                    onClick={() => {
                      setLogical(nextFree.logical_experiment_id);
                      setPhysical(nextFree.physical_run_id);
                    }}
                  >
                    Use next free pair {nextFree.logical_experiment_id}/{nextFree.physical_run_id} (fault {nextFree.fault_link})
                  </button>
                )}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="label">Traffic profile</span>
                <div className="mono text-sm">UDP 6 Mbps, h1 → h2, 60 s (frozen profile)</div>
              </div>
              <div>
                <span className="label">Phase durations</span>
                <div className="mono text-sm">normal 20 s · fault 20 s · recovery 20 s</div>
                <div className="note">Fixed by the frozen traffic profile; the runner rejects other values.</div>
              </div>
            </div>
            <div>
              <span className="label">Bottleneck / configured fault</span>
              <div className="mono text-sm">
                bottleneck {topology.data?.bottleneck_link ?? "…"} (10 Mbps / 5 ms) · fault {configuredFault ?? "—"}
              </div>
            </div>
            <div>
              <span className="label">Controller (tested from the VM)</span>
              <span className={`badge ${controllerStatus === "Connected" ? "badge-ok" : controllerStatus === "Disconnected" ? "badge-bad" : "badge-muted"}`}>
                {controllerStatus}
              </span>{" "}
              <span className="note">{health.data?.controller?.detail}</span>
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <button className="btn" onClick={doPreflight} disabled={busy !== null || switches === 4}>
                {busy === "preflight" ? "Checking…" : "Run preflight (read-only)"}
              </button>
              <button className="btn" onClick={() => setPending("verify")} disabled={busy !== null || pending !== null}>
                Verify topology
              </button>
              <button
                className="btn btn-danger"
                onClick={() => setPending("start")}
                disabled={busy !== null || pending !== null || switches === 4 || !preflight || preflight.ready !== true}
                title={!preflight ? "Run the preflight first" : preflight.ready ? "" : "Preflight reported blockers"}
              >
                Start experiment
              </button>
            </div>
            <div className="note">
              There is no stop button: the runner has no safe cancellation path (a kill would leave Mininet state behind). A run lasts
              about 100 s and cleans up on its own, also on failure.
            </div>

            {pending === "verify" && (
              <ConfirmPanel
                title={`Verify the ${switches}-switch topology?`}
                description={
                  <>
                    This runs <span className="mono">experiment_runner_recollection.py --verify-topology</span> on the VM: it starts the Mininet
                    network, records the runtime port mapping, pings all hosts and stops the network. No run directory is created and no fault
                    is injected. Takes 20–60 s.
                  </>
                }
                confirmLabel="Verify topology"
                busy={busy === "verify"}
                onConfirm={doVerify}
                onCancel={() => setPending(null)}
              />
            )}
            {pending === "start" && (
              <ConfirmPanel
                title={`Start experiment ${logical} / ${physical} on ${switches} switches?`}
                description={
                  <>
                    This deploys the {switches}-switch topology inside the VM, drives 6 Mbps UDP traffic, and <strong>brings link {configuredFault} down</strong>{" "}
                    for 20 s before restoring it. It writes a new run directory on the VM (never overwriting an existing one). The historical
                    datasets on this machine are not touched.
                  </>
                }
                confirmLabel="Deploy topology and inject fault"
                danger
                busy={busy === "start"}
                onConfirm={doStart}
                onCancel={() => setPending(null)}
              />
            )}
            <ErrorBox error={actionError} action="Check System Health, then re-run the preflight." />
            <ErrorBox error={preflightError} />
            {preflight && (
              <div className={`callout ${preflight.ready ? "" : "callout-bad"}`}>
                <div className="font-semibold text-sm">Preflight {preflight.ready ? "passed" : "reported blockers"}</div>
                {(preflight.blockers as string[]).length > 0 && (
                  <ul className="list-disc pl-5 mt-1 text-sm">
                    {(preflight.blockers as string[]).map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                )}
                {preflight.ready === true && (
                  <div className="note mt-1">
                    Runner output dir: <span className="mono">{String((preflight.runner_preflight as Record<string, unknown>)?.output_dir)}</span>
                    {" · "}fault link <span className="mono">{String(preflight.registry_fault_link)}</span>. Read-only: nothing was created.
                  </div>
                )}
              </div>
            )}
            {verifyResult && (
              <div className="callout">
                <div className="font-semibold text-sm">Topology verified</div>
                <KeyValue
                  items={[
                    ["inter-switch links", `${verifyResult.observed_inter_switch_link_count} / ${verifyResult.expected_candidate_count}`],
                    ["ping loss", `${verifyResult.ping_loss_percent}%`],
                    ["collector sweep", `${verifyResult.collector_sweep_seconds} s`],
                    ["bridges after stop", JSON.stringify(verifyResult.post_stop_bridges)],
                  ]}
                />
              </div>
            )}
            {launch && (
              <div className="callout">
                Launched runner PID {String(launch.remote_pid)} on the VM at {String(launch.launched_at)}. Log:{" "}
                <span className="mono">{String(launch.log_path)}</span>
              </div>
            )}
          </div>
        </div>

        {/* ---------------------------------------------------------------- run state */}
        <div className="xl:col-span-2 space-y-5">
          <div className="card">
            <div className="flex items-center justify-between">
              <div className="card-title">Experiment lifecycle</div>
              <RunPicker switches={switches} />
            </div>
            {!run ? (
              <div className="note">No run selected. Start an experiment or pick an existing VM run above.</div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 mb-3 text-sm">
                  <span className="mono">
                    {run.switches} sw · logical {run.logical} · physical {run.physical}
                  </span>
                  <StateBadge state={statusData?.state} />
                  {statusData?.status && <span className="badge badge-muted">runner status: {statusData.status}</span>}
                  {statusData?.state === "running" && <SourceTag kind="live" />}
                  <span className="note">
                    {status.error ? `status error: ${status.error}` : status.updatedAt ? `updated ${new Date(status.updatedAt).toLocaleTimeString()}` : "loading…"}
                  </span>
                </div>
                {statusData?.failure && <ErrorBox error={`Runner failure: ${statusData.failure}`} action="The run is FAILED_INVALID and will not be admitted. Pick the next free ID pair and retry." />}
                {statusData?.error && <ErrorBox error={statusData.error} />}
                <PhaseTimeline status={statusData} />
              </>
            )}
          </div>

          <div className="card">
            <div className="card-title">Network topology {run && statusData?.state === "running" ? "(live state)" : "(configured)"}</div>
            <TopologyDiagram state={diagramState} />
            <TopologyLegend />
            {!(run && statusData?.state === "running") && (
              <div className="note mt-1">
                No experiment is running for the selected IDs, so link states shown are the configuration, not live network state.
              </div>
            )}
          </div>
        </div>
      </div>

      {run && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <TelemetryChart
            telemetry={(statusData as { telemetry?: never })?.telemetry ?? null}
            metric="tx_throughput_mbps"
            switches={((statusData as { telemetry?: { switches: string[] } })?.telemetry?.switches ?? []).slice(0, 12)}
            title="TX throughput per switch (live)"
            unit=" Mb/s"
          />
          <TelemetryChart
            telemetry={(statusData as { telemetry?: never })?.telemetry ?? null}
            metric="rx_packet_rate"
            switches={((statusData as { telemetry?: { switches: string[] } })?.telemetry?.switches ?? []).slice(0, 12)}
            title="RX packet rate per switch (live)"
            unit=" pkt/s"
          />
        </div>
      )}

      {run && <InferencePanel run={run} status={statusData} />}
    </div>
  );
}

function RunPicker({ switches }: { switches: number }) {
  const { run, setRun } = useSelectedRun();
  const vmRuns = usePoll(`/api/experiments/vm-runs?switches=${switches}`, 15000, switches !== 4);
  const rows = ((vmRuns.data?.runs ?? []) as Array<{ name: string; status: string; logical_experiment_id: number; physical_run_id: number; fault_link?: string }>).slice().reverse();
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="note">Select VM run:</span>
      <select
        className="select"
        style={{ width: "auto" }}
        value={run && run.switches === switches ? run.physical : ""}
        onChange={(e) => {
          const row = rows.find((r) => r.physical_run_id === Number(e.target.value));
          if (row) setRun({ switches, logical: row.logical_experiment_id, physical: row.physical_run_id });
        }}
      >
        <option value="">—</option>
        {rows.map((r) => (
          <option key={r.name} value={r.physical_run_id}>
            {r.name} · {r.status}
            {r.fault_link ? ` · ${r.fault_link}` : ""}
          </option>
        ))}
      </select>
      {run && (
        <button className="btn" style={{ padding: "0.25rem 0.6rem" }} onClick={() => setRun(null)}>
          clear
        </button>
      )}
    </div>
  );
}

function InferencePanel({ run, status }: { run: RunRef; status: StatusLike | null }) {
  const [methods, setMethods] = useState<string[]>(METHOD_ORDER);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [fetchInfo, setFetchInfo] = useState<string | null>(null);
  const health = usePoll("/api/health", 60000);
  const supported: string[] = health.data?.inference?.live_inference?.[String(run.switches)]?.methods ?? [];
  const key = `${run.switches}/${run.logical}/${run.physical}`;

  useEffect(() => {
    setResult(null);
    setError(null);
    setFetchInfo(null);
    apiGet(`${runPath(run)}/inference`).then((r) => {
      if (r?.available) setResult(r);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const finished = status?.state === "complete";

  async function runInference() {
    setBusy(true);
    setError(null);
    try {
      const fetched = await apiPost(`${runPath(run)}/fetch`, {});
      setFetchInfo(fetched.fetched ? `Fetched raw run files into ${fetched.path}` : `Using local copy at ${fetched.path}`);
      const r = await apiPost(`${runPath(run)}/inference`, { methods: methods.filter((m) => supported.includes(m)) });
      setResult(r);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  const experiments = (result?.experiments ?? {}) as Record<string, Record<string, { label: string; ranking: string[]; scores: Record<string, number>; score_semantics: string; ground_truth_retrospective: string | null; rank_of_truth_retrospective: number | null; training: Record<string, unknown>; attribution?: Record<string, unknown>; fault_window_snapshots?: number }>>;
  const expId = Object.keys(experiments)[0];
  const blocks = expId ? experiments[expId] : null;
  const truth = blocks ? Object.values(blocks)[0]?.ground_truth_retrospective : null;

  return (
    <div className="card">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="card-title">Fault localisation inference (current run)</div>
        {result && <SourceTag kind="live" />}
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {METHOD_ORDER.map((m) => (
          <label key={m} className={`inline-flex items-center gap-1 ${supported.includes(m) ? "" : "opacity-40"}`}>
            <input
              type="checkbox"
              disabled={!supported.includes(m)}
              checked={methods.includes(m) && supported.includes(m)}
              onChange={(e) => setMethods(e.target.checked ? [...methods, m] : methods.filter((x) => x !== m))}
            />
            {METHOD_LABELS[m]}
          </label>
        ))}
        <button className="btn btn-primary" onClick={runInference} disabled={busy || !finished || methods.length === 0}>
          {busy ? "Fetching run and running inference…" : "Fetch run and rank candidate links"}
        </button>
        {!finished && <span className="note">Available once the runner reports COMPLETE (the fault window must be fully recorded).</span>}
      </div>
      <div className="note mt-2">
        Pipeline: copy the six raw run files into <span className="mono">dashboard_runs/</span> (isolated from the research datasets) → admit the run
        with <span className="mono">build_topology_candidate</span> → build graph snapshots → Random Forest and the topology ranker are refit on the
        saved admitted candidate ({run.switches}-switch, all its experiments) → GCN / LSTM / GCN+LSTM use saved LOEO fold checkpoints (3 seeds). The fault
        window is the first 10 s of the run&apos;s own annotated fault phase (conditional localisation, not online detection).
      </div>
      {fetchInfo && <div className="note mt-1">{fetchInfo}</div>}
      <ErrorBox error={error} action="If the run was excluded by the validation rules, the reason is shown above; a rejected run cannot be ranked." />
      {blocks && (
        <div className="mt-3">
          <div className="flex flex-wrap items-center gap-3 text-sm mb-3">
            <span>
              Ground truth (retrospective, from the run&apos;s phase events): <span className="mono font-semibold">{truth ?? "unknown"}</span>
            </span>
            <span className="note">
              report {String(result?.report_path)} · {String(result?.elapsed_seconds)} s · generated {String(result?.generated_at)}
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3 gap-4">
            {METHOD_ORDER.filter((m) => blocks[m]).map((m) => {
              const b = blocks[m];
              const hit = b.ranking[0] === truth;
              return (
                <div key={m} className="rounded-lg border p-3" style={{ borderColor: "var(--line)" }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-semibold text-sm">{b.label}</div>
                    <span className={`badge ${hit ? "badge-ok" : "badge-bad"}`}>{hit ? "Top-1 hit" : `truth at rank ${b.rank_of_truth_retrospective ?? "?"}`}</span>
                  </div>
                  <div className="text-sm mb-1">
                    Predicted faulty link: <span className="mono font-semibold">{b.ranking[0]}</span>{" "}
                    <span className="note">score {b.scores[b.ranking[0]].toFixed(4)}</span>
                  </div>
                  <RankingTable block={b} groundTruth={truth} maxRows={4} />
                  <ScoreCaveat text={b.score_semantics} />
                  <div className="note mt-1">
                    Trained on {String(b.training.count)} experiments
                    {b.training.fold ? ` (saved fold ${String(b.training.fold)} checkpoints)` : " (refit now)"}; run {run.logical} not in training.
                    {b.fault_window_snapshots ? ` ${b.fault_window_snapshots} snapshots in the fault window.` : ""}
                  </div>
                  {m === "rf_baseline" && b.attribution && (b.attribution as { available?: boolean }).available && (
                    <div className="mt-2">
                      <div className="label">Top SHAP contributions to the predicted class</div>
                      <ul className="text-xs mono space-y-0.5">
                        {((b.attribution as { top_features: Array<{ feature: string; shap: number; value: number }> }).top_features ?? []).slice(0, 4).map((f) => (
                          <li key={f.feature}>
                            {f.feature}: {f.shap >= 0 ? "+" : ""}
                            {f.shap.toFixed(4)} (value {f.value.toFixed(3)})
                          </li>
                        ))}
                      </ul>
                      <div className="note">Model attribution (TreeSHAP, additivity {String((b.attribution as { additivity_pass: boolean }).additivity_pass)}), not causal evidence.</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
