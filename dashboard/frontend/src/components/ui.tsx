"use client";

import { useState } from "react";

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-end justify-between mb-5 gap-4">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--navy)" }}>
          {title}
        </h1>
        {subtitle && <div className="note mt-0.5">{subtitle}</div>}
      </div>
      {right}
    </div>
  );
}

export function ErrorBox({ error, action }: { error: string | null | undefined; action?: string }) {
  if (!error) return null;
  return (
    <div className="callout callout-bad my-2">
      <div className="font-semibold text-sm">Something failed</div>
      <div className="mono mt-1 break-words">{error}</div>
      {action && <div className="note mt-1">{action}</div>}
    </div>
  );
}

export function SourceTag({ kind }: { kind: "saved" | "live" | "vm" | "local" }) {
  const map = {
    saved: ["badge-muted", "SAVED EVALUATION RESULTS"],
    live: ["badge-info", "LIVE — CURRENT RUN"],
    vm: ["badge-info", "READ FROM VM"],
    local: ["badge-warn", "LOCAL COPY"],
  } as const;
  return <span className={`badge ${map[kind][0]}`}>{map[kind][1]}</span>;
}

/** Explicit confirmation before an action that changes the Mininet environment. */
export function ConfirmPanel({
  title,
  description,
  confirmLabel,
  danger,
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  description: React.ReactNode;
  confirmLabel: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [ack, setAck] = useState(false);
  return (
    <div className="callout callout-warn my-3">
      <div className="font-semibold text-sm">{title}</div>
      <div className="mt-1 text-sm">{description}</div>
      <label className="mt-2 flex items-center gap-2 text-sm">
        <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />I understand this modifies the isolated Mininet
        experiment environment inside the VM.
      </label>
      <div className="mt-2 flex gap-2">
        <button className={`btn ${danger ? "btn-danger" : "btn-primary"}`} disabled={!ack || busy} onClick={onConfirm}>
          {busy ? "Working…" : confirmLabel}
        </button>
        <button className="btn" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export function KeyValue({ items }: { items: Array<[string, React.ReactNode]> }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-slate-500">{k}</dt>
          <dd className="mono break-all">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SwitchSelect({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <select className="select" value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {[4, 8, 12].map((n) => (
        <option key={n} value={n}>
          {n} switches ({n - 1} candidate links)
        </option>
      ))}
    </select>
  );
}
