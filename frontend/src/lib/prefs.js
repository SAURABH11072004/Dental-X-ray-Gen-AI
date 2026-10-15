import { useSyncExternalStore } from "react";

// Display preferences, stored only in this browser (never sent anywhere). Reading/writing can fail in private windows: every access is guarded.
const KEY = "dm_prefs_v1";
const DEFAULTS = { showResearch: false, reportLang: "en", showIds: true, showClasses: false, showMasks: true };
let cache = null;
const listeners = new Set();

function load() {
  if (cache) return cache;
  let stored = {};
  try { stored = JSON.parse(localStorage.getItem(KEY) || "{}") || {}; } catch { stored = {}; }
  cache = { ...DEFAULTS, ...stored };
  return cache;
}

export function setPrefs(patch) {
  cache = { ...load(), ...patch };
  try { localStorage.setItem(KEY, JSON.stringify(cache)); } catch { /* keep the in-memory value */ }
  listeners.forEach((l) => l());
}

export function usePrefs() {
  const prefs = useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, load, load);
  return [prefs, setPrefs];
}
