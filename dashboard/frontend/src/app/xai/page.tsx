"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { apiGet, errorText, usePoll, fmtNum, METHOD_ORDER, METHOD_LABELS } from "@/lib/api";
import { ErrorBox, PageHeader, SourceTag, SwitchSelect } from "@/components/ui";
import { RankingTable, ScoreCaveat } from "@/components/RankingTable";

function SignedBars({ data, title }: { data: Array<{ name: string; value: number }>; title: string }) {
  return (
    <div>
      <div className="label">{title}</div>
      <div style={{ width: "100%", height: 170 }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#eef1f5" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={48} />
            <YAxis tick={{ fontSize: 10 }} width={48} />
            <Tooltip formatter={(v: number) => fmtNum(v, 4)} contentStyle={{ fontSize: 12 }} />
            <Bar dataKey="value" isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={i} fill={d.value >= 0 ? "#1f5fbf" : "#d7263d"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function XaiPage() {
  const index = usePoll("/api/results/xai", 600000);
  const [switches, setSwitches] = useState(8);
  const [experiment, setExperiment] = useState<number | null>(104);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showMd, setShowMd] = useState(false);
  const topo = useMemo(() => (index.data?.topologies ?? []).find((t: { switch_count: number }) => t.switch_count === switches), [index.data, switches]);
  const experiments: number[] = topo?.experiments ?? [];

  useEffect(() => {
    if (experiments.length && (experiment === null || !experiments.includes(experiment))) setExperiment(experiments[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [switches, experiments.length]);

  useEffect(() => {
    if (experiment === null || !experiments.includes(experiment)) return;
    setReport(null);
    setError(null);
    apiGet(`/api/results/xai/${switches}/${experiment}`).then(setReport).catch((e) => setError(errorText(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [switches, experiment, experiments.length]);

  const methods = (report?.methods ?? {}) as Record<string, Record<string, unknown>>;
  return (
    <div className="space-y-5">
      <PageHeader title="XAI / Explainability" subtitle="Saved per-experiment explanation reports with validation checks. Attributions describe each model's score function; they are not causal evidence." right={<SourceTag kind="saved" />} />
      <ErrorBox error={index.error ?? error} />
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-5">
        <div className="card space-y-3">
          <div><span className="label">Topology</span><SwitchSelect value={switches} onChange={setSwitches} /></div>
          <div>
            <span className="label">Experiment (saved report)</span>
            <select className="select mono" value={experiment ?? ""} onChange={(e) => setExperiment(Number(e.target.value))}>
              {experiments.map((id) => (
                <option key={id} value={id}>experiment_{id}{switches === 8 && id === 104 ? " (worked example)" : ""}</option>
              ))}
            </select>
          </div>
          {topo && (
            <div className="note">
              {experiments.length} reports · IG steps {topo.ig_steps} · source <span className="mono">{topo.source}</span>
              <div className="mt-1">Validation pass counts: {Object.entries(topo.validation ?? {}).map(([m, v]) => `${METHOD_LABELS[m] ?? m} ${(v as { validation_pass_count: number; explained: number }).validation_pass_count}/${(v as { explained: number }).explained}`).join(" · ")}</div>
            </div>
          )}
          {report && (
            <div className="callout">
              Report for <strong>{String(report.switch_count)}-switch experiment {String(report.experiment_id)}</strong> ·{" "}
              <span className="mono">{String(report.source_json)}</span>
            </div>
          )}
        </div>
        <div className="xl:col-span-3 space-y-5">
          {report &&
            METHOD_ORDER.filter((m) => methods[m]).map((m) => {
              const b = methods[m] as {
                label: string; ranking: string[]; scores: Record<string, number>; ground_truth: string; top1_correct: boolean; rank_of_truth: number;
                explanation_method: string; score_semantics: string; validation: Record<string, unknown>; limitations?: string[];
                predicted_class_attribution?: { class: string; top_features: Array<{ feature: string; shap: number; value: number }>; support_by_switch: Record<string, number> };
                ig_per_switch_signed?: Record<string, number>; ig_per_feature_signed?: Record<string, number>; ig_per_timestep_signed?: number[];
                occlusion?: { switch_zeroed_delta?: Record<string, number> };
                component_table?: Record<string, Record<string, number>>; deciding_components_for_top1?: unknown; main_supporting_evidence?: unknown;
                fold?: { train_experiment_ids: number[] };
              };
              const v = b.validation ?? {};
              const passKeys = Object.entries(v).filter(([k]) => k.endsWith("_pass"));
              return (
                <div key={m} className="card">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="font-semibold">{b.label}</div>
                    <div className="flex gap-2">
                      <span className={`badge ${b.top1_correct ? "badge-ok" : "badge-bad"}`}>{b.top1_correct ? "Top-1 correct" : `truth at rank ${b.rank_of_truth}`}</span>
                      {passKeys.map(([k, val]) => (
                        <span key={k} className={`badge ${val ? "badge-ok" : "badge-bad"}`}>{k.replace("_pass", "")} {val ? "pass" : "fail"}</span>
                      ))}
                    </div>
                  </div>
                  <div className="note mt-1">{b.explanation_method}</div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3">
                    <div>
                      <div className="label">Ranking (ground truth: <span className="mono">{b.ground_truth}</span>)</div>
                      <RankingTable block={{ label: b.label, ranking: b.ranking, scores: b.scores }} groundTruth={b.ground_truth} maxRows={5} />
                      <ScoreCaveat text={b.score_semantics} />
                      {b.fold && <div className="note">Training fold: {b.fold.train_experiment_ids.length} experiments; experiment {String(report.experiment_id)} held out.</div>}
                    </div>
                    <div className="space-y-3">
                      {b.predicted_class_attribution && (
                        <>
                          <SignedBars title={`SHAP — top features for predicted class ${b.predicted_class_attribution.class}`} data={b.predicted_class_attribution.top_features.map((f) => ({ name: f.feature, value: f.shap }))} />
                          <SignedBars title="SHAP support by switch" data={Object.entries(b.predicted_class_attribution.support_by_switch).map(([k, val]) => ({ name: k, value: val }))} />
                        </>
                      )}
                      {b.ig_per_switch_signed && (
                        <>
                          <SignedBars title="Integrated gradients — signed attribution per switch" data={Object.entries(b.ig_per_switch_signed).sort((a, c) => Number(a[0].slice(1)) - Number(c[0].slice(1))).map(([k, val]) => ({ name: k, value: val }))} />
                          <SignedBars title="Integrated gradients — per feature" data={Object.entries(b.ig_per_feature_signed ?? {}).map(([k, val]) => ({ name: k, value: val }))} />
                        </>
                      )}
                      {b.component_table && (
                        <div>
                          <div className="label">Heuristic components (rank utilities averaged with equal weight)</div>
                          <div className="overflow-x-auto">
                            <table className="data">
                              <thead><tr><th>Link</th>{Object.keys(Object.values(b.component_table)[0] ?? {}).filter((k) => ["link_anomaly", "endpoint_imbalance", "pair_onset_seconds", "propagation_margin_seconds", "rank_score"].includes(k)).map((k) => <th key={k}>{k}</th>)}</tr></thead>
                              <tbody>
                                {Object.entries(b.component_table).map(([link, comps]) => (
                                  <tr key={link}><td className="mono">{link}</td>{["link_anomaly", "endpoint_imbalance", "pair_onset_seconds", "propagation_margin_seconds", "rank_score"].filter((k) => k in comps).map((k) => <td key={k} className="mono">{fmtNum(comps[k], 3)}</td>)}</tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <div className="note">Deciding components for top-1: <span className="mono">{JSON.stringify(b.deciding_components_for_top1)}</span></div>
                        </div>
                      )}
                    </div>
                  </div>
                  {b.limitations && (
                    <ul className="note mt-2 list-disc pl-5">
                      {b.limitations.map((l) => (<li key={l}>{l}</li>))}
                    </ul>
                  )}
                  <details className="mt-2">
                    <summary className="note cursor-pointer">Validation details</summary>
                    <pre className="log mt-1">{JSON.stringify(v, null, 2)}</pre>
                  </details>
                </div>
              );
            })}
          {typeof report?.markdown === "string" && (
            <div className="card">
              <button className="btn" onClick={() => setShowMd(!showMd)}>{showMd ? "Hide" : "Show"} original Markdown report</button>
              {showMd && <pre className="log mt-2" style={{ maxHeight: "40rem" }}>{String(report.markdown)}</pre>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
