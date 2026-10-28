"use client";

import { useState } from "react";
import { usePoll } from "@/lib/api";
import { useSelectedRun, runPath } from "@/lib/run-selection";
import { ErrorBox, PageHeader, SourceTag } from "@/components/ui";

export default function ExperimentsPage() {
  const { run, setRun } = useSelectedRun();
  const history = usePoll("/api/results/history", 30000);
  const logs = usePoll(run ? `${runPath(run)}/logs` : null, run ? 4000 : 0);
  const [tab, setTab] = useState<"vm" | "saved" | "local">("vm");
  const h = history.data;
  return (
    <div className="space-y-5">
      <PageHeader title="Saved Experiments" subtitle="Research runs admitted to the saved datasets, raw VM run directories, and runs fetched by this dashboard. New runs are never merged into the research datasets automatically." />
      <ErrorBox error={history.error} />
      <div className="flex gap-2">
        {(["vm", "saved", "local"] as const).map((t) => (
          <button key={t} className={`btn ${tab === t ? "btn-primary" : ""}`} onClick={() => setTab(t)}>
            {t === "vm" ? "VM run directories" : t === "saved" ? "Admitted research experiments" : "Dashboard-fetched runs"}
          </button>
        ))}
      </div>

      {h && tab === "vm" && (
        <div className="space-y-5">
          {Object.entries(h.vm as Record<string, unknown>).map(([sw, rows]) => (
            <div key={sw} className="card">
              <div className="flex items-center justify-between"><div className="card-title">{sw} switches — runs on the VM</div><SourceTag kind="vm" /></div>
              {Array.isArray(rows) ? (
                <div className="overflow-x-auto">
                  <table className="data">
                    <thead><tr><th>Run</th><th>Status</th><th>Fault link</th><th>Started</th><th>Completed / failed</th><th>Failure</th><th></th></tr></thead>
                    <tbody>
                      {(rows as Array<Record<string, string | number | null>>).slice().reverse().map((r) => (
                        <tr key={String(r.name)}>
                          <td className="mono">{String(r.name)}</td>
                          <td><span className={`badge ${r.status === "COMPLETE" ? "badge-ok" : r.status === "FAILED_INVALID" ? "badge-bad" : "badge-warn"}`}>{String(r.status)}</span></td>
                          <td className="mono">{String(r.fault_link ?? "")}</td>
                          <td className="mono text-xs">{String(r.started_at ?? "")}</td>
                          <td className="mono text-xs">{String(r.completed_at ?? r.failed_at ?? "")}</td>
                          <td className="note">{String(r.failure ?? "")}</td>
                          <td>
                            {r.logical_experiment_id !== null && (
                              <button className="btn" style={{ padding: "0.2rem 0.5rem" }} onClick={() => setRun({ switches: Number(sw), logical: Number(r.logical_experiment_id), physical: Number(r.physical_run_id) })}>
                                inspect
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <ErrorBox error={String((rows as { error: string }).error)} />
              )}
            </div>
          ))}
        </div>
      )}

      {h && tab === "saved" && (
        <div className="space-y-5">
          {(h.saved as Array<Record<string, unknown>>).map((t) => (
            <div key={String(t.switch_count)} className="card">
              <div className="flex items-center justify-between"><div className="card-title">{String(t.label)}</div><SourceTag kind="saved" /></div>
              <div className="note mb-2">
                candidate <span className="mono">{String(t.candidate_dir)}</span> · rows {String(t.rows ?? "–")} · SHA-256 <span className="mono">{String(t.dataset_sha256 ?? "").slice(0, 12)}…</span> · experiments per link{" "}
                <span className="mono">{JSON.stringify(t.experiments_per_link)}</span>
                {t.note ? <div>{String(t.note)}</div> : null}
              </div>
              <div className="overflow-x-auto">
                <table className="data">
                  <thead><tr><th>Experiment</th><th>Physical</th><th>Fault link</th><th>Fault event</th><th>Rows</th><th>Interval (s)</th><th>Window snapshots</th><th>Sender Mbps</th><th>Status</th><th>Run dir</th></tr></thead>
                  <tbody>
                    {(t.experiments as Array<Record<string, unknown>>).map((e) => (
                      <tr key={String(e.experiment_id)}>
                        <td className="mono">{String(e.experiment_id)}</td><td className="mono">{String(e.physical_run_id ?? "–")}</td><td className="mono">{String(e.fault_link)}</td>
                        <td className="mono text-xs">{String(e.fault_event ?? "–")}</td><td className="mono">{String(e.telemetry_rows ?? "–")}</td><td className="mono">{String(e.median_sample_interval_seconds ?? "–")}</td>
                        <td className="mono">{String(e.fault_window_10s_timestamps ?? "–")}</td><td className="mono">{String(e.iperf_sender_mbps ?? "–")}</td><td><span className="badge badge-ok">{String(e.status)}</span></td><td className="note">{String(e.run_dir ?? "")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {Array.isArray(t.excluded) && (t.excluded as unknown[]).length > 0 && (
                <details className="mt-2">
                  <summary className="note cursor-pointer">{(t.excluded as unknown[]).length} excluded runs (with reasons)</summary>
                  <table className="data mt-1">
                    <thead><tr><th>Run dir</th><th>Metadata status</th><th>Reason</th></tr></thead>
                    <tbody>{(t.excluded as Array<Record<string, string>>).map((x) => (<tr key={x.run_dir}><td className="mono text-xs">{x.run_dir}</td><td className="mono">{x.metadata_status}</td><td className="note">{x.reason}</td></tr>))}</tbody>
                  </table>
                </details>
              )}
            </div>
          ))}
        </div>
      )}

      {h && tab === "local" && (
        <div className="card">
          <div className="flex items-center justify-between"><div className="card-title">Runs fetched into {String(h.dashboard_runs?.root ?? "dashboard_runs/")} (isolated)</div><SourceTag kind="local" /></div>
          {(h.dashboard_runs as Array<Record<string, unknown>>).length === 0 ? (
            <div className="note">No runs fetched yet. Use “Fetch run and rank candidate links” on the Live Demo page.</div>
          ) : (
            <table className="data">
              <thead><tr><th>Run</th><th>Switches</th><th>Status</th><th>Fault link</th><th>Candidate built</th><th>Inference reports</th><th></th></tr></thead>
              <tbody>
                {(h.dashboard_runs as Array<Record<string, unknown>>).map((r) => (
                  <tr key={String(r.path)}>
                    <td className="mono">{String(r.name)}</td><td className="mono">{String(r.switch_count)}</td>
                    <td><span className={`badge ${r.status === "COMPLETE" ? "badge-ok" : "badge-bad"}`}>{String(r.status)}</span></td>
                    <td className="mono">{String(r.fault_link ?? "")}</td><td>{r.derived_candidate ? "yes" : "no"}</td>
                    <td className="mono text-xs">{(r.inference_reports as string[]).join(", ") || "–"}</td>
                    <td><button className="btn" style={{ padding: "0.2rem 0.5rem" }} onClick={() => setRun({ switches: Number(r.switch_count), logical: Number(r.logical_experiment_id), physical: Number(r.physical_run_id) })}>inspect</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div className="card">
        <div className="flex items-center justify-between">
          <div className="card-title">Logs for selected run {run ? `(${run.switches} sw · ${run.logical}/${run.physical})` : ""}</div>
          {logs.updatedAt && <span className="note">updated {new Date(logs.updatedAt).toLocaleTimeString()}</span>}
        </div>
        {!run && <div className="note">Select a run (inspect) to see its runner log and iperf logs.</div>}
        <ErrorBox error={logs.error} />
        {logs.data && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div>
              <div className="label">Runner stdout/stderr (dashboard-launched runs only)</div>
              <pre className="log">{logs.data.log || (logs.data.dashboard_launched ? "(empty so far)" : "(not a dashboard-launched run; runner console output was not captured by the dashboard — see the VM batch logs)")}</pre>
            </div>
            <div>
              <div className="label">iperf client log</div>
              <pre className="log">{logs.data.iperf_client_log ?? "(not available)"}</pre>
            </div>
            <div>
              <div className="label">iperf server log</div>
              <pre className="log">{logs.data.iperf_server_log ?? "(not available)"}</pre>
            </div>
          </div>
        )}
        {logs.data && (
          <div className="note mt-2">
            state {String(logs.data.state)} · runner status {String(logs.data.status)} · failure {String(logs.data.failure ?? "none")}
          </div>
        )}
      </div>
    </div>
  );
}
