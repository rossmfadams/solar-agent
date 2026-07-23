const STORAGE_KEY = "helios_recent_runs";
const MAX_RUNS = 10;

export interface RecentRun {
  site_id: string;
  address: string;
  score: number | null;
}

export function getRecentRuns(): RecentRun[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveRecentRun(run: RecentRun): void {
  const existing = getRecentRuns().filter((r) => r.site_id !== run.site_id);
  const next = [run, ...existing].slice(0, MAX_RUNS);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // localStorage unavailable (e.g. private browsing quota) — skip persisting.
  }
}
