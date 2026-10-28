"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8765";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function tokenHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? window.localStorage.getItem("sdn.dashboard.token")
      : null;
  return token ? { "X-Dashboard-Token": token } : {};
}

async function handle(res: Response) {
  const text = await res.text();
  let body: unknown = text;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in (body as object)
        ? (body as { detail: unknown }).detail
        : body;
    throw new ApiError(res.status, detail);
  }
  return body;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function apiGet<T = any>(path: string, timeoutMs = 60000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(API_BASE + path, {
      signal: controller.signal,
      cache: "no-store",
    });
    return (await handle(res)) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, `Backend unreachable at ${API_BASE} (${(err as Error).message})`);
  } finally {
    clearTimeout(timer);
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function apiPost<T = any>(path: string, body: unknown, timeoutMs = 600000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...tokenHeaders() },
      body: JSON.stringify(body ?? {}),
      signal: controller.signal,
    });
    return (await handle(res)) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, `Backend unreachable at ${API_BASE} (${(err as Error).message})`);
  } finally {
    clearTimeout(timer);
  }
}

export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "error" in (d as object)) {
      return String((d as { error: unknown }).error);
    }
    return JSON.stringify(d);
  }
  return err instanceof Error ? err.message : String(err);
}

/** Poll a GET endpoint without reloading the page. Returns the latest data,
 * the last error, and a manual refresh. Polling pauses while a request is in flight. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function usePoll<T = any>(path: string | null, intervalMs: number, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (!path || inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const result = await apiGet<T>(path);
      setData(result);
      setError(null);
      setUpdatedAt(Date.now());
    } catch (err) {
      setError(errorText(err));
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    if (!path || !enabled) return;
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [path, intervalMs, enabled, refresh]);

  return { data, error, loading, updatedAt, refresh };
}

export const METHOD_LABELS: Record<string, string> = {
  rf_baseline: "Random Forest",
  topology_link_ranker: "Topology ranker",
  graph_only: "GCN",
  temporal_only: "LSTM",
  graph_temporal: "GCN+LSTM",
};
export const METHOD_ORDER = [
  "rf_baseline",
  "topology_link_ranker",
  "graph_only",
  "temporal_only",
  "graph_temporal",
];

export function fmtPct(x: number | null | undefined, digits = 0) {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  return (x * 100).toFixed(digits) + "%";
}
export function fmtNum(x: number | null | undefined, digits = 3) {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  return x.toFixed(digits);
}
