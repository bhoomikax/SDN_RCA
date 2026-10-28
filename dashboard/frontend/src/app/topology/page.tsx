"use client";

import { useState } from "react";
import { usePoll } from "@/lib/api";
import { useSelectedRun, runPath } from "@/lib/run-selection";
import { TopologyDiagram, TopologyLegend } from "@/components/TopologyDiagram";
import { StatusLike } from "@/components/PhaseTimeline";
import { ErrorBox, PageHeader, SwitchSelect } from "@/components/ui";

export default function TopologyPage() {
  const { run } = useSelectedRun();
  const [switches, setSwitches] = useState(12);
  const topology = usePoll(`/api/topology?switches=${switches}`, 60000);
  const registry = usePoll(`/api/experiments/registry?switches=${switches}`, 30000, switches !== 4);
  const status = usePoll<StatusLike>(run && run.switches === switches ? `${runPath(run)}/status` : null, 3000);
  const live = status.data?.state === "running";
  const t = topology.data;
  const reg = (registry.data?.registry ?? []) as Array<{ logical_experiment_id: number; physical_run_id: number; fault_link: string; vm_status: string | null }>;
  const spec = t
    ? {
        switches,
        bottleneck: t.bottleneck_link,
        configuredFault: run && run.switches === switches ? (status.data?.configured_fault_link ?? reg.find((r) => r.logical_experiment_id === run.logical)?.fault_link ?? null) : null,
        observedFault: status.data?.fault_link_from_events ?? null,
        phase: status.data?.phase ?? null,
      }
    : null;
  return (
    <div className="space-y-5">
      <PageHeader title="Network Topology" subtitle="Linear chain h1 – s1 … sN – h2 with N−1 inter-switch candidate links and a 10 Mbps / 5 ms bottleneck on the middle link." />
      <ErrorBox error={topology.error} />
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <div className="card">
          <div className="card-title">Topology size</div>
          <SwitchSelect value={switches} onChange={setSwitches} />
          {t && (
            <dl className="mt-3 text-sm space-y-1">
              <div className="flex justify-between"><dt className="text-slate-500">Candidate links</dt><dd className="mono">{t.candidate_count}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Bottleneck</dt><dd className="mono">{t.bottleneck_link}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Chance Top-1</dt><dd className="mono">{(t.chance_top1 * 100).toFixed(1)}%</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Random MRR</dt><dd className="mono">{t.chance_mrr.toFixed(3)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Registry</dt><dd className="mono">{t.registry ? `${t.registry.logical_range[0]}–${t.registry.logical_range[1]}` : "exhausted"}</dd></div>
            </dl>
          )}
        </div>
        <div className="card xl:col-span-3">
          <div className="flex items-center justify-between">
            <div className="card-title">{live ? "Live state of the running experiment" : "Configured topology"}</div>
            {run && run.switches === switches ? (
              <span className={`badge ${live ? "badge-info" : "badge-muted"}`}>{live ? `running · phase ${status.data?.phase}` : `selected run ${run.logical}/${run.physical} · ${status.data?.state ?? "…"}`}</span>
            ) : (
              <span className="badge badge-muted">no running experiment for this size</span>
            )}
          </div>
          {spec && <TopologyDiagram state={spec} />}
          <TopologyLegend />
          {!live && <div className="note mt-2">Link states are the configuration from the registry; nothing here is live until a run for the selected IDs is in its fault phase.</div>}
        </div>
      </div>
      {t && (
        <div className="card">
          <div className="card-title">Links</div>
          <table className="data">
            <thead><tr><th>Link</th><th>Type</th><th>Shaping</th><th>Registry slots with this fault link</th></tr></thead>
            <tbody>
              {(t.edges as string[][]).map(([a, b]) => {
                const name = `${a}-${b}`;
                const isCandidate = (t.candidate_links as string[]).includes(name);
                const slots = reg.filter((r) => r.fault_link === name);
                return (
                  <tr key={name}>
                    <td className="mono">{name}</td>
                    <td>{isCandidate ? <span className="badge badge-info">candidate</span> : <span className="badge badge-muted">host link</span>}</td>
                    <td className="mono">{name === t.bottleneck_link ? "bw 10 Mbps, delay 5 ms" : "none"}</td>
                    <td className="mono text-xs">
                      {slots.length ? slots.map((s) => `${s.logical_experiment_id}${s.vm_status ? `(${s.vm_status === "COMPLETE" ? "✓" : s.vm_status === "FAILED_INVALID" ? "✗" : "…"})` : ""}`).join(" ") : "–"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {switches !== 4 && <div className="note mt-2">✓ COMPLETE on the VM, ✗ FAILED_INVALID, … other status; bare numbers are unused registry slots.</div>}
        </div>
      )}
    </div>
  );
}
