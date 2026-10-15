import { useCallback, useEffect, useRef, useState } from "react";

/** Load data on mount / when deps change. Always resolves into data or error (never stuck loading). */
export function useApi(fn, deps = [], { pollMs } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const alive = useRef(true);
  const run = useCallback(async (silent = false) => {
    if (!silent) setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fn();
      if (alive.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (alive.current) setState((s) => ({ data: silent ? s.data : null, error, loading: false }));
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { alive.current = true; run(); return () => { alive.current = false; }; }, [run]);
  useEffect(() => {
    if (!pollMs) return undefined;
    const t = setInterval(() => run(true), pollMs);
    return () => clearInterval(t);
  }, [pollMs, run]);
  return { ...state, reload: run };
}

/** Wrap an async action with busy/error state. */
export function useAction(fn) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const run = useCallback(async (...args) => {
    setBusy(true); setError(null);
    try { const r = await fn(...args); setResult(r); return r; }
    catch (e) { setError(e); return null; }
    finally { setBusy(false); }
  }, [fn]);
  return { run, busy, error, result, reset: () => { setError(null); setResult(null); } };
}
