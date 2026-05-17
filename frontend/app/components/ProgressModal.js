"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { streamUrl } from "../../lib/api";

// Ordered stepper labels. Each entry maps one or more SSE event names
// to the human label shown in the modal. Cached runs short-circuit the
// ingest substeps via the single `ingest_cached` event.
const STEPS = [
  { id: "start", label: "Connecting to pipeline" },
  { id: "ingest", label: "Fetching filings + audio" },
  { id: "filing", label: "Filing analyst (Gemini)" },
  { id: "call", label: "Call analyst (Gemini)" },
  { id: "bull", label: "Bull / Bear (Qwen3)" },
  { id: "reconciler", label: "Reconciling disputed facts" },
  { id: "done", label: "Ready" },
];

function classifyEvent(evt) {
  if (!evt || !evt.event) return null;
  if (evt.event === "start") return "start";
  if (evt.event === "ingest_start" || evt.event === "ingest_done" || evt.event === "ingest_cached") return "ingest";
  if (evt.event === "node_complete") {
    if (evt.node === "filing") return "filing";
    if (evt.node === "call") return "call";
    if (evt.node === "bull" || evt.node === "bear") return "bull";
    if (evt.node === "reconciler") return "reconciler";
  }
  if (evt.event === "done") return "done";
  return null;
}

export default function ProgressModal({ ticker, runId, cached, onClose }) {
  const router = useRouter();
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const esRef = useRef(null);
  const redirectedRef = useRef(false);

  useEffect(() => {
    const url = streamUrl(ticker, runId);
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        setEvents((prev) => [...prev, payload]);
        if (payload.event === "error") {
          setError(payload.error || "Pipeline error");
        }
        if (payload.event === "done") {
          setDone(true);
        }
      } catch {
        // Ignore non-JSON keep-alive comments etc.
      }
    };
    es.onerror = () => {
      // EventSource will auto-reconnect on transient drops. We only flag
      // a hard error if the stream is closed (readyState 2 = CLOSED).
      if (es.readyState === 2 && !done) {
        setError("Stream closed unexpectedly. Try again.");
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [ticker, runId, done]);

  // Redirect to the dashboard once the reconciler emits done. Small
  // delay so the user sees the green "Ready" state instead of a flash.
  useEffect(() => {
    if (!done || redirectedRef.current) return;
    redirectedRef.current = true;
    const t = setTimeout(() => {
      router.push(`/research/${ticker}`);
    }, 600);
    return () => clearTimeout(t);
  }, [done, router, ticker]);

  const completedSteps = useMemo(() => {
    const hit = new Set();
    for (const e of events) {
      const c = classifyEvent(e);
      if (c) hit.add(c);
    }
    return hit;
  }, [events]);

  const ingestInfo = events.find((e) => e.event === "ingest_done");
  const ingestCached = events.some((e) => e.event === "ingest_cached");
  const audioTier = ingestInfo?.audio_tier;
  const audioUploader = ingestInfo?.audio_uploader;
  const warnings = ingestInfo?.warnings || [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Running diligence on ${ticker}`}
    >
      <div className="w-full max-w-md rounded-lg border border-border/60 bg-background p-6 shadow-2xl">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display text-2xl font-bold tracking-tight">
            {ticker}
          </h2>
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-foreground/40">
            {cached ? "cached" : "live run"}
          </p>
        </div>

        <ol className="mt-5 space-y-2.5">
          {STEPS.map((s) => {
            const isDone = completedSteps.has(s.id);
            const isCurrent = !isDone && (
              (s.id === "start" && events.length === 0) ||
              (s.id !== "start" && completedSteps.size > 0 && !isDone)
            );
            return (
              <li
                key={s.id}
                className="flex items-center gap-3 font-mono text-sm"
              >
                <span
                  className={
                    "inline-block h-2 w-2 rounded-full " +
                    (isDone
                      ? "bg-accent shadow-[0_0_8px_rgba(34,197,94,0.7)]"
                      : isCurrent
                      ? "animate-pulse bg-foreground/60"
                      : "bg-foreground/15")
                  }
                />
                <span
                  className={
                    isDone
                      ? "text-foreground"
                      : isCurrent
                      ? "text-foreground/80"
                      : "text-foreground/40"
                  }
                >
                  {s.label}
                </span>
              </li>
            );
          })}
        </ol>

        {ingestCached ? (
          <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.2em] text-foreground/50">
            Using cached pipeline data — no API spend.
          </p>
        ) : ingestInfo ? (
          <div className="mt-5 space-y-1 rounded border border-border/40 bg-secondary/20 p-3 font-mono text-[11px] text-foreground/70">
            <p>
              <span className="text-foreground/40">Audio source:</span>{" "}
              <span className="text-foreground">{audioUploader || "—"}</span>
              {audioTier ? (
                <span className="ml-2 rounded bg-background/40 px-1.5 py-0.5 text-[9px] tracking-wider text-foreground/60">
                  {audioTier.split("_")[0]}
                </span>
              ) : null}
            </p>
            {warnings.length > 0 ? (
              <ul className="mt-1 list-disc pl-4 text-foreground/60">
                {warnings.slice(0, 3).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        {error ? (
          <div className="mt-5 rounded border border-destructive/50 bg-destructive/10 p-3 font-mono text-xs text-destructive">
            {error}
          </div>
        ) : null}

        <div className="mt-6 flex justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="font-mono text-xs uppercase tracking-[0.2em] text-foreground/50 hover:text-foreground"
          >
            Close
          </button>
          {done ? (
            <span className="font-mono text-xs uppercase tracking-[0.2em] text-accent">
              Loading dashboard…
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
