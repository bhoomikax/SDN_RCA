"use client";

import { fmtNum } from "@/lib/api";

export interface RankingBlock {
  label: string;
  ranking: string[];
  scores: Record<string, number>;
  score_semantics?: string;
  ground_truth_retrospective?: string | null;
  rank_of_truth_retrospective?: number | null;
  training?: Record<string, unknown>;
  fault_window_snapshots?: number;
}

export function RankingTable({ block, groundTruth, maxRows = 5 }: { block: RankingBlock; groundTruth?: string | null; maxRows?: number }) {
  const rows = block.ranking.slice(0, maxRows);
  const maxScore = Math.max(...rows.map((l) => block.scores[l] ?? 0), 1e-9);
  return (
    <table className="data">
      <thead>
        <tr>
          <th>#</th>
          <th>Candidate link</th>
          <th>Ranking score</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((link, i) => {
          const isTruth = groundTruth === link;
          return (
            <tr key={link} style={{ background: i === 0 ? "#f3f7fd" : undefined }}>
              <td className="mono">{i + 1}</td>
              <td className="mono">
                {link}
                {i === 0 && <span className="badge badge-info ml-2">predicted</span>}
                {isTruth && <span className="badge badge-ok ml-2">ground truth</span>}
              </td>
              <td className="mono">{fmtNum(block.scores[link], 4)}</td>
              <td style={{ width: 120 }}>
                <div className="h-2 rounded bg-slate-100">
                  <div className="h-2 rounded" style={{ width: `${(100 * (block.scores[link] ?? 0)) / maxScore}%`, background: "var(--accent)" }} />
                </div>
              </td>
            </tr>
          );
        })}
        {block.ranking.length > maxRows && (
          <tr>
            <td colSpan={4} className="note">
              … {block.ranking.length - maxRows} more candidates ranked below
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

export function ScoreCaveat({ text }: { text?: string }) {
  return (
    <div className="note mt-2">
      Scores are <strong>uncalibrated ranking scores</strong>, not probabilities.{text ? ` ${text}` : ""}
    </div>
  );
}
