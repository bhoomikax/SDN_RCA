"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSelectedRun, runName } from "@/lib/run-selection";
import { usePoll } from "@/lib/api";

const NAV = [
  { href: "/", label: "Live Demo", icon: "▶" },
  { href: "/topology", label: "Network Topology", icon: "⛓" },
  { href: "/telemetry", label: "Live Telemetry", icon: "〰" },
  { href: "/results", label: "Model Results", icon: "▦" },
  { href: "/comparison", label: "Model Comparison", icon: "▥" },
  { href: "/xai", label: "XAI / Explainability", icon: "◎" },
  { href: "/experiments", label: "Saved Experiments", icon: "☰" },
  { href: "/health", label: "System Health", icon: "♥" },
];

export function Sidebar() {
  const pathname = usePathname();
  const { run } = useSelectedRun();
  const active = usePoll<{ active: { name: string } | null }>("/api/experiments/active", 5000);
  return (
    <aside className="w-64 shrink-0 text-white flex flex-col" style={{ background: "var(--navy)" }}>
      <div className="px-5 pt-6 pb-4 border-b border-white/10">
        <div className="text-base font-semibold leading-tight">SDN Fault Localisation</div>
        <div className="text-xs text-white/60 mt-0.5">Research Demo</div>
        <div className="text-[11px] text-white/50 mt-2 leading-snug">
          Topology-Aware, Temporally Informed Root-Cause Analysis
        </div>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                isActive ? "bg-white/15 font-semibold" : "text-white/80 hover:bg-white/10"
              }`}
            >
              <span className="w-4 text-center text-white/60">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="px-5 py-4 border-t border-white/10 text-[11px] text-white/60 space-y-1">
        <div>
          <span className="text-white/40">Selected run: </span>
          <span className="text-white/80">{runName(run)}</span>
        </div>
        <div>
          <span className="text-white/40">Active VM run: </span>
          <span className="text-white/80">
            {active.error ? "backend unreachable" : active.data?.active ? active.data.active.name : "none"}
          </span>
        </div>
      </div>
    </aside>
  );
}
