"use client";

import { useEffect, useState } from "react";
import { listTickers, startResearch } from "../../lib/api";
import ProgressModal from "./ProgressModal";

const TICKER_RE = /^[A-Za-z0-9]{1,6}$/;

export default function TickerLauncher() {
  const [chips, setChips] = useState([]);
  const [chipsLoading, setChipsLoading] = useState(true);
  const [ticker, setTicker] = useState("");
  const [formError, setFormError] = useState(null);
  const [run, setRun] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listTickers()
      .then((rows) => {
        if (cancelled) return;
        setChips(rows);
        setChipsLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setChips([]);
        setChipsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const launch = async (raw, opts = {}) => {
    const t = (raw || "").trim().toUpperCase();
    if (!TICKER_RE.test(t)) {
      setFormError("Tickers are 1–6 letters or digits, e.g. NVDA, BRK.B → BRKB.");
      return;
    }
    setFormError(null);
    try {
      const res = await startResearch(t, { force: !!opts.force });
      setRun({ ticker: t, runId: res.run_id, cached: !!res.cached });
    } catch (err) {
      setFormError(`Backend rejected the request: ${err.message || err}`);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    launch(ticker);
  };

  return (
    <div className="mt-7 flex w-full max-w-xl flex-col items-center gap-4">
      <form
        onSubmit={onSubmit}
        className="flex w-full flex-col items-stretch gap-2 sm:flex-row"
        aria-label="Research a ticker"
      >
        <label className="sr-only" htmlFor="ticker-input">
          Ticker symbol
        </label>
        <input
          id="ticker-input"
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase().slice(0, 6))}
          placeholder="Type a ticker — NVDA, TSLA, PLTR …"
          autoComplete="off"
          spellCheck={false}
          className="h-12 flex-1 rounded-md border border-border/60 bg-secondary/30 px-4 font-mono text-sm uppercase tracking-[0.2em] text-foreground placeholder:text-foreground/40 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/30"
        />
        <button
          type="submit"
          className="h-12 rounded-md bg-accent px-6 font-mono text-sm font-semibold tracking-wide text-background transition-all duration-200 hover:brightness-110"
        >
          Run diligence
        </button>
      </form>
      {formError ? (
        <p className="font-mono text-xs text-destructive" role="alert">
          {formError}
        </p>
      ) : null}

      <div className="flex w-full flex-col items-center gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.4em] text-foreground/40">
          {chipsLoading ? "Loading cached tickers…" : "Or jump into a cached run"}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {chips.map((c) => (
            <button
              key={c.ticker}
              type="button"
              onClick={() => launch(c.ticker)}
              className="group inline-flex items-center gap-2 rounded-full border border-border/60 bg-secondary/30 px-4 py-2 font-mono text-xs uppercase tracking-[0.2em] text-foreground/85 transition-colors hover:border-accent hover:text-accent"
              title={c.company || c.ticker}
            >
              <span className="font-semibold">{c.ticker}</span>
              {c.audio_tier ? (
                <span className="rounded bg-background/40 px-1.5 py-0.5 text-[9px] font-medium tracking-wider text-foreground/60 group-hover:text-accent/80">
                  {c.audio_tier.split("_")[0]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {run ? (
        <ProgressModal
          ticker={run.ticker}
          runId={run.runId}
          cached={run.cached}
          onClose={() => setRun(null)}
        />
      ) : null}
    </div>
  );
}
