"use client";

import { useState } from "react";
import { usePoll } from "@/lib/api";
import { useSelectedRun, runPath, runName } from "@/lib/run-selection";
import { TelemetryChart, TelemetrySeries } from "@/components/TelemetryChart";
import { ErrorBox, PageHeader, SourceTag } from "@/components/ui";

const METRICS: Array<{ key: string; label: string; unit: string }> = [
  { key: "tx_throughput_mbps", label: "TX throughput", unit: " Mb/s" },
  { key: "rx_throughput_mbps", label: "RX throughput", unit: " Mb/s" },
  { key: "tx_packet_rate", label: "TX packet rate", unit: " pkt/s" },
  { key: "rx_packet_rate", label: "RX packet rate", unit: " pkt/s" },
];

export default function TelemetryPage() {
  const { run } = useSelectedRun();
  const [selected, setSelected] = useState<string[] | null>(null);
  const data = usePoll(run ? `${runPath(run)}/telemetry?source=auto` : null, 4000);
  const telemetry = (data.data?.telemetry ?? null) as TelemetrySeries | null;
  const switches = telemetry?.switches ?? [];
  const shown = selected ?? switches;
  if (!run) {
    return (
      <div className="space-y-5">
        <PageHeader title="Live Telemetry" />
        <div className="card note">No run selected. Choose a run on the Live Demo page.</div>
      </div>
    );
  }
  return (
    <div className="space-y-5">
      <PageHeader
        title="Live Telemetry"
        subtitle={`Run ${runName(run)} · per-port OVS counters polled by telemetry.py (~1 s, grows with switch count).`}
        right={data.data?.source ? <SourceTag kind={data.data.source === "vm" ? "vm" : "local"} /> : null}
      />
      <ErrorBox error={data.error} />
      {data.data && !data.data.available && <div className="card note">The run directory does not exist yet (on the VM or locally). Waiting for telemetry…</div>}
      {telemetry && (
        <>
          <div className="card">
            <div className="flex flex-wrap items-center gap-4 text-sm">
              <span>rows <span className="mono">{telemetry.rows}</span></span>
              <span>samples <span className="mono">{telemetry.series.length}</span></span>
              <span>skipped <span className="mono">{telemetry.skipped}</span></span>
              <span>schema <span className={`badge ${telemetry.schema_ok ? "badge-ok" : "badge-bad"}`}>{telemetry.schema_ok ? "ok" : "mismatch"}</span></span>
              <span>status <span className="mono">{data.data?.status ?? "–"}</span></span>
              <span>first <span className="mono">{telemetry.first_timestamp ?? "–"}</span></span>
              <span>last <span className="mono">{telemetry.last_timestamp ?? "–"}</span></span>
              <span className="note">{data.updatedAt ? `updated ${new Date(data.updatedAt).toLocaleTimeString()}` : ""}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {switches.map((sw) => (
                <label key={sw} className="inline-flex items-center gap-1">
                  <input type="checkbox" checked={shown.includes(sw)} onChange={(e) => setSelected(e.target.checked ? [...shown, sw] : shown.filter((s) => s !== sw))} />
                  {sw}
                </label>
              ))}
              {selected && <button className="underline" onClick={() => setSelected(null)}>all</button>}
            </div>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            {METRICS.map((m) => (
              <TelemetryChart key={m.key} telemetry={telemetry} metric={m.key} switches={shown} title={m.label} unit={m.unit} />
            ))}
          </div>
          <div className="card">
            <div className="card-title">Latest sample — per-port counters ({telemetry.last_timestamp})</div>
            <div className="overflow-x-auto">
              <table className="data">
                <thead>
                  <tr>
                    <th>Switch</th><th>Port</th><th>Interface</th><th>rx_packets</th><th>tx_packets</th><th>rx_bytes</th><th>tx_bytes</th><th>rx_dropped</th><th>tx_dropped</th><th>rx pkt/s</th><th>tx pkt/s</th><th>rx Mb/s</th><th>tx Mb/s</th>
                  </tr>
                </thead>
                <tbody>
                  {telemetry.latest.map((r, i) => (
                    <tr key={i} className="mono">
                      <td>{r.switch}</td><td>{r.port}</td><td>{r.interface_name}</td>
                      <td>{r.rx_packets}</td><td>{r.tx_packets}</td><td>{r.rx_bytes}</td><td>{r.tx_bytes}</td><td>{r.rx_dropped}</td><td>{r.tx_dropped}</td>
                      <td>{Number(r.rx_packet_rate).toFixed(1)}</td><td>{Number(r.tx_packet_rate).toFixed(1)}</td><td>{Number(r.rx_throughput_mbps).toFixed(3)}</td><td>{Number(r.tx_throughput_mbps).toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
