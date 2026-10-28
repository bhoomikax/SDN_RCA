"use client";

import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { usePoll, fmtPct, fmtNum, METHOD_ORDER, METHOD_LABELS } from "@/lib/api";
import { ErrorBox, PageHeader, SourceTag } from "@/components/ui";

interface Row {
  topology: string;
  switch_count: number;
  candidate_links: number;
  model: string;
  method: string;
  valid_experiments: number;
  top1_count: number;
  top2_count: number;
  mrr: number;
  top1_wilson95: [number, number];
  chance_top1: number;
  chance_mrr: number;
  xai_status: string;
  top1_fraction: number;
  top2_fraction: number;
}

const COLORS: Record<string, string> = { rf_baseline: "#1f5fbf", topology_link_ranker: "#94a3b8", graph_only: "#1f8a4c", temporal_only: "#7b3fa0", graph_temporal: "#e8a317" };

export default function ComparisonPage() {
  const data = usePoll("/api/results/comparison", 600000);
  const rows = (data.data?.rows ?? []) as Row[];
  const topologies = [4, 8, 12];
  const chart = (metric: "top1_fraction" | "mrr") =>
    topologies.map((n) => {
      const entry: Record<string, number | string> = { topology: `${n} sw (K=${n - 1})` };
      rows.filter((r) => r.switch_count === n).forEach((r) => (entry[r.method] = r[metric]));
      const chance = rows.find((r) => r.switch_count === n);
      entry.chance = metric === "top1_fraction" ? chance?.chance_top1 ?? 0 : chance?.chance_mrr ?? 0;
      return entry;
    });
  return (
    <div className="space-y-5">
      <PageHeader
        title="Model Comparison"
        subtitle="Five localisation methods on 4-, 8- and 12-switch topologies under experiment-grouped leave-one-experiment-out evaluation."
        right={<SourceTag kind="saved" />}
      />
      <ErrorBox error={data.error} />
      {data.data && (
        <>
          <div className="callout">
            <strong>How to read this.</strong> Chance Top-1 is 1 / K for K candidate links: 1/3, 1/7 and 1/11 for 4, 8 and 12 switches; random MRR is
            0.611, 0.370 and 0.275. Raw accuracies across topology sizes are not comparable at face value and must be read against these baselines.
            Experiments are the independent units (seeds and folds are not). All scores are uncalibrated ranking scores and the fault window is
            oracle-selected. Source: <span className="mono">{data.data.source}</span>.
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            {(["top1_fraction", "mrr"] as const).map((metric) => (
              <div key={metric} className="card">
                <div className="card-title">{metric === "top1_fraction" ? "Top-1 accuracy vs chance" : "Mean reciprocal rank vs random ranking"}</div>
                <div style={{ width: "100%", height: 280 }}>
                  <ResponsiveContainer>
                    <BarChart data={chart(metric)} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                      <CartesianGrid stroke="#eef1f5" />
                      <XAxis dataKey="topology" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v) => (metric === "top1_fraction" ? `${Math.round(v * 100)}%` : v.toFixed(2))} />
                      <Tooltip formatter={(v: number) => (metric === "top1_fraction" ? fmtPct(v, 1) : fmtNum(v, 4))} contentStyle={{ fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      {METHOD_ORDER.map((m) => (
                        <Bar key={m} dataKey={m} name={METHOD_LABELS[m]} fill={COLORS[m]} isAnimationActive={false} />
                      ))}
                      <Bar dataKey="chance" name="uniform chance" fill="#000" fillOpacity={0.15} isAnimationActive={false} />
                      {metric === "top1_fraction" && <ReferenceLine y={1 / 3} stroke="#999" strokeDasharray="3 3" />}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ))}
          </div>
          {topologies.map((n) => {
            const subset = rows.filter((r) => r.switch_count === n);
            const first = subset[0];
            return (
              <div key={n} className="card">
                <div className="flex items-baseline justify-between">
                  <div className="card-title">{n} switches</div>
                  {first && (
                    <div className="note">
                      {first.valid_experiments} valid independent experiments · {first.candidate_links} candidate links · chance Top-1 {fmtPct(first.chance_top1, 1)} · random
                      MRR {fmtNum(first.chance_mrr, 3)}
                    </div>
                  )}
                </div>
                <table className="data">
                  <thead>
                    <tr><th>Model</th><th>Top-1</th><th>Top-2</th><th>MRR</th><th>Top-1 Wilson 95% CI</th><th>Chance Top-1 / MRR</th><th>XAI validation</th></tr>
                  </thead>
                  <tbody>
                    {subset.map((r) => (
                      <tr key={r.method}>
                        <td>{r.model}</td>
                        <td className="mono">{r.top1_count}/{r.valid_experiments} ({fmtPct(r.top1_fraction)})</td>
                        <td className="mono">{r.top2_count}/{r.valid_experiments} ({fmtPct(r.top2_fraction)})</td>
                        <td className="mono">{fmtNum(r.mrr, 4)}</td>
                        <td className="mono">[{fmtPct(r.top1_wilson95[0], 1)}, {fmtPct(r.top1_wilson95[1], 1)}]</td>
                        <td className="mono">{fmtNum(r.chance_top1, 3)} / {fmtNum(r.chance_mrr, 3)}</td>
                        <td className="note">{r.xai_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
          <div className="callout callout-warn">
            Intervals overlap heavily among the learned models; no superiority claim is made. The fixed topology heuristic does not transfer beyond 4
            switches (its threshold is never crossed in the fault window and its imbalance term penalises the true link). See
            <span className="mono"> docs/RESULTS_TOPOLOGY_SCALING.md</span> and <span className="mono">results/audit/methodology_audit.md</span>.
          </div>
        </>
      )}
    </div>
  );
}
