"use client";

export interface TopologyState {
  switches: number;
  /** Fault link configured in the registry for the selected IDs (planned, not live). */
  configuredFault?: string | null;
  /** Fault link as recorded by the running experiment's phase events (live). */
  observedFault?: string | null;
  /** Current phase of the running experiment, if any. */
  phase?: string | null;
  bottleneck?: string | null;
  /** Links to highlight as a model's top-1 prediction (not live network state). */
  predicted?: string | null;
}

function nodesFor(n: number) {
  const nodes = ["h1"];
  for (let i = 1; i <= n; i++) nodes.push(`s${i}`);
  nodes.push("h2");
  return nodes;
}

export function linkName(a: string, b: string) {
  return `${a}-${b}`;
}

export function TopologyDiagram({ state, compact = false }: { state: TopologyState; compact?: boolean }) {
  const nodes = nodesFor(state.switches);
  const width = Math.max(560, nodes.length * 86);
  const height = compact ? 120 : 170;
  const gap = (width - 80) / (nodes.length - 1);
  const y = compact ? 56 : 78;
  const liveDown = state.phase === "fault" && state.observedFault;
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" style={{ minWidth: width * 0.75 }}>
        {nodes.slice(0, -1).map((a, i) => {
          const b = nodes[i + 1];
          const name = linkName(a, b);
          const x1 = 40 + i * gap;
          const x2 = 40 + (i + 1) * gap;
          const isBottleneck = state.bottleneck === name;
          const isConfigured = state.configuredFault === name;
          const isObservedDown = liveDown && state.observedFault === name;
          const isPredicted = state.predicted === name;
          let stroke = "#b8c2d0";
          let dash: string | undefined;
          let widthPx = 3;
          if (isBottleneck) {
            stroke = "var(--bottleneck)";
            widthPx = 5;
          }
          if (isConfigured) {
            stroke = "var(--fault)";
            dash = "8 5";
            widthPx = 4;
          }
          if (isObservedDown) {
            stroke = "var(--fault)";
            dash = "3 5";
            widthPx = 5;
          }
          return (
            <g key={name}>
              {isBottleneck && (
                <line x1={x1} y1={y} x2={x2} y2={y} stroke="var(--bottleneck)" strokeWidth={11} strokeOpacity={0.18} />
              )}
              {isPredicted && (
                <line x1={x1} y1={y} x2={x2} y2={y} stroke="var(--accent)" strokeWidth={13} strokeOpacity={0.22} />
              )}
              <line x1={x1} y1={y} x2={x2} y2={y} stroke={stroke} strokeWidth={widthPx} strokeDasharray={dash} strokeLinecap="round" />
              {!compact && (
                <text x={(x1 + x2) / 2} y={y + 30} textAnchor="middle" fontSize="10" fill="#6b7a8f">
                  {a.startsWith("s") && b.startsWith("s") ? name : ""}
                </text>
              )}
              {isObservedDown && (
                <text x={(x1 + x2) / 2} y={y - 22} textAnchor="middle" fontSize="10" fontWeight={700} fill="var(--fault)">
                  DOWN (live)
                </text>
              )}
              {isBottleneck && !compact && (
                <text x={(x1 + x2) / 2} y={y + 44} textAnchor="middle" fontSize="9" fill="var(--bottleneck)">
                  10 Mbps / 5 ms
                </text>
              )}
            </g>
          );
        })}
        {nodes.map((node, i) => {
          const x = 40 + i * gap;
          const isHost = node.startsWith("h");
          return (
            <g key={node}>
              {isHost ? (
                <rect x={x - 16} y={y - 14} width={32} height={28} rx={5} fill="#eef2f7" stroke="#7d8ca0" strokeWidth={1.5} />
              ) : (
                <circle cx={x} cy={y} r={15} fill="#ffffff" stroke="var(--navy)" strokeWidth={2} />
              )}
              <text x={x} y={y + 4} textAnchor="middle" fontSize="10.5" fontWeight={600} fill="var(--navy)">
                {node}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function TopologyLegend({ showPredicted = false }: { showPredicted?: boolean }) {
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
      <span className="inline-flex items-center gap-2">
        <span style={{ width: 28, height: 0, borderTop: "4px solid var(--bottleneck)" }} /> bottleneck link (10 Mbps / 5 ms)
      </span>
      <span className="inline-flex items-center gap-2">
        <span style={{ width: 28, height: 0, borderTop: "4px dashed var(--fault)" }} /> configured fault link (registry; injected only during the fault phase)
      </span>
      <span className="inline-flex items-center gap-2">
        <span style={{ width: 28, height: 0, borderTop: "4px dotted var(--fault)" }} /> link currently down (from the running experiment&apos;s phase events)
      </span>
      {showPredicted && (
        <span className="inline-flex items-center gap-2">
          <span style={{ width: 28, height: 8, background: "rgba(31,95,191,0.25)" }} /> model top-1 prediction (not network state)
        </span>
      )}
    </div>
  );
}
