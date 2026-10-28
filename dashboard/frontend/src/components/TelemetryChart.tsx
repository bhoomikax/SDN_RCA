"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TelemetrySeries {
  rows: number;
  skipped: number;
  schema_ok: boolean | null;
  switches: string[];
  series: Array<Record<string, string | number>>;
  latest: Array<Record<string, string | number>>;
  first_timestamp?: string | null;
  last_timestamp?: string | null;
}

const PALETTE = ["#1f5fbf", "#d7263d", "#1f8a4c", "#e8a317", "#7b3fa0", "#0d9488", "#b45309", "#64748b", "#be185d", "#2563eb", "#15803d", "#9333ea"];

export function TelemetryChart({
  telemetry,
  metric,
  switches,
  title,
  unit,
}: {
  telemetry: TelemetrySeries | null;
  metric: string;
  switches: string[];
  title: string;
  unit: string;
}) {
  const data = useMemo(() => {
    if (!telemetry?.series?.length) return [];
    const t0 = Date.parse(String(telemetry.series[0].timestamp));
    return telemetry.series.map((row): Record<string, string | number> & { t: number } => ({
      ...row,
      t: Number.isNaN(t0) ? 0 : (Date.parse(String(row.timestamp)) - t0) / 1000,
    }));
  }, [telemetry]);
  const bands = useMemo(() => {
    const out: Array<{ phase: string; x1: number; x2: number }> = [];
    let current: { phase: string; x1: number; x2: number } | null = null;
    for (const row of data) {
      const phase = String(row.phase);
      if (!current || current.phase !== phase) {
        if (current) out.push(current);
        current = { phase, x1: row.t as number, x2: row.t as number };
      } else {
        current.x2 = row.t as number;
      }
    }
    if (current) out.push(current);
    return out;
  }, [data]);

  if (!telemetry || !telemetry.series?.length) {
    return (
      <div className="card">
        <div className="card-title">{title}</div>
        <div className="note">No telemetry rows available yet. Telemetry appears about one second after the collector starts.</div>
      </div>
    );
  }
  return (
    <div className="card">
      <div className="flex items-baseline justify-between">
        <div className="card-title">{title}</div>
        <div className="note">
          {telemetry.rows} rows · {telemetry.series.length} samples{telemetry.skipped ? ` · ${telemetry.skipped} unparsable rows skipped` : ""}
        </div>
      </div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#eef1f5" />
            {bands.map((b, i) => (
              <ReferenceArea
                key={i}
                x1={b.x1}
                x2={b.x2}
                fill={b.phase === "fault" ? "#d7263d" : b.phase === "recovery" ? "#1f8a4c" : b.phase === "normal" ? "#1f5fbf" : "#94a3b8"}
                fillOpacity={0.06}
                label={{ value: b.phase, position: "insideTop", fontSize: 10, fill: "#64748b" }}
              />
            ))}
            <XAxis dataKey="t" type="number" domain={["dataMin", "dataMax"]} tick={{ fontSize: 11 }} unit="s" />
            <YAxis tick={{ fontSize: 11 }} unit={unit} width={56} />
            <Tooltip
              formatter={(value: number | string) => (typeof value === "number" ? value.toFixed(3) : value)}
              labelFormatter={(label) => `t = ${Number(label).toFixed(1)} s`}
              contentStyle={{ fontSize: 12 }}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {switches.map((sw, i) => (
              <Line
                key={sw}
                type="monotone"
                dataKey={`${sw}.${metric}`}
                name={sw}
                stroke={PALETTE[i % PALETTE.length]}
                dot={false}
                strokeWidth={1.6}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="note mt-1">
        Per-switch value = sum over the switch&apos;s numbered ports (LOCAL excluded), as in the research graph builder. x-axis is
        seconds since the first telemetry sample (VM clock).
      </div>
    </div>
  );
}
