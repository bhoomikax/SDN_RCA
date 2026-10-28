"use client";

import { createContext, useContext, useEffect, useState } from "react";

export interface RunRef {
  switches: number;
  logical: number;
  physical: number;
}

interface RunSelection {
  run: RunRef | null;
  setRun: (run: RunRef | null) => void;
}

const Ctx = createContext<RunSelection>({ run: null, setRun: () => {} });
const KEY = "sdn.dashboard.selectedRun";

export function RunSelectionProvider({ children }: { children: React.ReactNode }) {
  const [run, setRunState] = useState<RunRef | null>(null);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(KEY);
      if (raw) setRunState(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);
  const setRun = (next: RunRef | null) => {
    setRunState(next);
    try {
      if (next) window.localStorage.setItem(KEY, JSON.stringify(next));
      else window.localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  };
  return <Ctx.Provider value={{ run, setRun }}>{children}</Ctx.Provider>;
}

export function useSelectedRun() {
  return useContext(Ctx);
}

export function runPath(run: RunRef) {
  return `/api/experiments/${run.switches}/${run.logical}/${run.physical}`;
}

export function runName(run: RunRef | null) {
  return run ? `physical_${run.physical}_logical_${run.logical} (${run.switches} switches)` : "no run selected";
}
