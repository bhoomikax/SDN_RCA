"use client";

import { usePoll, API_BASE } from "@/lib/api";
import { ErrorBox, PageHeader } from "@/components/ui";

function Status({ s }: { s?: string }) {
  const cls = s === "Connected" ? "badge-ok" : s === "Disconnected" ? "badge-bad" : s === "Not Tested" ? "badge-muted" : "badge-warn";
  return <span className={`badge ${cls}`}>{s ?? "Unknown"}</span>;
}

export default function HealthPage() {
  const health = usePoll("/api/health", 15000);
  const h = health.data;
  const rows: Array<[string, string | undefined, React.ReactNode]> = h
    ? [
        ["Frontend ↔ backend", "Connected", `${API_BASE} · backend time ${h.backend?.time}`],
        ["SSH key file", h.ssh_key?.status, h.ssh_key?.detail],
        ["SSH to Mininet VM", h.ssh?.status, h.ssh?.detail],
        ["Ryu controller 127.0.0.1:6633 (tested from the VM)", h.controller?.status, `${h.controller?.detail ?? ""} ${h.controller?.process ?? ""}`],
        ["Mininet / Open vSwitch", h.mininet_ovs?.status, `${h.mininet_ovs?.detail ?? ""}${h.mininet_ovs ? ` · sudo -n ${h.mininet_ovs.sudo_nopasswd ? "ok" : "denied"} · iperf ${h.mininet_ovs.iperf ? "ok" : "missing"}` : ""}`],
        ["Runner deployed on VM", h.runner?.status, `${h.runner?.detail ?? ""}${h.runner ? ` · matches local source: ${h.runner.matches_local}` : ""}`],
        ["VM clock", h.vm_clock?.status, h.vm_clock?.detail],
        ["Saved research artifacts", h.saved_artifacts?.status, ""],
        ["Inference libraries", h.inference?.status, `${h.inference?.libraries ?? ""} · shap ${h.inference?.shap ? "ok" : "missing"}`],
      ]
    : [];
  return (
    <div className="space-y-5">
      <PageHeader title="System Health" subtitle="Each row is tested now; nothing is reported green because an address is configured." />
      <ErrorBox error={health.error} action="Start the backend: venv\Scripts\python.exe dashboard\backend\serve.py (port 8765)." />
      {health.error && (
        <div className="card">
          <table className="data"><tbody><tr><td>Frontend ↔ backend</td><td><Status s="Disconnected" /></td><td className="note">{API_BASE}</td></tr></tbody></table>
        </div>
      )}
      {h && (
        <>
          <div className="card">
            <table className="data">
              <thead><tr><th>Component</th><th>Status</th><th>Detail</th></tr></thead>
              <tbody>
                {rows.map(([name, s, detail]) => (
                  <tr key={name}><td>{name}</td><td><Status s={s} /></td><td className="note break-all">{detail}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-title">Telemetry files, checkpoints and inference readiness</div>
            <table className="data">
              <thead><tr><th>Topology</th><th>Candidate</th><th>Graph</th><th>RF/ranker eval</th><th>Neural eval</th><th>Checkpoints</th><th>XAI</th><th>Live inference for new runs</th></tr></thead>
              <tbody>
                {(h.saved_artifacts?.topologies ?? []).map((t: Record<string, unknown>) => {
                  const live = h.inference?.live_inference?.[String(t.switch_count)];
                  const yes = (v: unknown) => <span className={`badge ${v ? "badge-ok" : "badge-bad"}`}>{v ? "present" : "missing"}</span>;
                  return (
                    <tr key={String(t.switch_count)}>
                      <td className="mono">{String(t.switch_count)} switches</td>
                      <td>{yes(t.candidate_present)}</td><td>{yes(t.graph_present)}</td><td>{yes(t.rf_eval_present)}</td><td>{yes(t.neural_eval_present)}</td>
                      <td className="mono">{String(t.checkpoints)}</td><td>{yes(t.xai_present)}</td>
                      <td className="text-xs">{live?.new_runs_supported ? <span className="mono">{live.methods.join(", ")}</span> : <span className="note">{live?.note}</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-title">Active run and storage</div>
            <div className="text-sm">Active dashboard-launched run: <span className="mono">{h.active_run ? h.active_run.name : "none"}</span></div>
            <div className="text-sm">Dashboard run storage (isolated): <span className="mono">{h.dashboard_runs_dir}</span></div>
          </div>
        </>
      )}
    </div>
  );
}
