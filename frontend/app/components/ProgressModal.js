"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { streamUrl } from "../../lib/api";

// Ordered stepper labels. The pipeline runs filing+call in parallel
// then bull+bear in parallel — we render those as single combined
// steps so the UI doesn't imply a sequential order that doesn't exist
// in the graph. A combined step is "complete" only when BOTH its
// parallel children have emitted node_complete.
const STEPS = [
  { id: "start",      label: "Connecting to pipeline" },
  { id: "ingest",     label: "Fetching filings + audio" },
  { id: "extract",    label: "Filing + Call analysts (Gemini, parallel)", requires: ["filing", "call"] },
  { id: "debate",     label: "Bull + Bear analysts (Qwen3, parallel)",    requires: ["bull", "bear"] },
  { id: "reconciler", label: "Reconciling disputed facts" },
  { id: "done",       label: "Ready" },
];

function classifyEvent(evt) {
  if (!evt || !evt.event) return null;
  if (evt.event === "start") return "start";
  if (evt.event === "ingest_start" || evt.event === "ingest_done" || evt.event === "ingest_cached") return "ingest";
  if (evt.event === "node_complete") {
    if (evt.node === "filing" || evt.node === "call") return `_node:${evt.node}`;
    if (evt.node === "bull"   || evt.node === "bear") return `_node:${evt.node}`;
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

  const doneRef = useRef(false);
  useEffect(() => {
    doneRef.current = done;
  }, [done]);

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
      // EventSource auto-reconnects on transient drops. Only flag a
      // hard error if the stream is permanently closed AND the pipeline
      // hadn't already emitted `done` (reading via doneRef so this
      // effect doesn't re-run when `done` flips and reopens a second
      // stale EventSource).
      if (es.readyState === 2 && !doneRef.current) {
        setError("Stream closed unexpectedly. Try again.");
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [ticker, runId]);

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

  // Track which underlying nodes/events have completed; a parallel-
  // group step is "complete" only when every `requires` member has
  // landed. Avoids the previous behaviour where Bull's node_complete
  // alone marked the entire Bull+Bear step done.
  const completedSteps = useMemo(() => {
    const nodes = new Set();
    const direct = new Set();
    for (const e of events) {
      const c = classifyEvent(e);
      if (!c) continue;
      if (c.startsWith("_node:")) {
        nodes.add(c.slice("_node:".length));
      } else {
        direct.add(c);
      }
    }
    const hit = new Set(direct);
    for (const step of STEPS) {
      if (step.requires) {
        if (step.requires.every((n) => nodes.has(n))) hit.add(step.id);
      }
    }
    return hit;
  }, [events]);

  // First not-yet-done step in defined order; everything past it is
  // future, everything before it is past. Replaces the buggy "any
  // non-start step with events.length > 0 is current" heuristic which
  // marked all future steps as active simultaneously.
  const currentStepId = useMemo(() => {
    for (const s of STEPS) {
      if (!completedSteps.has(s.id)) return s.id;
    }
    return null;
  }, [completedSteps]);

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
            const isCurrent = s.id === currentStepId;
            return (
              <li
                key={s.id}
                className="flex items-center gap-3 font-mono text-sm"
              >
                <span
                  className={
                    "inline-block h-2.5 w-2.5 rounded-full transition-colors " +
                    (isDone
                      ? "bg-accent shadow-[0_0_8px_rgba(34,197,94,0.7)]"
                      : isCurrent
                      ? "animate-pulse bg-accent shadow-[0_0_10px_rgba(34,197,94,0.55)]"
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
            <p className="flex items-center gap-2 truncate">
              <span className="text-foreground/40">Audio source:</span>{" "}
              <span
                className="max-w-[14rem] truncate text-foreground"
                title={audioUploader || ""}
              >
                {audioUploader || "—"}
              </span>
              {audioTier ? (
                <span className="ml-1 shrink-0 rounded bg-background/40 px-1.5 py-0.5 text-[9px] tracking-wider text-foreground/60">
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
