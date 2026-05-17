// Small fetch shim for talking to backend/api.py.
//
// In production both the Next.js frontend (port 3000) and the FastAPI
// backend (127.0.0.1:8000) sit behind nginx — the frontend can hit
// "/api/..." paths directly. For local `next dev` we let an explicit
// DILIGENCE_API_BASE env var override.
//
// Server-side fetches go via the absolute URL because Node's fetch has
// no notion of relative origins. Browser-side fetches use the relative
// path so nginx routing Just Works.

const SERVER_BASE =
  process.env.DILIGENCE_API_BASE ||
  process.env.NEXT_PUBLIC_API_BASE ||
  "http://127.0.0.1:8000";

const BROWSER_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

function apiBase() {
  return typeof window === "undefined" ? SERVER_BASE : BROWSER_BASE;
}

export function apiUrl(path) {
  const base = apiBase();
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function getResearch(ticker) {
  const url = apiUrl(`/api/research/${ticker}`);
  const res = await fetch(url, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`getResearch ${ticker} → ${res.status}`);
  }
  return res.json();
}

// POST /api/research/{ticker} — kicks off (or surfaces) a run.
// Returns { run_id, ticker, cached }. Use cached=true to render the
// dashboard immediately without waiting for the SSE 'done' event.
export async function startResearch(ticker, { force = false } = {}) {
  const qs = force ? "?force=true" : "";
  const url = apiUrl(`/api/research/${ticker}${qs}`);
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    throw new Error(`startResearch ${ticker} → ${res.status}`);
  }
  return res.json();
}

// GET /api/tickers — chip set for the landing-page TickerLauncher.
export async function listTickers() {
  const url = apiUrl("/api/tickers");
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`listTickers → ${res.status}`);
  }
  const json = await res.json();
  return json.tickers || [];
}

// SSE URL for a given run_id. Caller passes this to `new EventSource(...)`.
export function streamUrl(ticker, runId) {
  return apiUrl(`/api/research/${ticker}/stream?run_id=${encodeURIComponent(runId)}`);
}
