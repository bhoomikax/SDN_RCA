"use client";

const PHASES: Array<{ key: "normal" | "fault" | "recovery"; title: string; blurb: string }> = [
  { key: "normal", title: "1 · Normal phase", blurb: "Baseline telemetry; link up" },
  { key: "fault", title: "2 · Fault phase", blurb: "Configured link set down; telemetry continues" },
  { key: "recovery", title: "3 · Recovery phase", blurb: "Link restored; observe recovery" },
];

export interface StatusLike {
  state?: string;
  status?: string | null;
  phase?: string | null;
  phase_elapsed_seconds?: number | null;
  phase_durations_seconds?: Record<string, number> | null;
  phase_events?: Record<string, string>;
  vm_time?: string | null;
  telemetry_rows?: number;
  failure?: string | null;
  fault_link_from_events?: string | null;
  configured_fault_link?: string | null;
  runner_process_pids?: number[];
  error?: string;
}

function secondsBetween(a?: string, b?: string | null) {
  if (!a || !b) return null;
  const t1 = Date.parse(a.replace(/([+-]\d\d:\d\d)$/, ""));
  const t2 = Date.parse(b.replace(/([+-]\d\d:\d\d)$/, ""));
  if (Number.isNaN(t1) || Number.isNaN(t2)) return null;
  return Math.max(0, (t2 - t1) / 1000);
}

export function PhaseTimeline({ status }: { status: StatusLike | null }) {
  const events = status?.phase_events ?? {};
  const durations = status?.phase_durations_seconds ?? { normal: 20, fault: 20, recovery: 20 };
  const order = ["normal", "fault", "recovery"] as const;
  const current = status?.phase ?? null;
  const running = status?.state === "running";
  return (
    <div>
      <div className="grid grid-cols-3 gap-3">
        {PHASES.map((p, idx) => {
          const started = events[p.key];
          const next = idx < 2 ? events[order[idx + 1]] : null;
          let elapsed: number | null = null;
          let done = false;
          if (started && next) {
            elapsed = secondsBetween(started, next);
            done = true;
          } else if (started && p.key === current) {
            elapsed = status?.phase_elapsed_seconds ?? secondsBetween(started, status?.vm_time ?? null);
            if (status?.state === "complete" || status?.state === "failed") done = true;
          }
          const planned = durations[p.key] ?? 20;
          const pct = elapsed === null ? 0 : Math.min(100, (elapsed / planned) * 100);
          const isCurrent = current === p.key && running;
          return (
            <div
              key={p.key}
              className="rounded-lg border p-3"
              style={{
                borderColor: isCurrent ? (p.key === "fault" ? "var(--fault)" : "var(--accent)") : "var(--line)",
                background: isCurrent ? (p.key === "fault" ? "#fdf1f3" : "#f3f7fd") : "#fff",
              }}
            >
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold">{p.title}</div>
                <span
                  className={`badge ${
                    done ? "badge-ok" : isCurrent ? (p.key === "fault" ? "badge-bad" : "badge-info") : "badge-muted"
                  }`}
                >
                  {done ? "done" : isCurrent ? "in progress" : started ? "recorded" : "pending"}
                </span>
              </div>
              <div className="note mt-1">{p.blurb}</div>
              <div className="mt-2 h-2 rounded bg-slate-100 overflow-hidden">
                <div
                  className="h-2 rounded"
                  style={{
                    width: `${pct}%`,
                    background: p.key === "fault" ? "var(--fault)" : p.key === "recovery" ? "var(--ok)" : "var(--accent)",
                    transition: "width 0.6s linear",
                  }}
                />
              </div>
              <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                <span>{started ? `started ${started.slice(11, 19)}` : "no event yet"}</span>
                <span>
                  {elapsed === null ? "–" : `${elapsed.toFixed(1)} s`} / {planned} s
                </span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="note mt-2">
        Phase boundaries and elapsed times come from the runner&apos;s own <span className="mono">phase_events.csv</span> and
        the VM clock, polled every four seconds. The VM clock is not NTP-synchronised; only within-run ordering is meaningful.
      </div>
    </div>
  );
}

export function StateBadge({ state }: { state?: string | null }) {
  const map: Record<string, string> = {
    running: "badge-info",
    complete: "badge-ok",
    failed: "badge-bad",
    failed_to_start: "badge-bad",
    stale_running_no_process: "badge-warn",
    not_started: "badge-muted",
    unknown: "badge-warn",
  };
  return <span className={`badge ${map[state ?? ""] ?? "badge-muted"}`}>{state ?? "unknown"}</span>;
}
