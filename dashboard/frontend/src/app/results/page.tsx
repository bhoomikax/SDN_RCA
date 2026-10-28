"use client";

import { useState } from "react";
import { usePoll, fmtPct, fmtNum, METHOD_ORDER, METHOD_LABELS } from "@/lib/api";
import { ErrorBox, PageHeader, SourceTag, SwitchSelect } from "@/components/ui";

export default function ResultsPage() {
  const [switches, setSwitches] = useState(12);
  const [method, setMethod] = useState("graph_only");
  const data = usePoll(`/api/results/evaluation?switches=${switches}`, 600000);
  const d = data.data;
  const block = d?.methods?.[method];
  return (
    <div className="space-y-5">
      <PageHeader title="Model Results" subtitle="Per-method metrics and per-experiment rankings from the saved grouped LOEO evaluations." right={<SourceTag kind="saved" />} />
      <ErrorBox error={data.error} />
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <div className="card space-y-3">
          <div>
            <span className="label">Topology</span>
            <SwitchSelect value={switches} onChange={setSwitches} />
          </div>
          <div>
            <span className="label">Method</span>
            <select className="select" value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHOD_ORDER.map((m) => (
                <option key={m} value={m}>{METHOD_LABELS[m]}</option>
              ))}
            </select>
          </div>
          {d && (
            <div className="note">
              {d.label}. {d.experiment_ids?.length} experiments; class support {JSON.stringify(d.class_support)}. Candidate SHA-256{" "}
              <span className="mono">{String(d.candidate_sha256).slice(0, 12)}…</span>
              <br />
              {d.protocol}
            </div>
          )}
        </div>
        <div className="card xl:col-span-3">
          <div className="card-title">Summary — all methods</div>
          {d && (
            <table className="data">
              <thead><tr><th>Method</th><th>Top-1</th><th>Top-2</th><th>Top-3</th><th>MRR</th><th>Top-1 Wilson 95%</th><th>Adjacent-link errors</th><th>Per-seed Top-1</th></tr></thead>
              <tbody>
                {METHOD_ORDER.map((m) => {
                  const b = d.methods[m];
                  return (
                    <tr key={m} style={{ background: m === method ? "#f3f7fd" : undefined }}>
                      <td><button className="underline" onClick={() => setMethod(m)}>{METHOD_LABELS[m]}</button></td>
                      <td className="mono">{b.top1_count}/{b.support} ({fmtPct(b.top1)})</td>
                      <td className="mono">{b.top2_count}/{b.support} ({fmtPct(b.top2)})</td>
                      <td className="mono">{b.top3_count ?? "–"}/{b.support}</td>
                      <td className="mono">{fmtNum(b.mrr, 4)}</td>
                      <td className="mono">{b.top1_wilson95 ? `[${fmtPct(b.top1_wilson95[0], 1)}, ${fmtPct(b.top1_wilson95[1], 1)}]` : "–"}</td>
                      <td className="mono">{b.adjacent_link_error_fraction === null || b.adjacent_link_error_fraction === undefined ? "no errors" : fmtPct(b.adjacent_link_error_fraction)}</td>
                      <td className="mono">{b.per_seed_top1 ? Object.values(b.per_seed_top1).join(" / ") : "–"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {d && (
            <div className="note mt-2">
              Chance: Top-1 {fmtPct(d.methods.rf_baseline.chance?.uniform_top1, 1)}, MRR {fmtNum(d.methods.rf_baseline.chance?.uniform_mrr, 3)}. {d.score_semantics}
            </div>
          )}
        </div>
      </div>
      {block && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="card">
            <div className="card-title">{METHOD_LABELS[method]} — per-class Top-1 recall</div>
            <table className="data">
              <thead><tr><th>Link</th><th>Support</th><th>Recall</th><th>Precision</th><th>Mean rank</th></tr></thead>
              <tbody>
                {Object.entries(block.per_class ?? {}).map(([link, v]) => {
                  const c = v as { support: number; top1_recall: number; top1_precision: number; mean_rank: number | null };
                  return (
                    <tr key={link}><td className="mono">{link}</td><td className="mono">{c.support}</td><td className="mono">{fmtPct(c.top1_recall)}</td><td className="mono">{fmtPct(c.top1_precision)}</td><td className="mono">{c.mean_rank === null ? "–" : c.mean_rank.toFixed(2)}</td></tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="card xl:col-span-2">
            <div className="card-title">{METHOD_LABELS[method]} — confusion (rows: actual, columns: rank-1)</div>
            <div className="overflow-x-auto">
              <table className="data">
                <thead><tr><th></th>{(block.confusion_labels ?? []).map((l: string) => <th key={l} className="mono">{l}</th>)}</tr></thead>
                <tbody>
                  {(block.confusion_matrix ?? []).map((row: number[], i: number) => (
                    <tr key={i}>
                      <td className="mono">{block.confusion_labels[i]}</td>
                      {row.map((v, j) => (
                        <td key={j} className="mono" style={{ background: v ? (i === j ? "#e6f4ec" : "#fdebee") : undefined, textAlign: "center" }}>{v || ""}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
      {d && (
        <div className="card">
          <div className="card-title">Per-experiment rankings ({METHOD_LABELS[method]})</div>
          <div className="overflow-x-auto">
            <table className="data">
              <thead><tr><th>Experiment</th><th>Ground truth</th><th>Rank-1</th><th>Rank-2</th><th>Rank-3</th><th>Rank of truth</th><th>Top-1 score</th><th>Training experiments</th></tr></thead>
              <tbody>
                {d.per_experiment.map((e: { experiment_id: number; actual_link: string; methods: Record<string, { ranking: string[]; scores: Record<string, number>; rank: number; top1_hit: boolean; train_experiment_ids?: number[] }> }) => {
                  const r = e.methods[method];
                  if (!r) return null;
                  return (
                    <tr key={e.experiment_id}>
                      <td className="mono">{e.experiment_id}</td>
                      <td className="mono">{e.actual_link}</td>
                      <td className="mono">{r.ranking[0]} {r.top1_hit ? <span className="badge badge-ok">hit</span> : <span className="badge badge-bad">miss</span>}</td>
                      <td className="mono">{r.ranking[1]}</td>
                      <td className="mono">{r.ranking[2]}</td>
                      <td className="mono">{r.rank}</td>
                      <td className="mono">{fmtNum(r.scores[r.ranking[0]], 4)}</td>
                      <td className="note">{r.train_experiment_ids ? `${r.train_experiment_ids.length} (held-out excluded)` : `${d.experiment_ids.length - 1} (held-out excluded)`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
