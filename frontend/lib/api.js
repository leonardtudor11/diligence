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
